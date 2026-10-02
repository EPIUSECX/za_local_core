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
