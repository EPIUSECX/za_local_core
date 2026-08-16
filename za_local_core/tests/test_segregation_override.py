"""A System Manager may push a governance record through, but never quietly."""

import frappe
from frappe.tests.classes import IntegrationTestCase
from frappe.utils.file_manager import save_file

from za_local_core.governance import SEGREGATION_OVERRIDE_ROLE


class TestSegregationOverride(IntegrationTestCase):
	"""Separation of duties needs three people on a compliance profile and two on a
	source. A single-administrator site cannot satisfy either, so a System Manager is
	allowed through and the override is recorded on the document.
	"""

	def setUp(self):
		self.ordinary = self._ensure_user("_test.za.ordinary@example.com", "ZA Ordinary")

	def test_administrator_holds_the_override_role(self):
		"""The whole design rests on this, so state it rather than assume it."""
		self.assertIn(SEGREGATION_OVERRIDE_ROLE, frappe.get_roles("Administrator"))

	def test_a_system_manager_may_approve_a_record_they_prepared(self):
		source = self._draft_source("override-approve")
		source.reviewed_by = "Administrator"
		source.save(ignore_permissions=True)
		source.submit()
		source.reload()
		self.assertEqual(1, source.docstatus)
		self.assertEqual("Approved", source.status)

	def test_the_override_is_recorded_on_the_document(self):
		"""An auditor must be able to tell this from an independent approval."""
		source = self._draft_source("override-comment")
		source.reviewed_by = "Administrator"
		source.save(ignore_permissions=True)
		source.submit()

		comments = frappe.get_all(
			"Comment",
			filters={"reference_doctype": source.doctype, "reference_name": source.name},
			pluck="content",
		)
		overrides = [c for c in comments if "Separation of duties overridden" in (c or "")]
		self.assertTrue(overrides, f"no override comment was recorded; comments were {comments}")
		self.assertIn("Administrator", overrides[0])

	def test_an_ordinary_user_is_still_refused(self):
		"""The override is the System Manager's alone; everyone else stays strict."""
		source = self._draft_source("override-refused")
		source.reviewed_by = "Administrator"
		source.save(ignore_permissions=True)
		frappe.share.add(source.doctype, source.name, self.ordinary, write=1, submit=1)
		with self.set_user(self.ordinary), self.assertRaises(frappe.PermissionError):
			source.submit()

	def test_an_independent_approval_records_no_override(self):
		"""Only a genuine bypass leaves a note, otherwise the signal means nothing."""
		reviewer = self._ensure_user(
			"_test.za.independent@example.com", "ZA Independent", "ZA Compliance Reviewer"
		)
		source = self._draft_source("override-clean")
		source.reviewed_by = reviewer
		source.save(ignore_permissions=True)
		with self.set_user(reviewer):
			source.submit()

		comments = frappe.get_all(
			"Comment",
			filters={"reference_doctype": source.doctype, "reference_name": source.name},
			pluck="content",
		)
		self.assertFalse([c for c in comments if "Separation of duties overridden" in (c or "")])

	def _draft_source(self, stem: str):
		source = frappe.get_doc(
			{
				"doctype": "ZA Statutory Source",
				"authority": "SARS",
				"title": f"_Test override {stem}",
				"document_type": "Test fixture",
				"version": stem[:8],
				"publication_date": "2026-03-01",
				"effective_from": "2026-03-01",
				"source_url": "https://www.sars.gov.za/",
			}
		).insert(ignore_permissions=True)
		attachment = save_file(
			f"_test-{stem}.txt", f"evidence for {stem}".encode(), source.doctype, source.name, is_private=1
		)
		source.source_file = attachment.file_url
		return source

	@staticmethod
	def _ensure_user(email: str, full_name: str, role: str = "ZA Compliance Manager") -> str:
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{"doctype": "User", "email": email, "first_name": full_name, "send_welcome_email": 0}
			).insert(ignore_permissions=True)
		user = frappe.get_doc("User", email)
		if role not in {r.role for r in user.roles}:
			user.append("roles", {"role": role})
			user.save(ignore_permissions=True)
		return email
