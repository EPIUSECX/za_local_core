import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class ZAComplianceCalendarEntry(Document):
	def before_naming(self) -> None:
		self._set_calendar_key()

	def validate(self) -> None:
		if getdate(self.period_end) < getdate(self.period_start):
			frappe.throw(_("Period End cannot be before Period Start."))
		self._set_calendar_key()

	def _set_calendar_key(self) -> None:
		if self.company and self.obligation and self.period_start and self.period_end:
			self.calendar_key = "|".join(
				(self.company, self.obligation, str(self.period_start), str(self.period_end))
			)
