import frappe
from frappe.tests.classes import IntegrationTestCase

from za_local_core.services.rates import get_rate


class TestGovernanceLifecycle(IntegrationTestCase):
	def setUp(self):
		self.company = frappe.get_all("Company", filters={"country": "South Africa"}, pluck="name", limit=1)[0]
		self.reviewer = self._ensure_user("_test.za.reviewer@example.com", "ZA Reviewer")
		self.approver = self._ensure_user("_test.za.approver@example.com", "ZA Approver")

	def test_approved_source_and_rate_are_resolved_by_date(self):
		source = self._approved_source("b" * 64)
		pack = frappe.get_doc(
			{
				"doctype": "ZA Statutory Rate Pack",
				"domain": "VAT",
				"title": "_Test VAT rates",
				"source": source.name,
				"effective_from": "2026-04-01",
				"effective_to": "2027-03-31",
				"reviewed_by": self.reviewer,
				"items": [{"rule_key": "vat.standard_rate", "numeric_value": 15, "unit": "Percentage"}],
			}
		).insert()
		pack.submit()

		self.assertEqual(get_rate("VAT", "vat.standard_rate", "2026-08-01"), 15)
		with self.assertRaises(frappe.ValidationError):
			get_rate("VAT", "vat.standard_rate", "2025-08-01")

	def test_overlapping_rate_pack_is_rejected(self):
		source = self._approved_source("c" * 64)
		self._insert_rate_pack(source.name, "2026-01-01", "2026-12-31")
		with self.assertRaises(frappe.ValidationError):
			self._insert_rate_pack(source.name, "2026-06-01", "2027-05-31")

	def test_filing_requires_separation_and_receipt_updates_external_state(self):
		source = self._approved_source("d" * 64)
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
		filing.submit()
		self.assertEqual(filing.status, "Approved")

		receipt = frappe.get_doc(
			{
				"doctype": "ZA Submission Receipt",
				"filing": filing.name,
				"authority_reference": "_TEST-REF-1",
				"submitted_at": "2026-08-20 10:00:00",
				"response_status": "Accepted",
				"submitted_by": self.approver,
				"evidence_file": "/private/files/_test-receipt.pdf",
				"sha256_checksum": "e" * 64,
				"declared_amount": 100,
			}
		).insert()
		receipt.submit()
		self.assertEqual(frappe.db.get_value("ZA Filing", filing.name, "status"), "Accepted")

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

	def _approved_source(self, checksum: str):
		source = frappe.get_doc(
			{
				"doctype": "ZA Statutory Source",
				"authority": "SARS",
				"title": "_Test statutory source",
				"document_type": "Guide",
				"version": checksum[0],
				"publication_date": "2026-03-01",
				"effective_from": "2026-03-01",
				"source_url": "https://www.sars.gov.za/",
				"sha256_checksum": checksum,
				"reviewed_by": self.reviewer,
			}
		).insert()
		source.submit()
		return source

	def _insert_rate_pack(self, source: str, effective_from: str, effective_to: str):
		return frappe.get_doc(
			{
				"doctype": "ZA Statutory Rate Pack",
				"domain": "Payroll",
				"title": f"_Test {effective_from}",
				"source": source,
				"effective_from": effective_from,
				"effective_to": effective_to,
				"reviewed_by": self.reviewer,
				"items": [{"rule_key": "test.rate", "numeric_value": 1, "unit": "Amount"}],
			}
		).insert()

	@staticmethod
	def _ensure_user(email: str, full_name: str) -> str:
		if frappe.db.exists("User", email):
			return email
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": full_name,
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)
		return email
