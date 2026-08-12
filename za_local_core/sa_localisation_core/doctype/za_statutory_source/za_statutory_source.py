import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime

from za_local_core.governance import (
	REVIEW_ROLES,
	stamp_evidence_checksum,
	validate_accountable_actor,
	validate_private_evidence,
)


class ZAStatutorySource(Document):
	def validate(self) -> None:
		stamp_evidence_checksum(self, "source_file", "sha256_checksum")
		if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
			frappe.throw(_("Effective To cannot be before Effective From."))
		if not self.source_url and not self.source_file:
			frappe.throw(_("Provide an Official Source URL or Retrieved Source File."))

	def before_submit(self) -> None:
		if not self.sha256_checksum:
			frappe.throw(_("SHA-256 Checksum is required before approval."))
		validate_accountable_actor(self, "reviewed_by", REVIEW_ROLES, "approve")
		validate_private_evidence(self, "source_file", checksum_field="sha256_checksum", required=True)
		self.status = "Approved"
		self.approved_on = now_datetime()

	def on_cancel(self) -> None:
		self.db_set("status", "Cancelled", update_modified=False)

	def before_cancel(self) -> None:
		validate_accountable_actor(self, "reviewed_by", REVIEW_ROLES, "cancel")
