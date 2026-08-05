import json
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests.classes import IntegrationTestCase, UnitTestCase

from za_local_core.sa_vat.doctype.vat201_return.vat201_return import VAT201Return
from za_local_core.sa_vat.install import seed_vat_statutory_source_catalog
from za_local_core.sa_vat.periods import (
	build_active_period_key,
	resolve_filing_category,
	validate_filing_period,
)
from za_local_core.sa_vat.setup import (
	backfill_vat201_active_period_keys,
	backfill_vat201_filing_categories,
	bootstrap_company_vat_setup,
	ensure_vat_custom_fields,
)
from za_local_core.sa_vat.statutory import (
	CURRENT_APPROVED_SOURCE_METADATA,
	FULL_INVOICE_THRESHOLD,
	NO_INVOICE_THRESHOLD,
	resolve_vat_controls,
)
from za_local_core.sa_vat.tax_invoice import build_sales_invoice_print_profile
from za_local_core.tests.e2e_setup import stage_approved_test_vat_governance
from za_local_core.tests.vat_fixtures import get_configured_vat_company

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
TEST_VAT_CONTROLS = {
	"values": {NO_INVOICE_THRESHOLD: 50, FULL_INVOICE_THRESHOLD: 5000},
	"source": "ZA-SRC-TEST",
	"source_sha256": "a" * 64,
	"rate_pack": "ZA-RATE-TEST",
	"rate_pack_sha256": "b" * 64,
	"effective_from": "2026-04-01",
	"effective_to": "2027-03-31",
}


