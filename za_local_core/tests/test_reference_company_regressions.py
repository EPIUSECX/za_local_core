"""Regressions found by the reference-company end-to-end validation.

Each test reproduces a defect observed on the synthetic reference company and
pins the fix: VAT-ISO-1, VAT201-ISO-1, VAT-5, VAT-6.
"""

from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.classes import IntegrationTestCase

from za_local_core.localisation import COUNTRY
from za_local_core.sa_localisation_core.doctype.za_filing.za_filing import ZAFiling
from za_local_core.sa_vat.doctype.vat201_return.vat201_return import VAT201Return
from za_local_core.tests.utils import ensure_company, ensure_south_african_company

FOREIGN_COMPANY = "_ZA Regression UK Company"


class TestReferenceCompanyRegressions(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.za_company = ensure_south_african_company()
		cls.foreign_company = ensure_company(FOREIGN_COMPANY, "_ZRUK", "United Kingdom", "GBP")

	def test_vat_override_keeps_erpnext_item_tax_semantics_outside_south_africa(self):
		"""VAT-ISO-1: a UK 5% reduced-rate item on a 20% row was taxed at nil.

		Non-South African invoices must use ERPNext's own calculation, never the ZA subclass.
		"""
		doc = frappe.new_doc("Sales Invoice")
		doc.company = self.foreign_company
		with (
			patch("za_local_core.sa_vat.vat_tax_calculation.ZACalculateTaxesAndTotals") as za_calc,
			patch("erpnext.controllers.taxes_and_totals.calculate_taxes_and_totals") as base_calc,
		):
			doc.calculate_taxes_and_totals()
		za_calc.assert_not_called()
		base_calc.assert_called_once()

	def test_vat_override_applies_to_south_african_company(self):
		doc = frappe.new_doc("Sales Invoice")
		doc.company = self.za_company
		with (
			patch("za_local_core.sa_vat.vat_tax_calculation.ZACalculateTaxesAndTotals") as za_calc,
			patch.object(type(doc), "calculate_commission"),
			patch.object(type(doc), "calculate_contribution"),
		):
			doc.calculate_taxes_and_totals()
		za_calc.assert_called_once_with(doc)

	def test_za_rate_matching_rule_is_unchanged(self):
		"""Same account, 15% and 0% rows: each row only takes items at its own rate."""
		from za_local_core.sa_vat.vat_tax_calculation import ZACalculateTaxesAndTotals

		calc = ZACalculateTaxesAndTotals.__new__(ZACalculateTaxesAndTotals)
		row = SimpleNamespace(account_head="VAT", rate=15)
		self.assertEqual(15, calc._get_tax_rate(row, {"VAT": 15}))
		self.assertEqual(0, calc._get_tax_rate(row, {"VAT": 0}))
		self.assertEqual(15, calc._get_tax_rate(row, {}))

	def test_vat201_rejects_foreign_company(self):
		"""VAT201-ISO-1: a VAT201 working paper was saved for a UK company."""
		doc = frappe.get_doc({"doctype": "VAT201 Return", "company": self.foreign_company})
		with self.assertRaisesRegex(frappe.ValidationError, "Country set to South Africa"):
			doc.validate_company_scope()

	def test_vat201_rejects_south_african_company_without_vat_number(self):
		doc = frappe.get_doc({"doctype": "VAT201 Return", "company": self.za_company})
		with patch.object(frappe.db, "get_value", side_effect=_company_values(COUNTRY, "")):
			with self.assertRaisesRegex(frappe.ValidationError, "no VAT Registration Number"):
				doc.validate_company_scope()
		with patch.object(frappe.db, "get_value", side_effect=_company_values(COUNTRY, "4900000017")):
			doc.validate_company_scope()

	def test_vat201_journal_rows_exclude_cancelled_entries(self):
		"""VAT-5: cancelled journals and their reversals were pulled into the return and failed to link."""
		doc = frappe.get_doc(
			{
				"doctype": "VAT201 Return",
				"company": self.za_company,
				"from_date": "2026-09-01",
				"to_date": "2026-10-31",
			}
		)
		calls = []

		def fake_get_all(doctype, **kwargs):
			calls.append((doctype, kwargs))
			return []

		settings = SimpleNamespace(vat_accounts=[SimpleNamespace(account="_Regression VAT")])
		with patch("frappe.get_all", side_effect=fake_get_all):
			VAT201Return.get_journal_entry_rows(doc, settings)
		gl_filters = next(kwargs["filters"] for doctype, kwargs in calls if doctype == "GL Entry")
		self.assertEqual(0, gl_filters["is_cancelled"])

	def test_cancelled_filing_releases_its_period_key(self):
		"""VAT-6: a cancelled ZA Filing kept its unique key, so the amended VAT201 could not file."""
		doc = frappe.new_doc("ZA Filing")
		with patch.object(ZAFiling, "db_set") as db_set:
			doc.on_cancel()
		values = db_set.call_args.args[0]
		self.assertEqual("Cancelled", values["status"])
		self.assertIsNone(values["filing_key"])

	def test_patch_releases_keys_of_previously_cancelled_filings(self):
		from za_local_core.patches.v1_5 import release_cancelled_filing_keys

		with patch.object(frappe.db, "sql") as sql:
			release_cancelled_filing_keys.execute()
		statement = sql.call_args.args[0]
		self.assertIn("docstatus = 2", statement)
		self.assertIn("filing_key = null", statement)


def _company_values(country, vat_number):
	def get_value(doctype, name=None, fieldname=None, *args, **kwargs):
		if doctype == "Company" and fieldname == "country":
			return country
		if doctype == "Company" and fieldname == "za_vat_number":
			return vat_number
		return None

	return get_value


class TestVATDocumentRegressions(IntegrationTestCase):
	"""Second validation round: VAT-4, VAT-1/VAT-10, VAT-8."""

	def test_exempt_only_invoice_is_not_a_tax_invoice(self):
		"""VAT-4: an exempt residential letting was printed "FULL TAX INVOICE"."""
		from za_local_core.sa_vat.statutory import FULL_INVOICE_THRESHOLD, NO_INVOICE_THRESHOLD
		from za_local_core.sa_vat.tax_invoice import build_sales_invoice_print_profile, is_exempt_only_invoice

		controls = {
			"values": {NO_INVOICE_THRESHOLD: 50, FULL_INVOICE_THRESHOLD: 5000},
			"source": "S",
			"source_sha256": "x",
			"rate_pack": "P",
			"rate_pack_sha256": "y",
			"effective_from": "2026-04-01",
			"effective_to": None,
		}
		profile = build_sales_invoice_print_profile(
			company=None,
			posting_date="2026-08-01",
			base_grand_total=8_000,
			is_exempt_only=1,
			company_currency="ZAR",
			statutory_controls=controls,
		)
		self.assertEqual("exempt_supply_invoice", profile["invoice_type"])
		self.assertIsNone(profile["print_format"])
		exempt = SimpleNamespace(
			total_taxes_and_charges=0, items=[frappe._dict(custom_sa_vat_category="Exempt")]
		)
		mixed = SimpleNamespace(
			total_taxes_and_charges=0,
			items=[
				frappe._dict(custom_sa_vat_category="Exempt"),
				frappe._dict(custom_sa_vat_category="Zero Rated"),
			],
		)
		self.assertTrue(is_exempt_only_invoice(exempt))
		self.assertFalse(is_exempt_only_invoice(mixed))

	def test_vat_credit_note_requires_a_reason(self):
		"""VAT-1/VAT-10: credit notes carried no section 21(3) explanation."""
		from za_local_core.overrides.vat_invoices import ZASalesInvoice

		doc = frappe._dict(is_return=1, company="ZA Co", za_adjustment_reason="")
		with (
			patch("za_local_core.overrides.vat_invoices.is_south_african_company", return_value=True),
			patch("frappe.db.get_value", return_value="4900000017"),
		):
			with self.assertRaisesRegex(frappe.ValidationError, "Reason for Adjustment"):
				ZASalesInvoice.validate_sa_credit_note_particulars(doc)
			doc.za_adjustment_reason = "Two days of the service were not delivered."
			ZASalesInvoice.validate_sa_credit_note_particulars(doc)

	def test_blocked_input_vat_may_not_reach_the_input_vat_account(self):
		"""VAT-8: blocked entertainment VAT sat in Input VAT and left an unexplained R300."""
		from za_local_core.overrides.vat_invoices import ZAPurchaseInvoice

		accounts = frappe._dict(
			input_vat_account="Input VAT - ZA",
			capital_input_vat_account="Capital VAT - ZA",
			import_input_vat_account=None,
		)

		def validate(taxes):
			doc = frappe._dict(
				company="ZA Co", items=[frappe._dict(za_vat_input_treatment="Blocked")], taxes=taxes
			)
			with (
				patch("za_local_core.overrides.vat_invoices.is_south_african_company", return_value=True),
				patch("frappe.db.get_value", side_effect=["VAT-SET", accounts]),
			):
				ZAPurchaseInvoice.validate_blocked_input_vat(doc)

		for account in ("Input VAT - ZA", "Capital VAT - ZA"):
			with self.assertRaisesRegex(frappe.ValidationError, "Blocked"):
				validate([frappe._dict(account_head=account, tax_amount=300)])
		validate([])


class TestDataSubjectRequestDeadline(IntegrationTestCase):
	"""PRIV-1: the PAIA due date was typed by hand and nothing flagged a late request."""

	def _request(self, **values):
		doc = frappe.new_doc("ZA Data Subject Request")
		doc.update({"received_on": "2026-01-05", "status": "Received", **values})
		return doc

	def test_due_date_defaults_to_thirty_days_after_receipt(self):
		doc = self._request()
		doc._set_statutory_due_date()
		self.assertEqual("2026-02-04", str(doc.due_date))
		self.assertEqual(1, doc.is_overdue)

	def test_due_date_beyond_thirty_days_needs_an_extension(self):
		doc = self._request(due_date="2026-02-20")
		with self.assertRaisesRegex(frappe.ValidationError, "30 days after receipt"):
			doc._set_statutory_due_date()
		doc.extension_reason = "Records held at an off-site archive"
		doc._set_statutory_due_date()
		with self.assertRaises(frappe.ValidationError):
			self._request(due_date="2026-03-10", extension_reason="x")._set_statutory_due_date()

	def test_closed_requests_are_never_overdue(self):
		doc = self._request(status="Closed")
		doc._set_statutory_due_date()
		self.assertEqual(0, doc.is_overdue)

	def test_daily_task_refreshes_overdue_flags(self):
		from za_local_core import tasks

		with (
			patch.object(tasks, "mark_overdue_entries", return_value=0),
			patch(
				"za_local_core.sa_localisation_core.doctype.za_data_subject_request."
				"za_data_subject_request.refresh_overdue_requests"
			) as refresh,
		):
			tasks.daily()
		refresh.assert_called_once()


class TestFeatureReadinessApproval(IntegrationTestCase):
	"""GOV-2: a manager could set Production directly, with no evidence or second person."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from za_local_core.tests.test_governance_lifecycle import TestGovernanceLifecycle

		cls.company = ensure_south_african_company()
		cls.proposer = TestGovernanceLifecycle._ensure_user(
			"_test.za.readiness.proposer@example.com", "Readiness Proposer", "ZA Compliance Manager"
		)
		cls.approver = TestGovernanceLifecycle._ensure_user(
			"_test.za.readiness.approver@example.com", "Readiness Approver", "ZA Compliance Manager"
		)

	def _feature(self, code, status="Preview"):
		return frappe.get_doc(
			{
				"doctype": "ZA Feature Readiness",
				"company": self.company,
				"feature_code": code,
				"feature_name": code,
				"domain": "Core",
				"status": status,
				"blocking_reason": "_Test limitation",
			}
		)

	def test_production_cannot_be_declared_directly(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Production directly"):
			self._feature("_TEST-GOV2-NEW", "Production").insert(ignore_permissions=True)
		doc = self._feature("_TEST-GOV2-RAISE").insert(ignore_permissions=True)
		doc.status = "Controlled Manual"
		with self.assertRaisesRegex(frappe.ValidationError, "needs approval"):
			doc.save(ignore_permissions=True)
		doc.reload()
		doc.status = "Blocked"
		doc.save(ignore_permissions=True)
		self.assertEqual("Blocked", doc.reload().status)

	def test_raise_needs_private_evidence_and_an_independent_approver(self):
		from frappe.utils.file_manager import save_file

		doc = self._feature("_TEST-GOV2-APPROVE").insert(ignore_permissions=True)
		with self.set_user(self.proposer):
			doc = frappe.get_doc("ZA Feature Readiness", doc.name)
			doc.proposed_status = "Controlled Manual"
			doc.approver = self.proposer
			doc.save()
			with self.assertRaisesRegex(frappe.ValidationError, "Approval Evidence"):
				doc.approve_proposed_status()
			doc.approval_evidence = save_file(
				"_test-gov2.txt", b"parallel run sign-off", doc.doctype, doc.name, is_private=1
			).file_url
			doc.save()
			with self.assertRaises(frappe.PermissionError):
				frappe.get_doc("ZA Feature Readiness", doc.name).approve_proposed_status()
			doc.approver = self.approver
			doc.save()
		with self.set_user(self.approver):
			frappe.get_doc("ZA Feature Readiness", doc.name).approve_proposed_status()
		doc.reload()
		self.assertEqual(
			("Controlled Manual", self.approver, None), (doc.status, doc.approved_by, doc.proposed_status)
		)


class TestRatePackSourceWindow(IntegrationTestCase):
	"""GOV-3: a rate pack's effective window was not checked against its source's dates."""

	SOURCE_MODULE = "za_local_core.sa_localisation_core.doctype.za_statutory_rate_pack.za_statutory_rate_pack"

	def _check(self, effective_from, effective_to, source):
		doc = frappe.new_doc("ZA Statutory Rate Pack")
		doc.update({"source": "SRC", "effective_from": effective_from, "effective_to": effective_to})
		with patch(f"{self.SOURCE_MODULE}.frappe.db.get_value", return_value=frappe._dict(source)):
			doc._validate_dates()

	def test_pack_must_sit_inside_the_source_window(self):
		source = {"effective_from": "2026-03-01", "effective_to": "2027-02-28"}
		self._check("2026-03-01", "2027-02-28", source)
		with self.assertRaisesRegex(frappe.ValidationError, "before Statutory Source"):
			self._check("2026-02-01", "2027-02-28", source)
		with self.assertRaisesRegex(frappe.ValidationError, "after Statutory Source"):
			self._check("2026-03-01", "2027-03-31", source)

	def test_open_ended_source_allows_any_later_end(self):
		self._check("2026-04-01", "2030-02-28", {"effective_from": "2026-03-01", "effective_to": None})


class TestFilingDifferenceExplanation(IntegrationTestCase):
	"""GOV-7: any text in Notes satisfied "explain the reconciliation difference"."""

	def _filing(self, **values):
		doc = frappe.new_doc("ZA Filing")
		doc.update({"currency": "ZAR", "declared_amount": 1300, "ledger_amount": 1000, **values})
		doc.unexplained_difference = doc.declared_amount - doc.ledger_amount
		return doc

	def test_notes_no_longer_explain_a_difference(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Difference Explanation"):
			self._filing(notes="ok")._validate_difference_explanation()
		with self.assertRaisesRegex(frappe.ValidationError, "at least 30"):
			self._filing(difference_explanation="see file")._validate_difference_explanation()
		self._filing(
			difference_explanation="R300 blocked input VAT on entertainment, journalled to expense on 31 August."
		)._validate_difference_explanation()

	def test_explanation_is_part_of_what_the_reviewer_saw(self):
		doc = self._filing(difference_explanation="first explanation of the R300 difference in full")
		before = doc._calculate_review_checksum()
		doc.difference_explanation = "a different explanation of the R300 difference in full"
		self.assertNotEqual(before, doc._calculate_review_checksum())

	def test_no_explanation_needed_without_a_difference(self):
		self._filing(declared_amount=1000)._validate_difference_explanation()


class TestSeparateInputVatLedgers(IntegrationTestCase):
	"""VAT-2: capital-goods and import VAT kept in their own accounts were ignored by VAT201."""

	def _settings(self, **values):
		return frappe._dict(
			{
				"input_vat_account": "VAT Input",
				"output_vat_account": "VAT Output",
				"capital_input_vat_account": None,
				"import_input_vat_account": None,
				**values,
			}
		)

	def test_all_input_ledgers_are_read_and_templates_post_to_them(self):
		from za_local_core.sa_vat.setup import get_input_vat_accounts, get_purchase_template_account

		settings = self._settings(
			capital_input_vat_account="VAT Capital", import_input_vat_account="VAT Import"
		)
		self.assertEqual(["VAT Input", "VAT Capital", "VAT Import"], get_input_vat_accounts(settings))
		self.assertEqual("VAT Capital", get_purchase_template_account(settings, "input_capital_local"))
		self.assertEqual("VAT Import", get_purchase_template_account(settings, "input_capital_import"))
		self.assertEqual("VAT Import", get_purchase_template_account(settings, "input_goods_import"))
		self.assertEqual("VAT Input", get_purchase_template_account(settings, "input_goods_local"))
		self.assertEqual("VAT Input", get_purchase_template_account(self._settings(), "input_capital_import"))

	def test_ledger_and_classification_must_agree(self):
		from za_local_core.sa_vat.doctype.vat201_return.vat201_return import (
			INPUT_CAPITAL_LOCAL,
			INPUT_OTHER_LOCAL,
			flag_input_vat_ledger_mismatch,
		)

		settings = self._settings(capital_input_vat_account="VAT Capital")
		on_capital = [frappe._dict(account_head="VAT Capital", tax_amount=150)]
		on_input = [frappe._dict(account_head="VAT Input", tax_amount=150)]

		def row(classification):
			return {
				"classification": classification,
				"classification_status": "Classified",
				"tax_amount": 150,
			}

		agreed = [row(INPUT_CAPITAL_LOCAL)]
		flag_input_vat_ledger_mismatch(agreed, on_capital, settings)
		self.assertEqual("Classified", agreed[0]["classification_status"])
		for rows, taxes in (([row(INPUT_OTHER_LOCAL)], on_capital), ([row(INPUT_CAPITAL_LOCAL)], on_input)):
			flag_input_vat_ledger_mismatch(rows, taxes, settings)
			self.assertEqual("Needs Review", rows[0]["classification_status"])
			self.assertIn("VAT Capital", rows[0]["classification_issue"])

	def test_separate_ledger_cannot_reuse_the_main_accounts(self):
		doc = frappe.new_doc("South Africa VAT Settings")
		doc.update(
			{
				"input_vat_account": "VAT Input",
				"output_vat_account": "VAT Output",
				"capital_input_vat_account": "VAT Input",
			}
		)
		with (
			patch(
				"za_local_core.sa_vat.doctype.south_africa_vat_settings.south_africa_vat_settings.validate_vat_posting_account"
			),
			self.assertRaisesRegex(frappe.ValidationError, "its own ledger account"),
		):
			doc.validate_vat_accounts()

	def test_gl_entries_are_read_from_every_posted_vat_account(self):
		from za_local_core.sa_vat import reconciliation

		with patch.object(reconciliation.frappe, "get_all", return_value=[]) as get_all:
			reconciliation.get_invoice_gl_entries("Purchase Invoice", "PINV-1", ["VAT Input", "VAT Capital"])
		self.assertEqual(["in", ["VAT Input", "VAT Capital"]], get_all.call_args.kwargs["filters"]["account"])


class TestVatTemplateDescriptions(IntegrationTestCase):
	"""VAT-9: the company name printed on every invoice VAT line."""

	def test_template_description_omits_the_company(self):
		from za_local_core.sa_vat import setup

		settings = frappe._dict(
			company="Acme (Pty) Ltd",
			output_vat_account="VAT Output",
			input_vat_account="VAT Input",
			standard_vat_rate=15,
		)
		with (
			patch.object(setup, "validate_vat_posting_account"),
			patch.object(setup, "ensure_item_tax_templates"),
			patch.object(setup, "ensure_tax_template", return_value="T") as ensure,
		):
			setup.ensure_default_tax_templates(settings)
		for call in ensure.call_args_list:
			self.assertIn("Acme (Pty) Ltd", call.kwargs["title"])
			self.assertNotIn("Acme", call.kwargs["description"])
