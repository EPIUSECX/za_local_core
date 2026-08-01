import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class ZAFeatureReadiness(Document):
	def before_naming(self) -> None:
		self._set_readiness_key()

	def validate(self) -> None:
		self.feature_code = (self.feature_code or "").strip().upper()
		self._set_readiness_key()
		self.checked_by = frappe.session.user
		self.checked_on = now_datetime()
		if self.status in ("Controlled Manual", "Preview", "Unsupported", "Blocked") and not (
			self.blocking_reason or ""
		).strip():
			frappe.throw(_("Blocking Reason or Limitations is required for status {0}.").format(self.status))

	def _set_readiness_key(self) -> None:
		feature_code = (self.feature_code or "").strip().upper()
		if self.company and feature_code:
			self.feature_code = feature_code
			self.readiness_key = f"{self.company}|{feature_code}"