class TestFinanceRemediation(UnitTestCase):
	def test_finance_owns_all_required_erpnext_custom_fields(self):
		with patch("za_local_core.sa_vat.setup.create_custom_fields") as create_fields:
			ensure_vat_custom_fields()

		definitions = create_fields.call_args.args[0]
		expected = {
			"Customer": {"za_company_registration": "Data", "za_is_vat_vendor": "Check"},
			"Item Group": {"is_capital_goods": "Check"},
		}
		for doctype, fields in expected.items():
			by_name = {field["fieldname"]: field for field in definitions[doctype]}
			for fieldname, fieldtype in fields.items():
				self.assertEqual(fieldtype, by_name[fieldname]["fieldtype"])
				self.assertEqual("SA VAT", by_name[fieldname]["module"])

	def test_all_sars_filing_categories_accept_their_complete_periods(self):
		valid_periods = {
			"Category A": ("2025-12-01", "2026-01-31"),
			"Category B": ("2026-01-01", "2026-02-28"),
			"Category C": ("2026-04-01", "2026-04-30"),
			"Category D": ("2026-03-01", "2026-08-31"),
			"Category E": ("2026-03-01", "2027-02-28"),
		}
		for category, period in valid_periods.items():
			with self.subTest(category=category):
				validate_filing_period(category, *period)

	def test_generic_quarterly_and_invalid_category_are_rejected(self):
		for value in ("Quarterly", "Every Four Months"):
			with self.subTest(value=value), self.assertRaises(frappe.ValidationError):
				resolve_filing_category(None, value, "2026-01-01", "2026-03-31")

	def test_category_schedule_and_partial_months_are_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			validate_filing_period("Category A", "2026-01-01", "2026-02-28")
		with self.assertRaises(frappe.ValidationError):
			validate_filing_period("Category C", "2026-04-02", "2026-04-30")
		with self.assertRaises(frappe.ValidationError):
			validate_filing_period("Category D", "2026-04-01", "2026-09-30")

	def test_legacy_monthly_and_bimonthly_periods_migrate_deterministically(self):
		self.assertEqual("Category C", resolve_filing_category(None, "Monthly"))
		self.assertEqual("Category D", resolve_filing_category(None, "Six-Monthly"))
		self.assertEqual("Category E", resolve_filing_category(None, "Annually"))
		self.assertEqual(
			"Category A",
			resolve_filing_category(None, "Bi-Monthly", "2025-12-01", "2026-01-31"),
		)
		self.assertEqual(
			"Category B",
			resolve_filing_category(None, "Bi-Monthly", "2026-01-01", "2026-02-28"),
		)

	def test_active_period_key_is_stable_and_company_scoped(self):
		first = build_active_period_key("Test Company", "2026-04-01", "2026-04-30")
		self.assertEqual(first, build_active_period_key("Test Company", "2026-04-01", "2026-04-30"))
		self.assertNotEqual(first, build_active_period_key("Other Company", "2026-04-01", "2026-04-30"))
		self.assertEqual(64, len(first))

	def test_active_period_backfill_preserves_conflicting_historical_rows(self):
		rows = [
			frappe._dict(
				name="VAT201-0001",
				company="Test Company",
				from_date="2026-04-01",
				to_date="2026-04-30",
				active_period_key=None,
			),
			frappe._dict(
				name="VAT201-0002",
				company="Test Company",
				from_date="2026-04-01",
				to_date="2026-04-30",
				active_period_key=None,
			),
		]
		meta = frappe._dict(has_field=lambda fieldname: fieldname == "active_period_key")
		with (
			patch("frappe.db.table_exists", return_value=True),
			patch("frappe.get_meta", return_value=meta),
			patch("frappe.get_all", return_value=rows),
			patch("frappe.db.set_value") as set_value,
			patch("frappe.logger"),
		):
			result = backfill_vat201_active_period_keys()

		self.assertEqual(1, result["updated"])
		self.assertEqual([{"name": "VAT201-0002", "conflicts_with": "VAT201-0001"}], result["conflicts"])
		set_value.assert_called_once()

	def test_historical_category_backfill_updates_only_valid_unambiguous_periods(self):
		rows = [
			frappe._dict(
				name="VAT201-MONTHLY",
				tax_period="Monthly",
				filing_category=None,
				from_date="2026-04-01",
				to_date="2026-04-30",
			),
			frappe._dict(
				name="VAT201-QUARTERLY",
				tax_period="Quarterly",
				filing_category=None,
				from_date="2026-04-01",
				to_date="2026-06-30",
			),
		]
		meta = frappe._dict(has_field=lambda fieldname: fieldname == "filing_category")
		with (
			patch("frappe.db.table_exists", return_value=True),
			patch("frappe.get_meta", return_value=meta),
			patch("frappe.get_all", return_value=rows),
			patch("frappe.db.set_value") as set_value,
			patch("frappe.logger"),
		):
			result = backfill_vat201_filing_categories()

		self.assertEqual(1, result["updated"])
		self.assertEqual("VAT201-QUARTERLY", result["unresolved"][0]["name"])
		set_value.assert_called_once_with(
			"VAT201 Return",
			"VAT201-MONTHLY",
			"filing_category",
			"Category C",
			update_modified=False,
		)

	def test_box_18_other_input_adjustment_reduces_vat_payable(self):
		doc = frappe.new_doc("VAT201 Return")
		doc.transactions = []
		doc.change_in_use_output = 100
		doc.bad_debts_output = 0
		doc.other_output = 0
		doc.change_in_use_input = 0
		doc.bad_debts_input = 0
		doc.other_input_adjustment = 25
		doc.diesel_refund = 0

		VAT201Return.calculate_totals(doc)

		self.assertEqual(25, doc.total_input_tax)
		self.assertEqual(75, doc.vat_payable)
		self.assertIn("18", [row["box"] for row in VAT201Return.get_summary_rows(doc)])

	def test_zero_rated_only_supply_uses_full_tax_invoice(self):
		with patch("za_local_core.sa_vat.tax_invoice.is_company_in_south_africa", return_value=True):
			profile = build_sales_invoice_print_profile(
				company="Test Company",
				posting_date="2026-04-10",
				base_grand_total=500,
				company_currency="ZAR",
				is_zero_rated_only=1,
				statutory_controls=TEST_VAT_CONTROLS,
			)

		self.assertEqual("full_tax_invoice", profile["invoice_type"])
		self.assertEqual("SA Full Tax Invoice", profile["print_format"])
		self.assertEqual("zero_rated_full_particulars", profile["threshold_basis"])

	def test_vat201_schema_has_amendment_box18_and_unique_active_period_fields(self):
		path = PACKAGE_ROOT / "sa_vat" / "doctype" / "vat201_return" / "vat201_return.json"
		fields = {field["fieldname"]: field for field in json.loads(path.read_text())["fields"]}
		self.assertEqual("VAT201 Return", fields["amended_from"]["options"])
		self.assertEqual(1, fields["amended_from"]["no_copy"])
		self.assertEqual(1, fields["active_period_key"]["unique"])
		self.assertEqual("Currency", fields["other_input_adjustment"]["fieldtype"])

	def test_active_print_templates_escape_document_values(self):
		commercial = (PACKAGE_ROOT / "templates" / "print_format" / "sa_commercial_document.html").read_text()
		payment = (PACKAGE_ROOT / "templates" / "print_format" / "sa_payment_entry.html").read_text()
		vat201 = (PACKAGE_ROOT / "templates" / "print_format" / "sa_vat201_return.html").read_text()
		self.assertIn("doc.terms | striptags | e", commercial)
		self.assertIn("item.description | striptags | e", commercial)
		self.assertIn('doc.get("party_name") or doc.get("party")) | e', payment)
		self.assertIn("row.voucher_no | e", vat201)
		self.assertNotIn("{{ doc.terms }}", commercial)


