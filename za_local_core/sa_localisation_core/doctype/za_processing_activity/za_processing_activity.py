import frappe
from frappe import _

from za_local_core.sa_localisation_core.doctype._privacy import ReviewedPrivacyDocument


class ZAProcessingActivity(ReviewedPrivacyDocument):
	date_pairs = (("last_reviewed_on", "next_review_date"),)
	required_evidence_fields = ("risk_assessment", "approval_evidence")

	def validate(self) -> None:
		super().validate()
		self._validate_retention_schedule()
		self._validate_cross_border_transfer()

	def _validate_retention_schedule(self) -> None:
		if not self.retention_schedule:
			return
		self._validate_linked_company(
			"ZA Retention Schedule", self.retention_schedule, _("Retention Schedule")
		)
		if frappe.db.get_value("ZA Retention Schedule", self.retention_schedule, "docstatus") != 1:
			frappe.throw(_("Retention Schedule must be approved."))

	def _validate_cross_border_transfer(self) -> None:
		if not self.cross_border_transfer:
			self.cross_border_transfer_record = None
			return
		if not self.cross_border_transfer_record:
			frappe.throw(_("Cross-border Transfer Record is required for cross-border processing."))
		self._validate_linked_company(
			"ZA Cross Border Transfer",
			self.cross_border_transfer_record,
			_("Cross-border Transfer Record"),
		)
		if (
			frappe.db.get_value("ZA Cross Border Transfer", self.cross_border_transfer_record, "docstatus")
			!= 1
		):
			frappe.throw(_("Cross-border Transfer Record must be approved."))
