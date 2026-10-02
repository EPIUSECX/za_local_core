import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, now_datetime

from za_local_core.governance import (
	APPROVAL_ROLES,
	REVIEW_ROLES,
	canonical_sha256,
	stamp_evidence_checksum,
	validate_accountable_actor,
	validate_private_evidence,
)


class ZAFiling(Document):
	def validate(self) -> None:
		if getdate(self.period_end) < getdate(self.period_start):
			frappe.throw(_("Period End cannot be before Period Start."))
		self.filing_key = "|".join(
			(self.company, self.obligation, str(self.period_start), str(self.period_end))
		)
		self.capability = frappe.db.get_value("ZA Compliance Obligation", self.obligation, "capability")
		stamp_evidence_checksum(self, "working_paper", "working_paper_sha256")
		self.unexplained_difference = flt(self.declared_amount) - flt(self.ledger_amount)

	@frappe.whitelist(methods=["POST"])
	def mark_reviewed(self) -> None:
		"""Record an accountable review before a different user approves the filing."""
		if self.docstatus != 0:
			frappe.throw(_("Only a draft filing can be reviewed."))
		if self.status not in {"Draft", "Reviewed"}:
			frappe.throw(_("Filing status must be Draft before review."))
		validate_accountable_actor(
			self,
			"reviewed_by",
			REVIEW_ROLES,
			"review",
			additional_excluded_users=(self.approved_by,),
		)
		self._validate_working_paper()
		self.status = "Reviewed"
		self.reviewed_on = now_datetime()
		self.review_checksum = self._calculate_review_checksum()
		self.save()

	def before_submit(self) -> None:
		if frappe.db.get_value("ZA Compliance Obligation", self.obligation, "docstatus") != 1:
			frappe.throw(_("Compliance Obligation {0} must be approved.").format(self.obligation))
		if self.status != "Reviewed" or not self.reviewed_on or not self.review_checksum:
			frappe.throw(_("The recorded reviewer must complete Mark Reviewed before approval."))
		validate_accountable_actor(
			self,
			"approved_by",
			APPROVAL_ROLES,
			"approve",
			additional_excluded_users=(self.reviewed_by,),
		)
		self._validate_working_paper()
		if self.review_checksum != self._calculate_review_checksum():
			frappe.throw(_("The filing changed after review. Complete Mark Reviewed again before approval."))
		if flt(self.unexplained_difference, 2) and not (self.notes or "").strip():
			frappe.throw(_("Explain the reconciliation difference before approving this filing."))
		if self.capability == "Unsupported":
			frappe.throw(_("Unsupported obligations cannot be approved for filing."))
		self.status = "Approved"
		self.approved_on = now_datetime()

	def on_cancel(self) -> None:
		# Release the unique period key, as VAT201 Return does with its active-period
		# key, so the amended working paper can create its replacement filing.
		self.db_set({"status": "Cancelled", "filing_key": None}, update_modified=False)

	def before_cancel(self) -> None:
		validate_accountable_actor(
			self,
			"approved_by",
			APPROVAL_ROLES,
			"cancel",
			additional_excluded_users=(self.reviewed_by,),
		)

	def _validate_working_paper(self) -> None:
		validate_private_evidence(
			self,
			"working_paper",
			checksum_field="working_paper_sha256",
			required=True,
		)

	def _calculate_review_checksum(self) -> str:
		return canonical_sha256(
			{
				"approved_by": self.approved_by,
				"capability": self.capability,
				"company": self.company,
				"currency": self.currency,
				"declared_amount": flt(self.declared_amount, 9),
				"due_date": str(self.due_date),
				"ledger_amount": flt(self.ledger_amount, 9),
				"notes": (self.notes or "").strip(),
				"obligation": self.obligation,
				"period_end": str(self.period_end),
				"period_start": str(self.period_start),
				"paid_amount": flt(self.paid_amount, 9),
				"reviewed_by": self.reviewed_by,
				"working_paper_sha256": self.working_paper_sha256,
			}
		)
