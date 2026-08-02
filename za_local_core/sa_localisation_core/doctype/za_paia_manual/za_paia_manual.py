import frappe
from frappe import _

from za_local_core.sa_localisation_core.doctype._privacy import ReviewedPrivacyDocument


class ZAPAIAManual(ReviewedPrivacyDocument):
	approved_status = "Published"
	date_pairs = (
		("published_on", "effective_from"),
		("effective_from", "effective_to"),
		("last_reviewed_on", "next_review_due"),
	)
	required_evidence_fields = ("manual_file", "publication_evidence")

	def validate(self) -> None:
		super().validate()
		if not self.information_officer_registration:
			return
		self._validate_linked_company(
			"ZA Information Officer Registration",
			self.information_officer_registration,
			_("Information Officer Registration"),
		)
		if (
			frappe.db.get_value(
				"ZA Information Officer Registration", self.information_officer_registration, "docstatus"
			)
			!= 1
		):
			frappe.throw(_("Information Officer Registration must be active and approved."))

	def before_submit(self) -> None:
		if not self.manual_file or not self.publication_evidence:
			frappe.throw(_("Published Manual and Publication Evidence are required."))
		super().before_submit()
