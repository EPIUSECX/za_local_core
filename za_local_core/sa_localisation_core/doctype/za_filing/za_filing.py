import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, now_datetime


class ZAFiling(Document):
	def validate(self) -> None:
		if getdate(self.period_end) < getdate(self.period_start):
			frappe.throw(_("Period End cannot be before Period Start."))
		self.filing_key = "|".join((self.company, self.obligation, str(self.period_start), str(self.period_end)))
		self.capability = frappe.db.get_value("ZA Compliance Obligation", self.obligation, "capability")
		self.unexplained_difference = flt(self.declared_amount) - flt(self.ledger_amount)

	def before_submit(self) -> None:
		if frappe.db.get_value("ZA Compliance Obligation", self.obligation, "docstatus") != 1:
			frappe.throw(_("Compliance Obligation {0} must be approved.").format(self.obligation))
		if self.reviewed_by == self.approved_by:
			frappe.throw(_("Reviewed By and Approved By must be different users."))
		if self.owner in (self.reviewed_by, self.approved_by):
			frappe.throw(_("The filing creator cannot review or approve the same filing."))
		if flt(self.unexplained_difference, 2) and not (self.notes or "").strip():
			frappe.throw(_("Explain the reconciliation difference before approving this filing."))
		if self.capability == "Unsupported":
			frappe.throw(_("Unsupported obligations cannot be approved for filing."))
		self.status = "Approved"
		self.approved_on = now_datetime()

	def on_cancel(self) -> None:
		self.db_set("status", "Cancelled", update_modified=False)
