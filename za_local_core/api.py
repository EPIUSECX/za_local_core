"""Permission-aware core APIs."""

from __future__ import annotations

import frappe


def has_app_permission() -> bool:
	"""Show the shared shell when the user can access any installed SA domain."""
	if frappe.session.user == "Administrator":
		return True
	roles = set(frappe.get_roles())
	if roles & {
		"System Manager",
		"ZA Compliance User",
		"ZA Compliance Reviewer",
		"ZA Compliance Manager",
	}:
		return True

	for doctype in (
		"South Africa VAT Settings",
		"Salary Slip",
		"Business Trip",
		"Workplace Injury",
		"COIDA Annual Return",
	):
		if frappe.db.exists("DocType", doctype) and frappe.has_permission(doctype, "read"):
			return True
	return False


@frappe.whitelist()
def get_company_readiness(company: str) -> list[dict]:
	"""Return capability labels after enforcing Company read permission."""
	if not isinstance(company, str) or not company.strip():
		raise TypeError("company must be a non-empty string")
	frappe.has_permission("Company", doc=company, ptype="read", throw=True)
	return frappe.get_list(
		"ZA Feature Readiness",
		filters={"company": company},
		fields=["feature_code", "feature_name", "domain", "status", "blocking_reason", "remediation_route"],
		order_by="domain, feature_code",
	)
