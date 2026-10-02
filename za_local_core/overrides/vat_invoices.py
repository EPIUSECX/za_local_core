"""Extend invoice controllers to use ZA VAT tax calculation."""

import frappe
from frappe import _
from frappe.utils import flt

from za_local_core.localisation import is_south_african_company


class ZASalesInvoice:
	"""Sales Invoice extension using ZA VAT tax calculation."""

	def calculate_taxes_and_totals(self):
		# Other countries keep ERPNext item-tax-template semantics (item rate replaces row rate).
		if not is_south_african_company(self.get("company")):
			return super().calculate_taxes_and_totals()

		from za_local_core.sa_vat.vat_tax_calculation import ZACalculateTaxesAndTotals

		ZACalculateTaxesAndTotals(self)

		if self.doctype in (
			"Sales Order",
			"Delivery Note",
			"Sales Invoice",
			"POS Invoice",
		):
			self.calculate_commission()
			self.calculate_contribution()

	def before_submit(self):
		parent = getattr(super(), "before_submit", None)
		if parent:
			parent()
		self.validate_sa_credit_note_particulars()

	def validate_sa_credit_note_particulars(self):
		"""Section 21(3): a VAT vendor's credit note states why it was issued."""
		if not self.get("is_return") or not is_south_african_company(self.get("company")):
			return
		if not frappe.db.get_value("Company", self.company, "za_vat_number"):
			return
		if not (self.get("za_adjustment_reason") or "").strip():
			frappe.throw(
				_(
					"Enter the Reason for Adjustment: a VAT credit note must briefly explain why it was issued."
				),
				title=_("Credit Note Reason Required"),
			)


class ZAPurchaseInvoice:
	"""Purchase Invoice extension using ZA VAT tax calculation."""

	def validate(self):
		super().validate()
		self.validate_blocked_input_vat()

	def validate_blocked_input_vat(self):
		"""Blocked input tax (section 17(2)) must not reach the Input VAT account.

		VAT201 rightly excludes blocked input tax, so tax posted to the control
		account for a blocked line leaves an unexplained difference between the
		ledger and the return. The VAT stays part of the cost of the expense.
		"""
		if not is_south_african_company(self.get("company")):
			return
		if not any(
			(item.get("za_vat_input_treatment") or "") == "Blocked" for item in self.get("items") or []
		):
			return
		settings_name = frappe.db.get_value("South Africa VAT Settings", {"company": self.company}, "name")
		if not settings_name:
			return
		from za_local_core.sa_vat.setup import INPUT_VAT_ACCOUNT_FIELDS

		input_accounts = set(
			frappe.db.get_value(
				"South Africa VAT Settings", settings_name, list(INPUT_VAT_ACCOUNT_FIELDS), as_dict=True
			).values()
		)
		input_accounts.discard(None)
		if any(row.account_head in input_accounts and flt(row.tax_amount) for row in self.get("taxes") or []):
			frappe.throw(
				_(
					"Lines marked Blocked carry input VAT that may not be deducted (section 17(2)). "
					"Remove the input VAT tax template so the VAT stays in the expense, or put the "
					"blocked lines on a separate invoice from deductible purchases."
				),
				title=_("Blocked Input VAT"),
			)

	def calculate_taxes_and_totals(self):
		if not is_south_african_company(self.get("company")):
			return super().calculate_taxes_and_totals()

		from za_local_core.sa_vat.vat_tax_calculation import ZACalculateTaxesAndTotals

		ZACalculateTaxesAndTotals(self)
