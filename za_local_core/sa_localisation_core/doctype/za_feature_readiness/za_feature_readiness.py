import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from za_local_core.governance import (
	APPROVAL_ROLES,
	stamp_evidence_checksum,
	validate_accountable_actor,
	validate_private_evidence,
)

# Lowest to highest readiness. Lowering is always allowed; raising needs approval.
STATUS_RANK = {"Blocked": 0, "Unsupported": 1, "Preview": 2, "Controlled Manual": 3, "Production": 4}


class ZAFeatureReadiness(Document):
	def before_naming(self) -> None:
		self._set_readiness_key()

	def validate(self) -> None:
		self.feature_code = (self.feature_code or "").strip().upper()
		self._set_readiness_key()
		self.checked_by = frappe.session.user
		self.checked_on = now_datetime()
		if (
			self.status in ("Controlled Manual", "Preview", "Unsupported", "Blocked")
			and not (self.blocking_reason or "").strip()
		):
			frappe.throw(_("Blocking Reason or Limitations is required for status {0}.").format(self.status))
		self._validate_status_change()
		stamp_evidence_checksum(self, "approval_evidence", "approval_evidence_sha256")

	def _validate_status_change(self) -> None:
		"""GOV-2: readiness is never raised by the person declaring it."""
		before = self.get_doc_before_save()
		if self.proposed_status and self.has_value_changed("proposed_status"):
			self.proposed_by = frappe.session.user
		if self.flags.readiness_approved:
			return
		if self.is_new() or not before:
			if self.status == "Production":
				frappe.throw(
					_(
						"A feature cannot be recorded as Production directly. Record it at a lower status, "
						"then propose Production with evidence for an independent approver."
					)
				)
			return
		if STATUS_RANK.get(self.status, 0) > STATUS_RANK.get(before.status, 0):
			frappe.throw(
				_(
					"Raising readiness from {0} to {1} needs approval. Set Proposed Status, attach the "
					"evidence and name an Approver, who then approves it."
				).format(before.status, self.status),
				title=_("Readiness Approval Required"),
			)

	@frappe.whitelist(methods=["POST"])
	def approve_proposed_status(self) -> None:
		"""Apply the proposed status as the recorded approver, who is not the proposer."""
		self.check_permission("write")
		if not self.proposed_status:
			frappe.throw(_("There is no proposed status to approve."))
		raising = STATUS_RANK.get(self.proposed_status, 0) > STATUS_RANK.get(self.status, 0)
		validate_private_evidence(
			self,
			"approval_evidence",
			checksum_field="approval_evidence_sha256" if self.approval_evidence else None,
			required=raising,
		)
		validate_accountable_actor(
			self, "approver", APPROVAL_ROLES, "approve", additional_excluded_users=(self.proposed_by,)
		)
		self.status = self.proposed_status
		self.proposed_status = None
		self.approved_by = frappe.session.user
		self.approved_on = now_datetime()
		self.flags.readiness_approved = True
		self.save()

	def _set_readiness_key(self) -> None:
		feature_code = (self.feature_code or "").strip().upper()
		if self.company and feature_code:
			self.feature_code = feature_code
			self.readiness_key = f"{self.company}|{feature_code}"
