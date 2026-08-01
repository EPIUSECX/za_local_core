import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class ZAComplianceObligation(Document):
	def validate(self) -> None:
		self.obligation_code = (self.obligation_code or "").strip().upper()
		if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
			frappe.throw(_("Effective To cannot be before Effective From."))

	def before_submit(self) -> None:
		if frappe.db.get_value("ZA Statutory Source", self.source, "docstatus") != 1:
			frappe.throw(_("The linked statutory source must be approved before this obligation."))
