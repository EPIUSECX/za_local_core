import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from za_local_core.governance import (
	APPROVAL_ROLES,
	stamp_evidence_checksum,
	validate_accountable_actor,
	validate_private_evidence,
)


class ZASubmissionReceipt(Document):
	def validate(self) -> None:
		stamp_evidence_checksum(self, "evidence_file", "sha256_checksum")

	def before_submit(self) -> None:
		validate_accountable_actor(self, "submitted_by", APPROVAL_ROLES, "record the external response")
		validate_private_evidence(self, "evidence_file", checksum_field="sha256_checksum", required=True)
		filing = frappe.get_doc("ZA Filing", self.filing)
		if filing.docstatus != 1 or filing.status not in ("Approved", "Filed", "Rejected"):
			frappe.throw(_("Filing {0} must be approved before recording a receipt.").format(self.filing))
		if flt(filing.declared_amount, 2) != flt(self.declared_amount, 2):
			frappe.throw(_("Receipt amount must match the approved filing amount."))

	def on_submit(self) -> None:
		frappe.db.set_value("ZA Filing", self.filing, "status", self.response_status, update_modified=False)

	def on_cancel(self) -> None:
		frappe.db.set_value("ZA Filing", self.filing, "status", "Approved", update_modified=False)

	def before_cancel(self) -> None:
		validate_accountable_actor(self, "submitted_by", APPROVAL_ROLES, "cancel the external response")
