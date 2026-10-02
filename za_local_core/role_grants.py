"""One-time permission grants on standard DocTypes that the ZA roles need.

A grant is added only where the role has no rule at that permission level, and each
set of grants runs once (from ``after_install`` or a patch), never on every migrate:
an administrator who later narrows or removes a rule in Role Permission Manager is
not overridden.
"""

import frappe
from frappe.permissions import add_permission, update_permission_property

CORE_GRANTS = (
	# EE-PERM-1: the reviewer of EE plans, filings and readiness evidence resolves the company.
	("Company", "ZA Compliance Reviewer", ("read",)),
)


def grant_permissions(grants) -> list[str]:
	"""Add each (doctype, role, rights) rule unless the role already has one at level 0."""
	added = []
	for doctype, role, rights in grants:
		if not frappe.db.exists("DocType", doctype) or not frappe.db.exists("Role", role):
			continue
		existing = {"parent": doctype, "role": role, "permlevel": 0, "if_owner": 0}
		if frappe.db.exists("Custom DocPerm", existing) or (
			not frappe.db.exists("Custom DocPerm", {"parent": doctype})
			and frappe.db.exists("DocPerm", existing)
		):
			continue
		add_permission(doctype, role, 0)
		for right in rights:
			update_permission_property(doctype, role, 0, right, 1, validate=False)
		frappe.clear_cache(doctype=doctype)
		added.append(f"{doctype}: {role}")
	return added


def grant_core_permissions() -> list[str]:
	return grant_permissions(CORE_GRANTS)
