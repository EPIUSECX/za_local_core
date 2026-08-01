import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class ZAStatutoryChangeReview(Document):
	def before_submit(self) -> None:
		if self.practitioner_reviewer == self.technical_reviewer:
			frappe.throw(_("Practitioner Reviewer and Technical Reviewer must be different users."))
		if frappe.db.get_value("ZA Statutory Source", self.source, "docstatus") != 1:
			frappe.throw(_("The linked statutory source must be approved before this review."))
		self.status = "Approved"
		self.approved_on = now_datetime()

	def on_cancel(self) -> None:
		self.db_set("status", "Cancelled", update_modified=False)
