import frappe
from frappe import _
from frappe.utils import cint

from za_local_core.sa_localisation_core.doctype._privacy import OperationalPrivacyDocument


class ZAPersonalInformationIncident(OperationalPrivacyDocument):
	initial_status = "Reported"
	date_pairs = (
		("occurred_from", "occurred_to"),
		("detected_at", "contained_at"),
		("detected_at", "resolved_at"),
	)
	allowed_transitions = {
		"Reported": frozenset({"Triaged"}),
		"Triaged": frozenset({"Contained", "Notification Assessment"}),
		"Contained": frozenset({"Notification Assessment"}),
		"Notification Assessment": frozenset({"Notifying", "Remediating"}),
		"Notifying": frozenset({"Remediating"}),
		"Remediating": frozenset({"Resolved"}),
		"Resolved": frozenset({"Closed"}),
		"Closed": frozenset(),
	}

	def validate(self) -> None:
		super().validate()
		if self.affected_data_subjects is not None and cint(self.affected_data_subjects) < 0:
			frappe.throw(_("Affected Data Subjects cannot be negative."))
		self._validate_containment()
		self._validate_notification_assessment()
		self._validate_notifications()
		if self.status in {"Resolved", "Closed"}:
			self._validate_closure_review("remediation_evidence", "resolved_at")

	def _validate_containment(self) -> None:
		if self.status in {"Contained", "Notification Assessment", "Notifying", "Remediating", "Resolved", "Closed"}:
			if not self.contained_at or not self.containment_evidence:
				frappe.throw(_("Contained At and Containment Evidence are required for this status."))

	def _validate_notification_assessment(self) -> None:
		if self.status not in {"Notification Assessment", "Notifying", "Remediating", "Resolved", "Closed"}:
			return
		if self.notification_decision == "Pending Assessment":
			frappe.throw(_("Complete the Notification Decision before advancing this incident."))
		if not (self.notification_rationale or "").strip() or not self.notification_assessment_evidence:
			frappe.throw(_("Notification Rationale and Notification Assessment Evidence are required."))

	def _validate_notifications(self) -> None:
		if self.status not in {"Remediating", "Resolved", "Closed"}:
			return
		if self.notification_decision in {"Regulator Only", "Regulator and Data Subjects"}:
			if not self.regulator_notified_on or not self.regulator_notification_evidence:
				frappe.throw(_("Information Regulator notification date and evidence are required."))
		if self.notification_decision in {"Data Subjects Only", "Regulator and Data Subjects"}:
			if not self.data_subjects_notified_on or not self.data_subject_notification_evidence:
				frappe.throw(_("Data-subject notification date and evidence are required."))
