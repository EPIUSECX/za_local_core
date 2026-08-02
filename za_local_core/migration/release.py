"""Deterministic release controls for repeated migration and legacy retirement."""

import json

import frappe

from za_local_core.governance import canonical_sha256


def assert_legacy_app_absent() -> bool:
	"""Fail a target-only release candidate if the retired monolith is installed."""
	if "za_local" in set(frappe.get_installed_apps() or ()):
		raise RuntimeError("Legacy app za_local is installed on the target-only release candidate")
	return True


def core_state_fingerprint() -> str:
	"""Hash stable core-owned migration state, excluding timestamps and user data."""
	return canonical_sha256(core_state_snapshot())


def core_state_snapshot() -> dict:
	return {
		"roles": _rows("Role", ["name"], {"name": ["like", "ZA Compliance%"]}),
		"source_catalog": _rows(
			"ZA Statutory Source", ["catalog_key", "status", "docstatus"], {"catalog_key": ["is", "set"]}
		),
		"profiles": _rows(
			"ZA Company Compliance Profile",
			["profile_key", "status", "docstatus", "enabled"],
		),
		"readiness": _rows("ZA Feature Readiness", ["name", "feature_code", "status", "domain"]),
		"desktop_icons": _rows(
			"Desktop Icon",
			["label", "icon_type", "parent_icon", "app", "logo_url", "link_to"],
			{"app": "za_local_core"},
		),
	}


def print_core_state_fingerprint() -> None:
	"""Bench-friendly output with no logger-dependent formatting."""
	print(core_state_fingerprint())


def _rows(doctype: str, fields: list[str], filters: dict | None = None) -> list[dict]:
	if not frappe.db.exists("DocType", doctype):
		return []
	rows = frappe.get_all(doctype, fields=fields, filters=filters or {}, order_by="name")
	return json.loads(json.dumps(rows, default=str, sort_keys=True))
