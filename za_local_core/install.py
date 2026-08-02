"""Idempotent installation for the shared localisation foundation."""

import frappe

from za_local_core.navigation import sync_shared_navigation

CORE_ROLES = (
	("ZA Compliance User", "Prepare South African compliance working papers"),
	("ZA Compliance Reviewer", "Review South African compliance working papers"),
	("ZA Compliance Manager", "Approve South African compliance configuration and filings"),
)

CORE_FEATURES = (
	(
		"STATUTORY-GOVERNANCE",
		"Statutory source, rate and filing governance",
		"Core",
		"Controlled Manual",
		"A designated reviewer must approve source evidence, effective dates and each production feature.",
	),
	(
		"POPIA-PAIA-GOVERNANCE",
		"POPIA and PAIA governance registers and case workflows",
		"POPIA and PAIA",
		"Controlled Manual",
		"The app records controls and evidence; regulator submissions, legal interpretation and incident notification decisions remain accountable-person duties.",
	),
)


def after_install() -> None:
	ensure_core_roles()
	seed_core_readiness()
	sync_shared_navigation()


def after_migrate() -> None:
	ensure_core_roles()
	seed_core_readiness()
	sync_shared_navigation()


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


def seed_core_readiness() -> None:
	"""Create conservative core capability records for South African companies."""
	if not frappe.db.exists("DocType", "ZA Feature Readiness"):
		return
	companies = frappe.get_all("Company", filters={"country": "South Africa"}, pluck="name")
	for company in companies:
		for feature_code, feature_name, domain, status, limitation in CORE_FEATURES:
			key = f"{company}|{feature_code}"
			if frappe.db.exists("ZA Feature Readiness", key):
				continue
			frappe.get_doc(
				{
					"doctype": "ZA Feature Readiness",
					"company": company,
					"feature_code": feature_code,
					"feature_name": feature_name,
					"domain": domain,
					"status": status,
					"blocking_reason": limitation,
					"remediation_route": "Complete accountable-person review and attach approval evidence.",
				}
			).insert(ignore_permissions=True)
