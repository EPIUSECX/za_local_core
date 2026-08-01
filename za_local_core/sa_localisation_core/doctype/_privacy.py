from typing import ClassVar

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime


class CompanyScopedPrivacyDocument(Document):
	"""Shared validation for company-scoped POPIA and PAIA records."""

	date_pairs: tuple[tuple[str, str], ...] = ()

	def validate(self) -> None:
		self._validate_company()
		self._validate_date_pairs()

	def _validate_company(self) -> None:
		if not self.company:
			return
		country = frappe.get_cached_value("Company", self.company, "country")
		if country != "South Africa":
			frappe.throw(_("Company {0} must have Country set to South Africa.").format(self.company))

	def _validate_date_pairs(self) -> None:
		for from_field, to_field in self.date_pairs:
			from_date = self.get(from_field)
			to_date = self.get(to_field)
			if from_date and to_date and getdate(to_date) < getdate(from_date):
				frappe.throw(
					_("{0} cannot be before {1}.").format(
						self.meta.get_label(to_field), self.meta.get_label(from_field)
					)
				)

	def _validate_linked_company(self, doctype: str, name: str | None, label: str) -> None:
		if not name:
			return
		linked_company = frappe.db.get_value(doctype, name, "company")
		if linked_company != self.company:
			frappe.throw(_("{0} must belong to Company {1}.").format(label, self.company))


class ReviewedPrivacyDocument(CompanyScopedPrivacyDocument):
	"""Immutable approved record with maker-reviewer separation."""

	approved_status = "Approved"
	cancelled_status = "Cancelled"
	required_evidence_fields: tuple[str, ...] = ()

	def validate(self) -> None:
		super().validate()
		if self.docstatus == 0:
			self.status = "Draft"

	def before_submit(self) -> None:
		self._validate_reviewer()
		self._validate_evidence()
		self.status = self.approved_status
		self.reviewed_on = now_datetime()

	def on_cancel(self) -> None:
		self.db_set("status", self.cancelled_status, update_modified=False)

	def _validate_reviewer(self) -> None:
		if not self.reviewed_by:
			frappe.throw(_("Reviewed By is required before approval."))
		if self.reviewed_by == self.owner:
			frappe.throw(_("The reviewer must differ from the record creator."))
		if self.get("responsible_user") and self.reviewed_by == self.responsible_user:
			frappe.throw(_("The reviewer must differ from the Responsible User."))

	def _validate_evidence(self) -> None:
		if self.required_evidence_fields and not any(
			(self.get(fieldname) or "").strip() for fieldname in self.required_evidence_fields
		):
			labels = ", ".join(self.meta.get_label(fieldname) for fieldname in self.required_evidence_fields)
			frappe.throw(_("Attach at least one approval evidence file: {0}.").format(labels))


class OperationalPrivacyDocument(CompanyScopedPrivacyDocument):
	"""Mutable case record with an explicit, auditable status state machine."""

	allowed_transitions: ClassVar[dict[str, frozenset[str]]] = {}
	initial_status = "Draft"

	def validate(self) -> None:
		super().validate()
		self._validate_status_transition()

	def _validate_status_transition(self) -> None:
		previous = self.get_doc_before_save()
		if not previous:
			if self.status != self.initial_status:
				frappe.throw(_("A new {0} must start in status {1}.").format(self.doctype, self.initial_status))
			return
		if previous.status == self.status:
			return
		allowed = self.allowed_transitions.get(previous.status, frozenset())
		if self.status not in allowed:
			frappe.throw(
				_("Status cannot change from {0} to {1}.").format(previous.status, self.status)
			)

	def _validate_closure_review(self, evidence_field: str, resolution_field: str) -> None:
		if not self.get(resolution_field):
			frappe.throw(_("{0} is required for this status.").format(self.meta.get_label(resolution_field)))
		if not self.get(evidence_field):
			frappe.throw(_("{0} is required for this status.").format(self.meta.get_label(evidence_field)))
		if not self.reviewed_by:
			frappe.throw(_("Reviewed By is required for this status."))
		if self.reviewed_by in {self.owner, self.get("responsible_user")}:
			frappe.throw(_("The closing reviewer must differ from the creator and Responsible User."))
		if not self.reviewed_on:
			self.reviewed_on = now_datetime()