class TestFinanceInstallMetadata(IntegrationTestCase):
	def test_production_install_stages_only_unapproved_vat_source_metadata(self):
		pack_count = frappe.db.count("ZA Statutory Rate Pack", {"domain": "VAT", "docstatus": 1})
		source_name = seed_vat_statutory_source_catalog()
		source = frappe.db.get_value(
			"ZA Statutory Source",
			source_name,
			["catalog_key", "status", "docstatus", "source_file", "reviewed_by"],
			as_dict=True,
		)
		self.assertEqual("SARS-VAT-CONTROLS-2026-04-01", source.catalog_key)
		self.assertEqual("Draft", source.status)
		self.assertEqual(0, source.docstatus)
		self.assertFalse(source.source_file)
		self.assertFalse(source.reviewed_by)
		self.assertEqual(
			pack_count,
			frappe.db.count("ZA Statutory Rate Pack", {"domain": "VAT", "docstatus": 1}),
		)

	def test_fresh_site_bootstrap_blocks_until_governance_is_approved(self):
		company = frappe.db.get_value("Company", {"country": "South Africa"}, "name")
		if not company:
			self.skipTest("A South African company is required.")
		with self.assertRaises(frappe.ValidationError):
			bootstrap_company_vat_setup(company, statutory_control_date="2099-01-01")

	def test_e2e_setup_stages_reviewed_submitted_test_source_and_pack(self):
		governance = stage_approved_test_vat_governance()
		self.assertEqual(1, frappe.db.get_value("ZA Statutory Source", governance["source"], "docstatus"))
		self.assertEqual(
			"Approved", frappe.db.get_value("ZA Statutory Source", governance["source"], "status")
		)
		self.assertEqual(
			1, frappe.db.get_value("ZA Statutory Rate Pack", governance["rate_pack"], "docstatus")
		)
		controls = resolve_vat_controls("2026-04-01")
		self.assertEqual(CURRENT_APPROVED_SOURCE_METADATA["expected_current_values"], controls["values"])

	def test_required_erpnext_metadata_exists_with_finance_ownership(self):
		expected = {
			("Customer", "za_company_registration"): "Data",
			("Customer", "za_is_vat_vendor"): "Check",
			("Item Group", "is_capital_goods"): "Check",
		}
		for (doctype, fieldname), fieldtype in expected.items():
			with self.subTest(doctype=doctype, fieldname=fieldname):
				field = frappe.get_meta(doctype).get_field(fieldname)
				self.assertIsNotNone(field)
				self.assertEqual(fieldtype, field.fieldtype)
				custom_field = frappe.db.get_value(
					"Custom Field",
					{"dt": doctype, "fieldname": fieldname},
					["module", "fieldtype"],
					as_dict=True,
				)
				self.assertEqual("SA VAT", custom_field.module)
				self.assertEqual(fieldtype, custom_field.fieldtype)

	def test_vat201_duplicate_period_is_blocked_and_cancelled_return_can_be_amended(self):
		company = get_configured_vat_company()
		if not company:
			self.skipTest("A South African company with VAT Settings is required.")

		values = {
			"doctype": "VAT201 Return",
			"company": company,
			"filing_category": "Category C",
			"from_date": "2020-01-01",
			"to_date": "2020-01-31",
			"submission_date": "2020-02-01",
			"status": "Draft",
			"filing_due_date": "2020-02-25",
			"filing_reviewer": "Administrator",
			"filing_approver": "Administrator",
		}
		# Instantiate the app controller directly. Frappe CLI test processes load
		# modules from every app present on the bench, including an uninstalled
		# legacy za_local checkout that declares the same transitional module name.
		# Web requests and jobs correctly use installed-app module ownership.
		original = VAT201Return(values).insert()
		with self.assertRaises(frappe.ValidationError):
			VAT201Return(values).insert()

		with (
			patch("za_local_core.sa_vat.doctype.vat201_return.vat201_return.verify_snapshots"),
			patch("za_local_core.sa_vat.doctype.vat201_return.vat201_return.verify_live_ledger"),
			patch("za_local_core.sa_vat.doctype.vat201_return.vat201_return.create_filing"),
		):
			original.submit()
			original.cancel()
		self.assertIsNone(frappe.db.get_value("VAT201 Return", original.name, "active_period_key"))

		amended = VAT201Return({**values, "amended_from": original.name}).insert()
		self.assertEqual(original.name, amended.amended_from)
		self.assertTrue(amended.active_period_key)
