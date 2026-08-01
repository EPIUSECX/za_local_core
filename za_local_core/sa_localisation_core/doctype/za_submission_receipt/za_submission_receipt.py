import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class ZASubmissionReceipt(Document):
	def validate(self) -> None:
		self.sha256_checksum = (self.sha256_checksum or "").strip().lower()
		if not re.fullmatch(r"[0-9a-f]{64}", self.sha256_checksum):
			frappe.throw(_("SHA-256 Checksum must contain exactly 64 hexadecimal characters."))

	def before_submit(self) -> None:
		filing = frappe.get_doc("ZA Filing", self.filing)
		if filing.docstatus != 1 or filing.status not in ("Approved", "Filed", "Rejected"):
			frappe.throw(_("Filing {0} must be approved before recording a receipt.").format(self.filing))
		if flt(filing.declared_amount, 2) != flt(self.declared_amount, 2):
			frappe.throw(_("Receipt amount must match the approved filing amount."))

	def on_submit(self) -> None:
		frappe.db.set_value("ZA Filing", self.filing, "status", self.response_status, update_modified=False)

	def on_cancel(self) -> None:
		frappe.db.set_value("ZA Filing", self.filing, "status", "Approved", update_modified=False)
