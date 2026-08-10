"""Deterministic governance staging for isolated ``*.test`` sites only."""

from __future__ import annotations

import hashlib

import frappe
from frappe import _
from frappe.utils.file_manager import save_file

from za_local_core.sa_vat.statutory import (
	COMPULSORY_REGISTRATION_THRESHOLD,
	CURRENT_APPROVED_SOURCE_METADATA,
	FULL_INVOICE_THRESHOLD,
	NO_INVOICE_THRESHOLD,
	STANDARD_RATE,
	VOLUNTARY_REGISTRATION_THRESHOLD,
)

TEST_REVIEWER = "_test.finance.governance.reviewer@example.com"


def stage_approved_test_vat_governance(
	effective_from: str = "2026-04-01",
	effective_to: str = "2027-03-31",
) -> dict[str, str]:
	"""Create reviewed test evidence and a submitted pack on an isolated test site."""
	_assert_test_site()
	reviewer = _ensure_reviewer()
	period_key = f"{effective_from}-{effective_to}"
	content = (
		"TEST-ONLY SARS VAT governance evidence\n"
		f"period={period_key}\n"
		f"metadata={CURRENT_APPROVED_SOURCE_METADATA}\n"
	).encode()
	checksum = hashlib.sha256(content).hexdigest()
	catalog_key = f"TEST-SARS-VAT-{period_key}"
	source_name = frappe.db.get_value("ZA Statutory Source", {"catalog_key": catalog_key}, "name")
	if not source_name:
		file_doc = save_file(
			f"_test-vat-governance-{effective_from}.txt",
			content,
			None,
			None,
			is_private=1,
		)
		source = frappe.get_doc(
			{
				"doctype": "ZA Statutory Source",
				"catalog_key": catalog_key,
				"authority": "SARS",
				"title": f"TEST ONLY VAT controls {period_key}",
				"document_type": "Test governance evidence",
				"version": period_key,
				"publication_date": effective_from,
				"effective_from": effective_from,
				"effective_to": effective_to,
				"source_url": CURRENT_APPROVED_SOURCE_METADATA["registration_source_url"],
				"source_file": file_doc.file_url,
				"sha256_checksum": checksum,
				"reviewed_by": reviewer,
				"notes": "TEST ONLY. Never migrate this record to production.",
			}
		).insert()
		with _acting_as(reviewer):
			source.submit()
		source_name = source.name

	# Look for any live pack in this window, not just a submitted one. Install seeds a
	# draft across exactly this period, and packs may not overlap, so a fixture that
	# only recognised its own submitted pack would be unable to insert at all.
	# Adopting the seeded draft is also what a practitioner actually does.
	existing = frappe.db.get_value(
		"ZA Statutory Rate Pack",
		{
			"domain": "VAT",
			"effective_from": effective_from,
			"effective_to": effective_to,
			"docstatus": ("<", 2),
		},
		["name", "docstatus"],
		as_dict=True,
	)
	pack_name = existing.name if existing else None
	if existing and existing.docstatus == 0:
		pack = frappe.get_doc("ZA Statutory Rate Pack", existing.name)
		# Repoint at the reviewed test source: the seeded source carries no evidence
		# and therefore cannot be approved, which would block this submit.
		pack.source = source_name
		pack.reviewed_by = reviewer
		pack.save()
		with _acting_as(reviewer):
			pack.submit()
	elif not pack_name:
		values = CURRENT_APPROVED_SOURCE_METADATA["expected_current_values"]
		pack = frappe.get_doc(
			{
				"doctype": "ZA Statutory Rate Pack",
				"domain": "VAT",
				"title": f"TEST ONLY VAT controls {period_key}",
				"source": source_name,
				"effective_from": effective_from,
				"effective_to": effective_to,
				"reviewed_by": reviewer,
				"notes": "TEST ONLY. Deterministic E2E statutory controls.",
				"items": [
					_item(STANDARD_RATE, values[STANDARD_RATE], "Percentage"),
					_item(
						COMPULSORY_REGISTRATION_THRESHOLD,
						values[COMPULSORY_REGISTRATION_THRESHOLD],
						"Amount",
					),
					_item(
						VOLUNTARY_REGISTRATION_THRESHOLD,
						values[VOLUNTARY_REGISTRATION_THRESHOLD],
						"Amount",
					),
					_item(NO_INVOICE_THRESHOLD, values[NO_INVOICE_THRESHOLD], "Amount"),
					_item(FULL_INVOICE_THRESHOLD, values[FULL_INVOICE_THRESHOLD], "Amount"),
				],
			}
		).insert()
		with _acting_as(reviewer):
			pack.submit()
		pack_name = pack.name

	return {"source": source_name, "rate_pack": pack_name, "reviewer": reviewer}


def _item(rule_key: str, value: float, unit: str) -> dict:
	return {
		"rule_key": rule_key,
		"numeric_value": value,
		"unit": unit,
		"precision": 2,
	}


def _assert_test_site() -> None:
	site = frappe.local.site or ""
	if not (site.endswith(".test") or frappe.flags.in_test):
		frappe.throw(
			_("Test VAT governance fixtures may only be staged on an isolated .test site."),
			frappe.PermissionError,
		)


def _ensure_reviewer() -> str:
	if not frappe.db.exists("User", TEST_REVIEWER):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": TEST_REVIEWER,
				"first_name": "Test Finance Governance Reviewer",
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)
	user = frappe.get_doc("User", TEST_REVIEWER)
	if "ZA Compliance Reviewer" not in frappe.get_roles(TEST_REVIEWER):
		user.add_roles("ZA Compliance Reviewer")
	return TEST_REVIEWER


class _acting_as:
	def __init__(self, user: str):
		self.user = user
		self.previous = None

	def __enter__(self):
		self.previous = frappe.session.user
		frappe.set_user(self.user)

	def __exit__(self, exc_type, exc_value, traceback):
		frappe.set_user(self.previous or "Administrator")
