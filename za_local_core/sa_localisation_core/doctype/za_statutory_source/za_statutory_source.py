import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime


class ZAStatutorySource(Document):
	def validate(self) -> None:
		self.sha256_checksum = (self.sha256_checksum or "").strip().lower()
		if not re.fullmatch(r"[0-9a-f]{64}", self.sha256_checksum):
			frappe.throw(_("SHA-256 Checksum must contain exactly 64 hexadecimal characters."))
		if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
			frappe.throw(_("Effective To cannot be before Effective From."))
		if not self.source_url and not self.source_file:
			frappe.throw(_("Provide an Official Source URL or Retrieved Source File."))

	def before_submit(self) -> None:
		if not self.reviewed_by:
			frappe.throw(_("Reviewed By is required before approving a statutory source."))
		if self.reviewed_by == self.owner:
			frappe.throw(_("The statutory source reviewer must differ from its creator."))
		self.status = "Approved"
		self.approved_on = now_datetime()

	def on_cancel(self) -> None:
		self.db_set("status", "Cancelled", update_modified=False)
