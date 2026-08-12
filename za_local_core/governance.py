"""Shared controls for accountable compliance actions and evidence."""

import hashlib
import json
import re
from collections.abc import Iterable

import frappe
from frappe import _

REVIEW_ROLES = frozenset({"ZA Compliance Reviewer", "ZA Compliance Manager", "System Manager"})
APPROVAL_ROLES = frozenset({"ZA Compliance Manager", "System Manager"})
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


def validate_accountable_actor(
	doc,
	actor_field: str,
	allowed_roles: Iterable[str],
	action: str,
	additional_excluded_users: Iterable[str | None] = (),
) -> str:
	"""Require the signed-in user to be the recorded, authorised independent actor."""
	actor = frappe.session.user
	recorded_actor = doc.get(actor_field)
	label = doc.meta.get_label(actor_field)
	if not recorded_actor:
		frappe.throw(_("{0} is required before {1}.").format(label, action))
	if actor != recorded_actor:
		frappe.throw(
			_("Only the recorded {0}, {1}, may {2} this document.").format(label, recorded_actor, action),
			frappe.PermissionError,
		)
	excluded_users = {doc.owner, *additional_excluded_users}
	excluded_users.discard(None)
	if actor in excluded_users:
		frappe.throw(
			_("The document creator or responsible preparer cannot {0} the same document.").format(action),
			frappe.PermissionError,
		)
	actor_roles = set(frappe.get_roles(actor))
	required_roles = set(allowed_roles)
	if actor_roles.isdisjoint(required_roles):
		frappe.throw(
			_("{0} requires one of these roles: {1}.").format(
				action.title(), ", ".join(sorted(required_roles))
			),
			frappe.PermissionError,
		)
	return actor


def normalize_sha256(value: str | None, label: str = "SHA-256 Checksum") -> str:
	"""Normalize and validate one SHA-256 digest."""
	digest = (value or "").strip().lower()
	if not SHA256_PATTERN.fullmatch(digest):
		frappe.throw(_("{0} must contain exactly 64 hexadecimal characters.").format(label))
	return digest


def stamp_evidence_checksum(doc, fieldname: str, checksum_field: str) -> str | None:
	"""Record the digest of the attached evidence, replacing whatever is stored.

	The digest is computed, never typed. A hand-entered value only ever proved that
	the uploader pasted the hash of the file they had just uploaded, which is the one
	thing the server can already see for itself. Computing it gives the same tamper
	evidence -- a recorded digest that detects a later substitution of the file --
	without the friction, and it cannot be mistyped or invented.

	Only drafts are stamped. Approval re-hashes the stored bytes and compares them to
	what was recorded, so stamping during submit would repair a substituted file
	instead of refusing it, and that comparison would never be able to fail.

	Returns the digest, or None when nothing is attached yet or the record is no
	longer a draft.
	"""
	if doc.docstatus != 0:
		return doc.get(checksum_field)

	file_url = (doc.get(fieldname) or "").strip()
	if not file_url:
		doc.set(checksum_field, None)
		return None

	file_name = frappe.db.get_value("File", {"file_url": file_url, "is_folder": 0}, "name")
	if not file_name:
		# The attachment is unresolved. before_submit reports that properly; leaving
		# any stale digest in place here would let it describe a different file.
		doc.set(checksum_field, None)
		return None

	content = frappe.get_doc("File", file_name).get_content()
	if isinstance(content, str):
		content = content.encode()
	digest = hashlib.sha256(content).hexdigest()

	# Where the digest is unique, attaching one document to two records now collides
	# every time rather than only when someone typed the same value. Name the record
	# holding it: a raw unique-constraint error quotes 64 hex characters and tells
	# the practitioner nothing.
	field = doc.meta.get_field(checksum_field)
	if field and field.unique:
		clash = frappe.db.get_value(
			doc.doctype, {checksum_field: digest, "name": ["!=", doc.name or ""]}, "name"
		)
		if clash:
			frappe.throw(
				_(
					"{0} is already recorded as the evidence on {1} {2}. Each one needs its own document."
				).format(doc.meta.get_label(fieldname), doc.doctype, clash),
				title=_("Evidence Already Recorded"),
			)

	doc.set(checksum_field, digest)
	return digest


def validate_private_evidence(
	doc,
	fieldname: str,
	*,
	checksum_field: str | None = None,
	required: bool = False,
) -> str | None:
	"""Verify that an attachment is a private File and optionally match its bytes."""
	file_url = (doc.get(fieldname) or "").strip()
	label = doc.meta.get_label(fieldname)
	if not file_url:
		if required:
			frappe.throw(_("{0} is required for this compliance action.").format(label))
		return None

	file_rows = frappe.get_all(
		"File",
		filters={"file_url": file_url, "is_folder": 0},
		fields=["name", "is_private"],
		limit=2,
	)
	if not file_rows:
		frappe.throw(_("{0} must reference a stored File record; upload the evidence again.").format(label))
	file_row = file_rows[0]
	if any(not row.is_private for row in file_rows) or not file_url.startswith("/private/files/"):
		frappe.throw(
			_("{0} contains compliance evidence and must be stored as a private file.").format(label)
		)

	if checksum_field:
		checksum_label = doc.meta.get_label(checksum_field)
		expected = normalize_sha256(doc.get(checksum_field), checksum_label)
		file_doc = frappe.get_doc("File", file_row.name)
		content = file_doc.get_content()
		if isinstance(content, str):
			content = content.encode()
		actual = hashlib.sha256(content).hexdigest()
		if actual != expected:
			frappe.throw(_("{0} does not match the SHA-256 checksum of {1}.").format(checksum_label, label))
	return file_url


def validate_populated_private_attachments(doc) -> None:
	"""Reject public or unresolved files in populated Attach fields."""
	for field in doc.meta.get("fields"):
		if field.fieldtype == "Attach" and doc.get(field.fieldname):
			validate_private_evidence(doc, field.fieldname)


def canonical_sha256(payload: dict) -> str:
	"""Hash a JSON-compatible payload using one stable representation."""
	serialized = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
	return hashlib.sha256(serialized.encode()).hexdigest()
