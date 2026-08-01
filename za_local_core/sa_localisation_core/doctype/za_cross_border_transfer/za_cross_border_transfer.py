import frappe
from frappe import _

from za_local_core.sa_localisation_core.doctype._privacy import ReviewedPrivacyDocument


class ZACrossBorderTransfer(ReviewedPrivacyDocument):
	date_pairs = (("assessment_date", "next_review_date"), ("effective_from", "effective_to"))
	required_evidence_fields = ("transfer_assessment", "safeguard_evidence")

	def validate(self) -> None:
		super().validate()
		if self.destination_country == "South Africa":
			frappe.throw(_("Destination Country must be outside South Africa."))
		if self.transfer_ground == "Consent" and not self.consent_evidence:
			frappe.throw(_("Consent Evidence is required when Transfer Ground is Consent."))

	def before_submit(self) -> None:
		if not self.transfer_assessment:
			frappe.throw(_("Transfer Assessment is required."))
		super().before_submit()
