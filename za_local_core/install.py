"""Idempotent installation for the shared localisation foundation."""

import frappe

from za_local_core.dashboards import repair_metric_presentation, seed_dashboards
from za_local_core.migration.backfill import run as run_core_backfill
from za_local_core.migration.ownership import verify_checked_manifest
from za_local_core.navigation import sync_shared_navigation
from za_local_core.practitioner_guide.stage import unpublish_guides
from za_local_core.sa_vat.install import (
	VAT_CHARTS,
	VAT_MODULE,
	VAT_NUMBER_CARDS,
	apply_vat_setup,
	seed_vat_dashboards,
	seed_vat_readiness,
)

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
	run_core_backfill()
	seed_core_readiness()
	seed_core_dashboards()
	_setup_vat_module()
	sync_shared_navigation()


def after_migrate() -> None:
	verify_checked_manifest()
	ensure_core_roles()
	seed_core_readiness()
	seed_core_dashboards()
	repair_core_metrics()
	_setup_vat_module()
	sync_shared_navigation()


def repair_core_metrics(user_input: dict | None = None) -> dict:
	"""Restamp metric presentation from the currency in force now.

	Number Card and Dashboard Chart persist a currency on the record. Nothing
	corrected a wrong one on a fresh install: ``install_app`` marks every patch
	complete before it runs ``after_install``, so the repair patch could never
	execute, and ``seed_dashboards`` skips records that already exist. Whatever
	currency was resolvable during install was therefore permanent, and Frappe
	ships INR, so South African statutory figures rendered in rupees forever.

	Called from ``after_migrate`` and from ``setup_wizard_complete``, which is the
	first moment the real company currency is known. ``user_input`` is the setup
	wizard payload and is unused.
	"""
	return {
		CORE_MODULE: repair_metric_presentation(
			CORE_MODULE, cards=CORE_NUMBER_CARDS, charts=CORE_CHARTS
		),
		VAT_MODULE: repair_metric_presentation(VAT_MODULE, cards=VAT_NUMBER_CARDS, charts=VAT_CHARTS),
	}


def _setup_vat_module() -> None:
	"""Set up the SA VAT module this app absorbed from za_local_finance."""
	apply_vat_setup()
	seed_vat_readiness()
	seed_vat_dashboards()


def before_uninstall() -> None:
	"""Remove artefacts Frappe cannot reclaim by module.

	``remove_app`` deletes any record whose DocType links to Module Def, which
	covers this suite's Custom Fields, Property Setters, Print Formats, Pages and
	Workspaces. Role has no module field, and neither Wiki DocType has one, so
	those rows must be removed here or they outlive the app.

	Statutory and payroll business records are deliberately retained: an
	uninstall must not destroy a company's payroll history or filing evidence.
	"""
	remove_core_roles()
	unpublish_guides()


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


def remove_core_roles() -> None:
	"""Delete this app's roles, including their assignments to users."""
	for role_name, _description in CORE_ROLES:
		if frappe.db.exists("Role", role_name):
			frappe.delete_doc("Role", role_name, force=True, ignore_permissions=True)


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


CORE_MODULE = "SA Localisation Core"

CORE_NUMBER_CARDS = (
	{
		"label": "Filings Awaiting Approval",
		"document_type": "ZA Filing",
		"function": "Count",
		"filters": [["status", "in", ["Draft", "Reviewed"]]],
	},
	{
		"label": "Filings Rejected by an Authority",
		"document_type": "ZA Filing",
		"function": "Count",
		"filters": [["status", "=", "Rejected"]],
	},
	{
		"label": "Obligations Overdue",
		"document_type": "ZA Compliance Calendar Entry",
		"function": "Count",
		"filters": [["status", "=", "Overdue"]],
	},
	{
		"label": "Capabilities Not Yet Production",
		"document_type": "ZA Feature Readiness",
		"function": "Count",
		"filters": [["status", "in", ["Preview", "Controlled Manual", "Blocked"]]],
	},
	{
		"label": "Approved Statutory Rate Packs",
		"document_type": "ZA Statutory Rate Pack",
		"function": "Count",
		"filters": [["docstatus", "=", 1]],
	},
)

CORE_CHARTS = (
	{
		"chart_name": "SA Filings by Status",
		"chart_type": "Group By",
		"document_type": "ZA Filing",
		"group_by_type": "Count",
		"group_by_based_on": "status",
		"type": "Donut",
	},
	{
		"chart_name": "SA Compliance Calendar by Status",
		"chart_type": "Group By",
		"document_type": "ZA Compliance Calendar Entry",
		"group_by_type": "Count",
		"group_by_based_on": "status",
		"type": "Bar",
	},
	{
		"chart_name": "SA Capability Readiness by Domain",
		"chart_type": "Group By",
		"document_type": "ZA Feature Readiness",
		"group_by_type": "Count",
		"group_by_based_on": "domain",
		"type": "Bar",
	},
)


def seed_core_dashboards() -> dict:
	"""Create the SA Overview number cards and charts when missing."""
	return seed_dashboards(CORE_MODULE, cards=CORE_NUMBER_CARDS, charts=CORE_CHARTS, workspace="SA Overview")
