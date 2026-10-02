import hashlib

import frappe
from frappe.tests.classes import IntegrationTestCase
from frappe.utils.file_manager import save_file

from za_local_core.services.profiles import resolve_company_profile
from za_local_core.services.rates import get_rate, resolve_rate
from za_local_core.tests.utils import ensure_south_african_company


class TestGovernanceLifecycle(IntegrationTestCase):
	def setUp(self):
		self.company = ensure_south_african_company()
		self.reviewer = self._ensure_user(
			"_test.za.reviewer@example.com", "ZA Reviewer", "ZA Compliance Reviewer"
		)
		self.approver = self._ensure_user(
			"_test.za.approver@example.com", "ZA Approver", "ZA Compliance Manager"
		)

	def test_approved_source_and_rate_are_resolved_by_date(self):
		source = self._approved_source("vat")
		pack = frappe.get_doc(
			{
				"doctype": "ZA Statutory Rate Pack",
				"domain": "CIPC",
				"title": "_Test generic governed rates",
				"source": source.name,
				"effective_from": "2026-04-01",
				"effective_to": "2027-03-31",
				"reviewed_by": self.reviewer,
				"items": [{"rule_key": "cipc.test_rate", "numeric_value": 15, "unit": "Percentage"}],
			}
		).insert()
		with self.set_user(self.reviewer):
			pack.submit()

		self.assertEqual(get_rate("CIPC", "cipc.test_rate", "2026-08-01"), 15)
		resolution = resolve_rate("CIPC", "cipc.test_rate", "2026-08-01", expected_unit="Percentage")
		self.assertEqual(source.name, resolution["source"])
		self.assertRegex(resolution["source_sha256"], r"^[0-9a-f]{64}$")
		with self.assertRaises(frappe.ValidationError):
			get_rate("CIPC", "cipc.test_rate", "2025-08-01")
		with self.assertRaises(frappe.ValidationError):
			resolve_rate("CIPC", "cipc.test_rate", "2026-08-01", expected_unit="Amount")

	def test_company_profile_requires_independent_review_approval_and_evidence(self):
		evidence, evidence_checksum = self._evidence("profile-approval", b"profile approval")
		profile = frappe.get_doc(
			{
				"doctype": "ZA Company Compliance Profile",
				"company": self.company,
				"effective_from": "2030-01-01",
				"effective_to": "2030-12-31",
				"enabled": 1,
				"vat_registered": 1,
				"reviewed_by": self.reviewer,
				"approved_by": self.approver,
				"approval_evidence": evidence,
				"approval_evidence_sha256": evidence_checksum,
			}
		).insert()
		with self.set_user(self.reviewer):
			profile.mark_reviewed()
		profile.reload()
		self.assertEqual("Reviewed", profile.status)
		with self.set_user(self.approver):
			profile.submit()

		resolved = resolve_company_profile(self.company, "2030-06-01")
		self.assertEqual(profile.name, resolved["name"])
		self.assertEqual(1, resolved["vat_registered"])

	def test_overlapping_rate_pack_is_rejected(self):
		source = self._approved_source("overlap")
		# Use a period isolated from the rate pack created by the date-resolution
		# test. Frappe integration tests share their class transaction, so reusing
		# 2026 here would make the first insert collide before this test can create
		# the deliberate second overlap.
		self._insert_rate_pack(source.name, "2035-01-01", "2035-12-31")
		with self.assertRaises(frappe.ValidationError):
			self._insert_rate_pack(source.name, "2035-06-01", "2036-05-31")

	def test_source_rejects_spoofed_reviewer_and_public_or_changed_evidence(self):
		private_url, private_checksum = self._evidence("source-private", b"authoritative source")
		source = self._source(private_url, private_checksum, self.reviewer).insert()
		# self.approver holds ZA Compliance Manager but not System Manager, so the
		# recorded-actor rule still binds them. Administrator would now override it.
		with self.set_user(self.approver), self.assertRaises(frappe.PermissionError):
			source.submit()

		public_url, public_checksum = self._evidence("source-public", b"public source", is_private=0)
		public_source = self._source(public_url, public_checksum, self.reviewer).insert()
		with self.set_user(self.reviewer), self.assertRaises(frappe.ValidationError):
			public_source.submit()

		# A mistyped digest is no longer reachable: the field is read-only and stamped
		# from the attachment while the record is a draft. What is still reachable is
		# the attachment being swapped after the digest was recorded, so approval
		# re-hashes the stored bytes. Repointed straight at the column to bypass the
		# stamping, which is the only way a live site could drift.
		changed_url, changed_checksum = self._evidence("source-changed", b"the approved document")
		changed_source = self._source(changed_url, changed_checksum, self.reviewer).insert()
		substitute_url, _ = self._evidence("source-substitute", b"a different document altogether")
		frappe.db.set_value(
			"ZA Statutory Source", changed_source.name, "source_file", substitute_url, update_modified=False
		)
		changed_source.reload()
		with self.set_user(self.reviewer), self.assertRaises(frappe.ValidationError):
			changed_source.submit()

		preparer = self._ensure_user("_test.za.preparer@example.com", "ZA Preparer", "ZA Compliance User")
		role_url, role_checksum = self._evidence("source-role", b"role-controlled source")
		role_source = self._source(role_url, role_checksum, preparer).insert()
		role_source.flags.ignore_permissions = True
		with self.set_user(preparer), self.assertRaises(frappe.PermissionError):
			role_source.submit()

	def test_only_recorded_reviewer_can_cancel_approved_source(self):
		source = self._approved_source("cancel")
		with self.set_user(self.approver), self.assertRaises(frappe.PermissionError):
			source.cancel()
		source.reload()
		with self.set_user(self.reviewer):
			source.cancel()
		self.assertEqual(source.status, "Cancelled")

	def test_rate_pack_requires_numeric_values_and_normalizes_precision(self):
		source = self._approved_source("numeric")
		missing = self._rate_pack(source.name)
		missing.items[0].numeric_value = None
		with self.assertRaises(frappe.ValidationError):
			missing.insert()

		invalid_precision = self._rate_pack(source.name)
		invalid_precision.items[0].precision = 10
		with self.assertRaises(frappe.ValidationError):
			invalid_precision.insert()

		normalized = self._rate_pack(source.name)
		normalized.items[0].numeric_value = 1.235
		normalized.items[0].precision = 2
		normalized.insert()
		self.assertEqual(normalized.items[0].numeric_value, 1.24)
		self.assertRegex(normalized.content_sha256, r"^[0-9a-f]{64}$")

	def test_filing_requires_separation_and_receipt_updates_external_state(self):
		file_error_count = frappe.db.count("Error Log", {"error": ["like", "%_test-receipt%"]})
		source = self._approved_source("filing")
		obligation = frappe.get_doc(
			{
				"doctype": "ZA Compliance Obligation",
				"obligation_code": "_TEST-VAT201",
				"title": "_Test VAT201",
				"domain": "VAT",
				"authority": "SARS",
				"source": source.name,
				"frequency": "Bi-monthly",
				"due_rule": "_Test rule",
				"capability": "Controlled Manual",
				"effective_from": "2026-01-01",
			}
		).insert()
		obligation.submit()

		filing = frappe.get_doc(
			{
				"doctype": "ZA Filing",
				"company": self.company,
				"obligation": obligation.name,
				"period_start": "2026-06-01",
				"period_end": "2026-07-31",
				"due_date": "2026-08-25",
				"currency": "ZAR",
				"ledger_amount": 100,
				"declared_amount": 100,
				"reviewed_by": self.reviewer,
				"approved_by": self.approver,
			}
		).insert()
		self.assertEqual(self._calendar(filing), {"filing": filing.name, "status": "In Progress"})
		working_paper, working_paper_checksum = self._evidence(
			"filing-working-paper", b"approved filing working paper"
		)
		filing.working_paper = working_paper
		filing.working_paper_sha256 = working_paper_checksum
		filing.save()
		with self.set_user(self.reviewer):
			filing.mark_reviewed()
		filing.reload()
		filing.notes = "_Test changed after accountable review"
		filing.save()
		with self.set_user(self.approver), self.assertRaises(frappe.ValidationError):
			filing.submit()
		filing.reload()
		with self.set_user(self.reviewer):
			filing.mark_reviewed()
		filing.reload()
		with self.set_user(self.approver):
			filing.submit()
		self.assertEqual(filing.status, "Approved")
		self.assertEqual(self._calendar(filing), {"filing": filing.name, "status": "Approved"})

		receipt_file, receipt_checksum = self._evidence("receipt", b"authority receipt")
		receipt = frappe.get_doc(
			{
				"doctype": "ZA Submission Receipt",
				"filing": filing.name,
				"authority_reference": "_TEST-REF-1",
				"submitted_at": "2026-08-20 10:00:00",
				"response_status": "Accepted",
				"submitted_by": self.approver,
				"evidence_file": receipt_file,
				"sha256_checksum": receipt_checksum,
				"declared_amount": 100,
			}
		).insert()
		with self.set_user(self.approver):
			receipt.submit()
		self.assertEqual(frappe.db.get_value("ZA Filing", filing.name, "status"), "Accepted")
		self.assertEqual(self._calendar(filing), {"filing": filing.name, "status": "Accepted"})
		self.assertEqual(
			file_error_count,
			frappe.db.count("Error Log", {"error": ["like", "%_test-receipt%"]}),
		)

		# Cancelling releases the period: past its due date it is overdue again
		# until an amended filing links itself.
		with self.set_user(self.approver):
			receipt.cancel()
		self.assertEqual(self._calendar(filing), {"filing": filing.name, "status": "Approved"})
		filing.reload()
		with self.set_user(self.approver):
			filing.cancel()
		self.assertEqual(self._calendar(filing), {"filing": None, "status": "Overdue"})

	def _calendar(self, filing):
		key = "|".join((filing.company, filing.obligation, str(filing.period_start), str(filing.period_end)))
		return frappe.db.get_value("ZA Compliance Calendar Entry", key, ["filing", "status"], as_dict=True)

	def test_evidence_fixture_creates_a_real_private_file(self):
		file_url, checksum = self._evidence("real-private-file", b"real private evidence")
		file_doc = frappe.get_doc("File", {"file_url": file_url})
		self.assertEqual(1, file_doc.is_private)
		content = file_doc.get_content()
		if isinstance(content, str):
			content = content.encode()
		self.assertEqual(b"real private evidence", content)
		self.assertEqual(hashlib.sha256(content).hexdigest(), checksum)

	def test_feature_readiness_derives_its_key_before_naming(self):
		doc = frappe.get_doc(
			{
				"doctype": "ZA Feature Readiness",
				"company": self.company,
				"feature_code": "_test-readiness",
				"feature_name": "_Test readiness",
				"domain": "Core",
				"status": "Preview",
				"blocking_reason": "_Test limitation",
			}
		).insert(ignore_permissions=True)

		self.assertEqual(doc.name, f"{self.company}|_TEST-READINESS")

	def _approved_source(self, suffix: str):
		file_url, checksum = self._evidence(f"source-{suffix}", f"source-{suffix}".encode())
		source = self._source(file_url, checksum, self.reviewer).insert()
		with self.set_user(self.reviewer):
			source.submit()
		return source

	def _source(self, file_url: str, checksum: str, reviewer: str):
		return frappe.get_doc(
			{
				"doctype": "ZA Statutory Source",
				"authority": "SARS",
				"title": f"_Test statutory source {checksum[:8]}",
				"document_type": "Guide",
				"version": checksum[:8],
				"publication_date": "2026-03-01",
				"effective_from": "2026-03-01",
				"source_url": "https://www.sars.gov.za/",
				"source_file": file_url,
				"sha256_checksum": checksum,
				"reviewed_by": reviewer,
			}
		)

	def _insert_rate_pack(self, source: str, effective_from: str, effective_to: str):
		pack = self._rate_pack(source)
		pack.title = f"_Test {effective_from}"
		pack.effective_from = effective_from
		pack.effective_to = effective_to
		return pack.insert()

	def _rate_pack(self, source: str):
		return frappe.get_doc(
			{
				"doctype": "ZA Statutory Rate Pack",
				"domain": "CIPC",
				"title": "_Test rate pack",
				"source": source,
				"effective_from": "2028-01-01",
				"effective_to": "2028-12-31",
				"reviewed_by": self.reviewer,
				"items": [{"rule_key": "test.rate", "numeric_value": 1, "unit": "Amount"}],
			}
		)

	@staticmethod
	def _evidence(stem: str, content: bytes, is_private: int = 1) -> tuple[str, str]:
		file_doc = save_file(f"_test-{stem}.txt", content, None, None, is_private=is_private)
		return file_doc.file_url, hashlib.sha256(content).hexdigest()

	@staticmethod
	def _ensure_user(email: str, full_name: str, role: str) -> str:
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": full_name,
					"send_welcome_email": 0,
				}
			).insert(ignore_permissions=True)
		user = frappe.get_doc("User", email)
		if role not in frappe.get_roles(email):
			user.add_roles(role)
		return email
