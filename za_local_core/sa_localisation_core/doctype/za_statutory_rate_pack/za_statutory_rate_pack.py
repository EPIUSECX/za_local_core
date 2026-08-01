import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime


class ZAStatutoryRatePack(Document):
	def validate(self) -> None:
		self._validate_dates()
		self._validate_items()
		self._validate_no_overlap()

	def before_submit(self) -> None:
		if frappe.db.get_value("ZA Statutory Source", self.source, "docstatus") != 1:
			frappe.throw(_("Statutory Source {0} must be approved before this rate pack.").format(self.source))
		if not self.reviewed_by:
			frappe.throw(_("Reviewed By is required before approving a statutory rate pack."))
		if self.reviewed_by == self.owner:
			frappe.throw(_("The rate-pack reviewer must differ from its creator."))
		self.status = "Approved"
		self.approved_on = now_datetime()

	def on_cancel(self) -> None:
		self.db_set("status", "Cancelled", update_modified=False)

	def _validate_dates(self) -> None:
		if getdate(self.effective_to) < getdate(self.effective_from):
			frappe.throw(_("Effective To cannot be before Effective From."))

	def _validate_items(self) -> None:
		if not self.items:
			frappe.throw(_("Add at least one statutory rate item."))
		seen = set()
		for row in self.items:
			key = (row.rule_key or "").strip()
			if not key:
				frappe.throw(_("Rule Key is required on every rate item."))
			if key in seen:
				frappe.throw(_("Rule Key {0} is duplicated in the rate pack.").format(key))
			seen.add(key)
			row.rule_key = key
			if row.unit == "Text" and not row.text_value:
				frappe.throw(_("Text Value is required for rule {0}.").format(key))

	def _validate_no_overlap(self) -> None:
		pack = frappe.qb.DocType("ZA Statutory Rate Pack")
		overlap = (
			frappe.qb.from_(pack)
			.select(pack.name)
			.where(pack.name != (self.name or ""))
			.where(pack.domain == self.domain)
			.where(pack.docstatus < 2)
			.where(pack.effective_from <= self.effective_to)
			.where(pack.effective_to >= self.effective_from)
			.limit(1)
		).run(pluck=True)
		if overlap:
			frappe.throw(_("Rate pack overlaps {0} for domain {1}.").format(overlap[0], self.domain))
