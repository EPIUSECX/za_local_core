import frappe
from frappe import _
from frappe.utils import cint

from za_local_core.sa_localisation_core.doctype._privacy import ReviewedPrivacyDocument


class ZAOperatorAgreement(ReviewedPrivacyDocument):
	approved_status = "Active"
	date_pairs = (
		("signed_on", "effective_from"),
		("effective_from", "effective_to"),
		("last_assessed_on", "next_assessment_due"),
	)
	required_evidence_fields = ("signed_agreement", "security_assessment")

	def validate(self) -> None:
		super().validate()
		if self.breach_notification_hours is not None and cint(self.breach_notification_hours) <= 0:
			frappe.throw(_("Breach Notification Hours must be greater than zero."))

	def before_submit(self) -> None:
		if not self.signed_agreement:
			frappe.throw(_("Signed Agreement is required."))
		super().before_submit()
