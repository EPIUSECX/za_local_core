"""Idempotent installation for the shared localisation foundation."""

import frappe


CORE_ROLES = (
	("ZA Compliance User", "Prepare South African compliance working papers"),
	("ZA Compliance Reviewer", "Review South African compliance working papers"),
	("ZA Compliance Manager", "Approve South African compliance configuration and filings"),
)


def after_install() -> None:
	ensure_core_roles()


def after_migrate() -> None:
	ensure_core_roles()


def ensure_core_roles() -> None:
	"""Create missing roles without overwriting administrator-managed role settings."""
	for role_name, description in CORE_ROLES:
		if frappe.db.exists("Role", role_name):
			continue
		frappe.get_doc(
			{
				"doctype": "Role",
				"role_name": role_name,
				"desk_access": 1,
				"description": description,
			}
		).insert(ignore_permissions=True)
