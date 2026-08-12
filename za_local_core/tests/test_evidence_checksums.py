"""Evidence digests are recorded by the app, never typed by a practitioner."""

import hashlib

import frappe
from frappe.tests.classes import IntegrationTestCase, UnitTestCase
from frappe.utils.file_manager import save_file

from za_local_core.governance import stamp_evidence_checksum

EVIDENCE_FIELDS = {
	"ZA Statutory Source": ("source_file", "sha256_checksum"),
	"ZA Submission Receipt": ("evidence_file", "sha256_checksum"),
	"ZA Company Compliance Profile": ("approval_evidence", "approval_evidence_sha256"),
	"ZA Filing": ("working_paper", "working_paper_sha256"),
	"VAT201 Return": ("adjustment_evidence", "adjustment_evidence_sha256"),
}


class TestDigestFieldsCannotBeTyped(UnitTestCase):
	def test_every_evidence_digest_is_read_only(self):
		"""A digest a practitioner can type is a digest they can get wrong or invent.

		It is derived from the attachment, so the form must not offer it for editing.
		"""
		for doctype, (_attach, checksum) in EVIDENCE_FIELDS.items():
			if not frappe.db.exists("DocType", doctype):
				continue
			field = frappe.get_meta(doctype).get_field(checksum)
			self.assertIsNotNone(field, f"{doctype} has no field {checksum}")
			self.assertTrue(field.read_only, f"{doctype}.{checksum} is editable")

	def test_every_evidence_digest_explains_itself(self):
		"""The form has to say where the value comes from; the guide is not always open."""
		for doctype, (_attach, checksum) in EVIDENCE_FIELDS.items():
			if not frappe.db.exists("DocType", doctype):
				continue
			field = frappe.get_meta(doctype).get_field(checksum)
			self.assertTrue(field.description, f"{doctype}.{checksum} has no description")


class TestStampEvidenceChecksum(IntegrationTestCase):
	def test_the_digest_matches_the_attached_bytes(self):
		payload = b"statutory evidence bytes for the stamping test\n"
		source = frappe.get_doc(
			{
				"doctype": "ZA Statutory Source",
				"catalog_key": "TEST-STAMP-001",
				"authority": "SARS",
				"title": "Digest stamping test",
				"document_type": "Test fixture",
				"version": "1",
				"publication_date": "2026-01-01",
				"effective_from": "2026-01-01",
				"source_url": "https://example.invalid/evidence",
			}
		).insert(ignore_permissions=True)
		try:
			attachment = save_file("stamp-test.txt", payload, source.doctype, source.name, is_private=1)
			source.source_file = attachment.file_url
			source.save(ignore_permissions=True)
			source.reload()
			self.assertEqual(hashlib.sha256(payload).hexdigest(), source.sha256_checksum)
		finally:
			frappe.delete_doc("ZA Statutory Source", source.name, force=True, ignore_permissions=True)

	def test_a_typed_digest_is_overwritten_rather_than_trusted(self):
		"""Anything already in the field is replaced by the truth about the file."""
		payload = b"the real bytes\n"
		doc = frappe.new_doc("ZA Statutory Source")
		doc.catalog_key = "TEST-STAMP-002"
		doc.authority = "SARS"
		doc.title = "Digest overwrite test"
		doc.document_type = "Test fixture"
		doc.version = "1"
		doc.publication_date = "2026-01-01"
		doc.effective_from = "2026-01-01"
		doc.source_url = "https://example.invalid/evidence"
		doc.insert(ignore_permissions=True)
		try:
			attachment = save_file("overwrite-test.txt", payload, doc.doctype, doc.name, is_private=1)
			doc.source_file = attachment.file_url
			doc.sha256_checksum = "0" * 64
			stamp_evidence_checksum(doc, "source_file", "sha256_checksum")
			self.assertEqual(hashlib.sha256(payload).hexdigest(), doc.sha256_checksum)
		finally:
			frappe.delete_doc("ZA Statutory Source", doc.name, force=True, ignore_permissions=True)

	def test_removing_the_attachment_clears_the_digest(self):
		"""A digest left behind would describe a file that is no longer there."""
		doc = frappe.new_doc("ZA Statutory Source")
		doc.sha256_checksum = "a" * 64
		doc.source_file = None
		self.assertIsNone(stamp_evidence_checksum(doc, "source_file", "sha256_checksum"))
		self.assertFalse(doc.sha256_checksum)
