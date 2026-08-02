import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime

from za_local_core.governance import (
	APPROVAL_ROLES,
	REVIEW_ROLES,
	canonical_sha256,
	normalize_sha256,
	validate_accountable_actor,
	validate_private_evidence,
)


class ZACompanyComplianceProfile(Document):
	def before_naming(self) -> None:
		self.profile_key = self.profile_key or _profile_key(self.company, self.effective_from)

	def validate(self) -> None:
		country = frappe.get_cached_value("Company", self.company, "country")
		if country != "South Africa":
			frappe.throw(_("Company {0} must have Country set to South Africa.").format(self.company))
		if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
			frappe.throw(_("Effective To cannot be before Effective From."))
		self.profile_key = self.profile_key or _profile_key(self.company, self.effective_from)
		if self.approval_evidence_sha256:
			self.approval_evidence_sha256 = normalize_sha256(self.approval_evidence_sha256)
		if self.status == "Reviewed" and self.review_checksum != self._configuration_checksum():
			self.status = "Draft"
			self.reviewed_by = None
			self.reviewed_on = None
			self.review_checksum = None

	@frappe.whitelist(methods=["POST"])
	def mark_reviewed(self) -> None:
		if self.docstatus != 0:
			frappe.throw(_("Only a draft profile can be reviewed."))
		self.reviewed_by = frappe.session.user
		validate_accountable_actor(self, "reviewed_by", REVIEW_ROLES, "review")
		self.reviewed_on = now_datetime()
		self.review_checksum = self._configuration_checksum()
		self.status = "Reviewed"
		self.save()

	def before_submit(self) -> None:
		if not self.enabled:
			frappe.throw(_("Enable the profile before approval."))
		if self.status != "Reviewed" or not self.review_checksum:
			frappe.throw(_("The profile must be independently reviewed before approval."))
		if self.review_checksum != self._configuration_checksum():
			frappe.throw(_("The profile changed after review; review it again before approval."))
		validate_accountable_actor(
			self,
			"approved_by",
			APPROVAL_ROLES,
			"approve",
			additional_excluded_users=(self.reviewed_by,),
		)
		validate_private_evidence(
			self,
			"approval_evidence",
			checksum_field="approval_evidence_sha256",
			required=True,
		)
		self._validate_no_approved_overlap()
		self.status = "Approved"
		self.approved_on = now_datetime()

	def before_cancel(self) -> None:
		validate_accountable_actor(
			self,
			"approved_by",
			APPROVAL_ROLES,
			"cancel",
			additional_excluded_users=(self.reviewed_by,),
		)

	def on_cancel(self) -> None:
		self.db_set("status", "Cancelled", update_modified=False)

	def _configuration_checksum(self) -> str:
		return canonical_sha256(
			{
				"bargaining_council": self.bargaining_council,
				"coida_industry_class": self.coida_industry_class,
				"coida_registered": int(self.coida_registered or 0),
				"company": self.company,
				"effective_from": str(self.effective_from),
				"effective_to": str(self.effective_to or ""),
				"employment_equity_designated": int(self.employment_equity_designated or 0),
				"filing_contact": self.filing_contact,
				"paye_registered": int(self.paye_registered or 0),
				"sdl_registered": int(self.sdl_registered or 0),
				"seta": self.seta,
				"uif_registered": int(self.uif_registered or 0),
				"vat_registered": int(self.vat_registered or 0),
			}
		)

	def _validate_no_approved_overlap(self) -> None:
		profile = frappe.qb.DocType("ZA Company Compliance Profile")
		query = (
			frappe.qb.from_(profile)
			.select(profile.name)
			.where(profile.name != (self.name or ""))
			.where(profile.company == self.company)
			.where(profile.docstatus == 1)
			.where(profile.effective_from <= (self.effective_to or "9999-12-31"))
			.where((profile.effective_to.isnull()) | (profile.effective_to >= self.effective_from))
			.limit(1)
		)
		if overlap := query.run(pluck=True):
			frappe.throw(_("Profile dates overlap approved profile {0}.").format(overlap[0]))


def _profile_key(company: str, effective_from: str) -> str:
	if not company or not effective_from:
		frappe.throw(_("Company and Effective From are required."))
	return f"{company}|{getdate(effective_from)}"
