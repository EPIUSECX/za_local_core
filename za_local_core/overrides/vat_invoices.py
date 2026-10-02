"""Extend invoice controllers to use ZA VAT tax calculation."""

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


class ZAPurchaseInvoice:
	"""Purchase Invoice extension using ZA VAT tax calculation."""

	def calculate_taxes_and_totals(self):
		if not is_south_african_company(self.get("company")):
			return super().calculate_taxes_and_totals()

		from za_local_core.sa_vat.vat_tax_calculation import ZACalculateTaxesAndTotals

		ZACalculateTaxesAndTotals(self)
