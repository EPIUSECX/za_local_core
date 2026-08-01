import frappe
from frappe import _
from frappe.utils import cint

from za_local_core.sa_localisation_core.doctype._privacy import ReviewedPrivacyDocument


class ZARetentionSchedule(ReviewedPrivacyDocument):
	date_pairs = (("effective_from", "effective_to"),)
	required_evidence_fields = ("legal_basis_evidence", "approval_evidence")

	def validate(self) -> None:
		super().validate()
		if self.retention_period_value is not None and cint(self.retention_period_value) <= 0:
			frappe.throw(_("Retention Period must be greater than zero."))
		if self.disposal_method == "Other" and not (self.disposal_instructions or "").strip():
			frappe.throw(_("Disposal Instructions are required when Disposal Method is Other."))
