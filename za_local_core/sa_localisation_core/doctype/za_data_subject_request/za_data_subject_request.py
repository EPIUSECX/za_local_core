from typing import ClassVar

import frappe
from frappe import _

from za_local_core.sa_localisation_core.doctype._privacy import OperationalPrivacyDocument


class ZADataSubjectRequest(OperationalPrivacyDocument):
	initial_status = "Received"
	date_pairs = (("received_on", "due_date"), ("received_on", "completed_on"))
	allowed_transitions: ClassVar[dict[str, frozenset[str]]] = {
		"Received": frozenset({"Identity Verification Pending", "In Progress", "Withdrawn"}),
		"Identity Verification Pending": frozenset({"In Progress", "Refused", "Withdrawn"}),
		"In Progress": frozenset({"Extended", "Fulfilled", "Refused", "Withdrawn"}),
		"Extended": frozenset({"Fulfilled", "Refused", "Withdrawn"}),
		"Fulfilled": frozenset({"Closed"}),
		"Refused": frozenset({"Closed"}),
		"Withdrawn": frozenset({"Closed"}),
		"Closed": frozenset(),
	}

	def validate(self) -> None:
		super().validate()
		self._validate_identity_control()
		self._validate_extension()
		self._validate_terminal_status()

	def _validate_identity_control(self) -> None:
		if self.status not in {"In Progress", "Extended", "Fulfilled"}:
			return
		if not self.identity_verified_on or not self.identity_verification_evidence:
			frappe.throw(
				_(
					"Identity Verified On and Identity Verification Evidence are required before processing or disclosure."
				)
			)

	def _validate_extension(self) -> None:
		if self.status != "Extended":
			return
		if not (self.extension_reason or "").strip() or not self.extension_evidence:
			frappe.throw(_("Extension Reason and Extension Evidence are required for an extended request."))

	def _validate_terminal_status(self) -> None:
		if self.status not in {"Fulfilled", "Refused", "Withdrawn", "Closed"}:
			return
		if self.status == "Refused" and not (self.refusal_reason or "").strip():
			frappe.throw(_("Refusal Reason is required for a refused request."))
		self._validate_closure_review("final_response_evidence", "completed_on")
