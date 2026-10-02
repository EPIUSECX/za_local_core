import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate, now_datetime

from za_local_core.governance import REVIEW_ROLES, canonical_sha256, validate_accountable_actor

NUMERIC_UNITS = frozenset({"Amount", "Percentage", "Count", "Hours", "Days"})
MAX_RATE_PRECISION = 9


class ZAStatutoryRatePack(Document):
	def validate(self) -> None:
		self._validate_dates()
		self._validate_items()
		self._validate_no_overlap()
		self.content_sha256 = self._calculate_content_sha256()

	def before_submit(self) -> None:
		if frappe.db.get_value("ZA Statutory Source", self.source, "docstatus") != 1:
			frappe.throw(
				_("Statutory Source {0} must be approved before this rate pack.").format(self.source)
			)
		self._validate_within_source_window()
		validate_accountable_actor(self, "reviewed_by", REVIEW_ROLES, "approve")
		self.status = "Approved"
		self.approved_on = now_datetime()

	def on_cancel(self) -> None:
		self.db_set("status", "Cancelled", update_modified=False)

	def before_cancel(self) -> None:
		validate_accountable_actor(self, "reviewed_by", REVIEW_ROLES, "cancel")

	def _validate_dates(self) -> None:
		if getdate(self.effective_to) < getdate(self.effective_from):
			frappe.throw(_("Effective To cannot be before Effective From."))
		self._validate_within_source_window()

	def _validate_within_source_window(self) -> None:
		"""GOV-3: a pack cannot apply a source before, or after, the source itself is in force."""
		if not self.source:
			return
		source = frappe.db.get_value(
			"ZA Statutory Source", self.source, ["effective_from", "effective_to"], as_dict=True
		)
		if not source:
			return
		if source.effective_from and getdate(self.effective_from) < getdate(source.effective_from):
			frappe.throw(
				_("Effective From {0} is before Statutory Source {1} takes effect on {2}.").format(
					self.effective_from, self.source, source.effective_from
				)
			)
		if source.effective_to and getdate(self.effective_to) > getdate(source.effective_to):
			frappe.throw(
				_("Effective To {0} is after Statutory Source {1} ceases on {2}.").format(
					self.effective_to, self.source, source.effective_to
				)
			)

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
			if row.unit in NUMERIC_UNITS:
				if row.get("numeric_value") is None:
					frappe.throw(_("Numeric Value is required for rule {0}.").format(key))
				precision = cint(row.precision)
				if precision < 0 or precision > MAX_RATE_PRECISION:
					frappe.throw(
						_("Display Precision for rule {0} must be between 0 and {1}.").format(
							key, MAX_RATE_PRECISION
						)
					)
				row.precision = precision
				row.numeric_value = flt(row.numeric_value, precision)
				if row.text_value:
					frappe.throw(_("Text Value is not allowed for numeric rule {0}.").format(key))

	def _calculate_content_sha256(self) -> str:
		return canonical_sha256(
			{
				"domain": self.domain,
				"effective_from": str(self.effective_from),
				"effective_to": str(self.effective_to),
				"items": [
					{
						"numeric_value": row.numeric_value if row.unit in NUMERIC_UNITS else None,
						"precision": row.precision,
						"rule_key": row.rule_key,
						"text_value": row.text_value if row.unit == "Text" else None,
						"unit": row.unit,
					}
					for row in sorted(self.items, key=lambda item: item.rule_key)
				],
				"source": self.source,
			}
		)

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
