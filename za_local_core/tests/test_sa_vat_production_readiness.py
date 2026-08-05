import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from za_local_core.custom.customer import validate as validate_customer
from za_local_core.sa_vat.doctype.vat201_return.vat201_return import VAT201Return
from za_local_core.sa_vat.report.vat_201_account_classifications import vat_201_account_classifications
from za_local_core.sa_vat.report.vat_201_linked_transactions import vat_201_linked_transactions
from za_local_core.sa_vat.setup import ensure_vat_custom_fields, validate_vat_posting_account
from za_local_core.sa_vat.statutory import FULL_INVOICE_THRESHOLD, NO_INVOICE_THRESHOLD
from za_local_core.sa_vat.tax_invoice import (
	build_sales_invoice_print_profile,
	check_tax_invoice_readiness,
	get_sales_invoice_print_profile,
)

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


class TestSAVATProductionReadiness(unittest.TestCase):
	def test_non_zar_threshold_is_conservative_and_returns_use_credit_note(self):
		with patch("za_local_core.sa_vat.tax_invoice.is_company_in_south_africa", return_value=True):
			profile = build_sales_invoice_print_profile(
				company="Test Company",
				posting_date="2026-04-10",
				base_grand_total=100,
				company_currency="USD",
				statutory_controls=TEST_VAT_CONTROLS,
			)
			credit = build_sales_invoice_print_profile(
				company="Test Company",
				posting_date="2026-04-10",
				base_grand_total=-5750,
				is_return=1,
				company_currency="ZAR",
				statutory_controls=TEST_VAT_CONTROLS,
			)

		self.assertEqual("full_tax_invoice", profile["invoice_type"])
		self.assertEqual("conservative_non_zar_company_currency", profile["threshold_basis"])
		self.assertEqual("credit_note", credit["invoice_type"])
		self.assertEqual("SA Credit Note", credit["print_format"])

	def test_abridged_readiness_does_not_require_recipient_details(self):
		invoice = SimpleNamespace(
			name="SINV-TEST",
			company="Test Company",
			base_grand_total=115,
			grand_total=115,
			is_pos=0,
			is_return=0,
			company_address_display="1 Test Street",
			company_tax_id="4123456789",
			customer=None,
			customer_name=None,
			address_display=None,
			posting_date="2026-04-10",
			items=[SimpleNamespace(description="Service", qty=1)],
			total_taxes_and_charges=15,
		)
		with (
			patch("za_local_core.sa_vat.tax_invoice.frappe.get_doc", return_value=invoice),
			patch(
				"za_local_core.sa_vat.tax_invoice.get_company_vat_registration_number",
				return_value="4123456789",
			),
			patch("za_local_core.sa_vat.tax_invoice.get_company_currency", return_value="ZAR"),
			patch("za_local_core.sa_vat.tax_invoice.is_company_in_south_africa", return_value=True),
			patch(
				"za_local_core.sa_vat.tax_invoice.resolve_vat_controls",
				return_value=TEST_VAT_CONTROLS,
			),
		):
			result = check_tax_invoice_readiness("SINV-TEST")

		self.assertEqual("ready", result["status"])
		self.assertNotIn("Recipient name", result["missing"])
		self.assertNotIn("Recipient address", result["missing"])

	def test_print_profile_endpoint_checks_invoice_and_company_permissions(self):
		with (
			patch("za_local_core.sa_vat.tax_invoice.frappe.has_permission") as has_permission,
			patch("za_local_core.sa_vat.tax_invoice.get_company_currency", return_value="ZAR"),
			patch("za_local_core.sa_vat.tax_invoice.is_company_in_south_africa", return_value=True),
			patch(
				"za_local_core.sa_vat.tax_invoice.resolve_vat_controls",
				return_value=TEST_VAT_CONTROLS,
			),
		):
			get_sales_invoice_print_profile(
				company="Test Company", posting_date="2026-04-10", base_grand_total=115
			)

		has_permission.assert_any_call("Sales Invoice", "read", throw=True)
		has_permission.assert_any_call("Company", "read", "Test Company", throw=True)

	def test_return_sign_is_not_inverted_twice(self):
		worker = SimpleNamespace()
		self.assertEqual(
			1, VAT201Return.get_invoice_sign(worker, frappe._dict(is_return=1, base_net_total=-100))
		)
		self.assertEqual(
			-1, VAT201Return.get_invoice_sign(worker, frappe._dict(is_return=1, base_net_total=100))
		)

	def test_vat201_allocation_uses_vat_inclusive_consideration_and_reversal_side(self):
		worker = SimpleNamespace(make_transaction_row=lambda **values: values)
		invoice = frappe._dict(name="SINV-TEST", posting_date="2026-04-10")
		rows = VAT201Return.allocate_tax_by_group(
			worker,
			invoice,
			{"Output - A Standard rate (excl capital goods)": 100},
			15,
			"SA Standard Rated Sales 15% - Test Company",
		)
		reversal = VAT201Return.allocate_tax_by_group(
			worker,
			invoice,
			{"Output - A Standard rate (excl capital goods)": -100},
			-15,
			"SA Standard Rated Sales 15% - Test Company",
		)

		self.assertEqual(115, rows[0]["incl_tax_amount"])
		self.assertEqual(15, rows[0]["tax_account_credit"])
		self.assertEqual(-115, reversal[0]["incl_tax_amount"])
		self.assertEqual(15, reversal[0]["tax_account_debit"])

	def test_vat_posting_accounts_must_be_enabled_tax_ledgers_for_the_company(self):
		with patch(
			"za_local_core.sa_vat.setup.frappe.db.get_value",
			return_value=frappe._dict(company="Test Company", account_type="Tax", is_group=0, disabled=0),
		):
			validate_vat_posting_account("VAT Output - TC", "Test Company", "Output VAT Account")

	def test_linked_report_authorizes_parent_before_reading_child_rows(self):
		with (
			patch(
				"za_local_core.sa_vat.report.vat_201_linked_transactions.vat_201_linked_transactions.frappe.get_doc"
			) as get_doc,
			patch(
				"za_local_core.sa_vat.report.vat_201_linked_transactions.vat_201_linked_transactions.frappe.get_all",
				return_value=[],
			),
		):
			vat_201_linked_transactions.get_data({"vat_return": "VAT201-TEST"})

		get_doc.assert_called_once_with("VAT201 Return", "VAT201-TEST", check_permission=True)

	def test_account_classification_report_uses_permission_filtered_list(self):
		with (
			patch(
				"za_local_core.sa_vat.report.vat_201_account_classifications.vat_201_account_classifications.frappe.has_permission"
			) as has_permission,
			patch(
				"za_local_core.sa_vat.report.vat_201_account_classifications.vat_201_account_classifications.frappe.get_list",
				return_value=[],
			) as get_list,
		):
			vat_201_account_classifications.execute({"company": "Test Company"})

		has_permission.assert_called_once_with("Account", "read", throw=True)
		self.assertEqual("Account", get_list.call_args.args[0])

	def test_vat_print_formats_use_shared_templates(self):
		for path in (PACKAGE_ROOT / "sa_vat" / "print_format").glob("*/sa_*.json"):
			data = json.loads(path.read_text())
			if data["name"] == "SA VAT201 Return":
				continue
			self.assertIn("{% include", data["html"], msg=data["name"])
			self.assertLess(len(data["html"].splitlines()), 10, msg=data["name"])

		template = (PACKAGE_ROOT / "templates" / "print_format" / "sa_commercial_document.html").read_text()
		self.assertIn("{% if address %}", template)
		self.assertNotIn("amount > 5000", template)

	def test_vat201_doctype_supports_submit_cancel_and_amend(self):
		path = PACKAGE_ROOT / "sa_vat" / "doctype" / "vat201_return" / "vat201_return.json"
		data = json.loads(path.read_text())
		self.assertEqual(1, data["is_submittable"])
		for role in ("System Manager", "Accounts Manager"):
			permissions = next(row for row in data["permissions"] if row["role"] == role)
			self.assertEqual(1, permissions["submit"])
			self.assertEqual(1, permissions["cancel"])
			self.assertEqual(1, permissions["amend"])

	def test_customer_vat_validation_uses_explicit_vendor_flag(self):
		with patch("za_local_core.custom.customer.validate_sa_vat_number") as validate_number:
			validate_customer(SimpleNamespace(tax_id="4123456789", za_is_vat_vendor=0), None)
			validate_number.assert_not_called()
			validate_customer(SimpleNamespace(tax_id="4123456789", za_is_vat_vendor=1), None)
			validate_number.assert_called_once()

	def test_fresh_install_creates_company_vat_registration_field(self):
		with patch("za_local_core.sa_vat.setup.create_custom_fields") as create_fields:
			ensure_vat_custom_fields()

		definitions = create_fields.call_args.args[0]
		company_fields = {field["fieldname"]: field for field in definitions["Company"]}
		self.assertIn("za_vat_number", company_fields)
		self.assertEqual("Data", company_fields["za_vat_number"]["fieldtype"])


if __name__ == "__main__":
	unittest.main()
