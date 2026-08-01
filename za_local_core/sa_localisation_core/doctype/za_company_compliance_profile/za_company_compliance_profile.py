import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime


class ZACompanyComplianceProfile(Document):
	def validate(self) -> None:
		country = frappe.get_cached_value("Company", self.company, "country")
		if country != "South Africa":
			frappe.throw(_("Company {0} must have Country set to South Africa.").format(self.company))
		if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
			frappe.throw(_("Effective To cannot be before Effective From."))

	def mark_reviewed(self) -> None:
		self.reviewed_by = frappe.session.user
		self.reviewed_on = now_datetime()
