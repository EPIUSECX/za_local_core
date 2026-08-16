"""Install and migrate steps for the SA VAT module.

These arrived from the separate ``za_local_finance`` app, which is retired. They
live inside the module they configure rather than in the app's ``install.py``,
which orchestrates them.
"""

import frappe

from za_local_core.dashboards import seed_dashboards
from za_local_core.localisation import resolve_south_african_companies
from za_local_core.sa_vat.setup import (
	backfill_vat201_active_period_keys,
	backfill_vat201_filing_categories,
	backfill_vat_settings_filing_categories,
	ensure_vat_custom_fields,
	migrate_legacy_vat_account_rows,
	seed_vat_vendor_types,
)
from za_local_core.sa_vat.statutory import (
	CURRENT_APPROVED_SOURCE_METADATA,
	VAT_CONTROL_RULE_KEYS,
	VAT_CONTROL_UNITS,
	VAT_DOMAIN,
)

# The catalogued SARS window. A pack must be closed-ended, so the year it was
# published for is the honest boundary; the next period gets its own reviewed pack.
VAT_PACK_EFFECTIVE_FROM = "2026-04-01"
VAT_PACK_EFFECTIVE_TO = "2027-03-31"

VAT_MODULES = ("SA VAT",)

VAT_FEATURES = (
	(
		"VAT201-WORKING-PAPER",
		"VAT201 preparation and reconciliation",
		"VAT",
		"Controlled Manual",
		"The app prepares and reconciles the working paper; portal filing and the SARS receipt remain manual.",
	),
	(
		"VAT-TAX-DOCUMENTS",
		"South African tax invoice and credit/debit note controls",
		"VAT",
		"Preview",
		"A VAT practitioner must approve the company configuration and representative rendered documents.",
	),
	(
		"CORPORATE-TAX",
		"Corporate income and provisional tax working papers",
		"Corporate Tax",
		"Preview",
		"No ITR14 or IRP6 electronic filing interface is implemented; practitioner-controlled working papers are required.",
	),
	(
		"CIPC",
		"CIPC annual-return and beneficial-ownership compliance",
		"CIPC",
		"Controlled Manual",
		"CIPC portal filing and acceptance evidence must be completed and attached manually.",
	),
)


def apply_vat_setup() -> None:
	"""Apply non-destructive VAT schema defaults and claim module ownership.

	Navigation is not synced here. The app's ``after_install`` and ``after_migrate``
	both sync once after every module's setup has run, and patches run before those
	hooks, so a sync inside this function would only be repeated work.
	"""
	claim_vat_module_ownership()
	ensure_vat_custom_fields()
	backfill_vat_settings_filing_categories()
	seed_vat_dashboards()
	backfill_vat201_filing_categories()
	backfill_vat201_active_period_keys()
	seed_vat_vendor_types()
	seed_vat_statutory_rate_pack(seed_vat_statutory_source_catalog())
	migrate_legacy_vat_account_rows()
	seed_vat_readiness()


def seed_vat_statutory_source_catalog() -> str:
	"""Create current SARS VAT catalogue metadata as an unapproved draft only."""
	catalog_key = "SARS-VAT-CONTROLS-2026-04-01"
	existing = frappe.db.get_value("ZA Statutory Source", {"catalog_key": catalog_key}, "name")
	if existing:
		return existing

	metadata = CURRENT_APPROVED_SOURCE_METADATA
	doc = frappe.get_doc(
		{
			"doctype": "ZA Statutory Source",
			"catalog_key": catalog_key,
			"authority": metadata["authority"],
			"title": "SARS VAT controls effective 1 April 2026",
			"document_type": "SARS VAT guidance catalogue",
			"version": "2026-04-01",
			"publication_date": "2026-02-25",
			"effective_from": metadata["effective_from"],
			"source_url": metadata["registration_source_url"],
			"notes": (
				"DRAFT CATALOGUE METADATA ONLY. Retrieve the official SARS evidence privately, "
				"obtain independent review and approve a matching rate pack.\n"
				"Records the 15% standard rate, compulsory registration at R2,300,000 and "
				"voluntary registration at R120,000, all effective 1 April 2026. The two "
				"registration thresholds were raised from R1,000,000 and R50,000 by the Budget "
				"of 25 February 2026, amending section 23 of the Value-Added Tax Act 89 of 1991. "
				"Confirm the amending Act against the Government Gazette: SARS states the amounts "
				"but cites no legal instrument.\n"
				f"Registration source: {metadata['registration_source_url']}\n"
				f"Budget announcement: {metadata['announcement_source_url']}\n"
				f"Tax invoice source: {metadata['invoice_source_url']}\n"
				f"VAT rate source: {metadata['rate_source_url']}"
			),
			"status": "Draft",
		}
	).insert(ignore_permissions=True)
	return doc.name


def seed_vat_statutory_rate_pack(source: str | None) -> str | None:
	"""Pre-populate the rate pack the reviewer approves, as an unapproved draft.

	VAT cannot be configured until one approved pack answers all five control keys,
	and hand-entering them is where a practitioner either gives up or invents a
	number. Shipping the draft moves the work from transcription to review while
	leaving every part of the control intact: the pack stays ``docstatus=0``, it
	cannot be submitted until its source is approved, and the source cannot be
	approved without privately attached SARS evidence whose SHA-256 matches.
	"""
	if not source or not frappe.db.exists("DocType", "ZA Statutory Rate Pack"):
		return None

	existing = frappe.db.get_value(
		"ZA Statutory Rate Pack",
		{
			"domain": VAT_DOMAIN,
			"effective_from": VAT_PACK_EFFECTIVE_FROM,
			"docstatus": ("<", 2),
		},
		"name",
	)
	if existing:
		return existing

	# A practitioner may already own a pack across this window. Overlapping packs are
	# rejected on validate, and an install is the wrong place to raise that.
	if _overlapping_vat_pack_exists():
		return None

	values = CURRENT_APPROVED_SOURCE_METADATA["expected_current_values"]
	return (
		frappe.get_doc(
			{
				"doctype": "ZA Statutory Rate Pack",
				"domain": VAT_DOMAIN,
				"title": "SARS VAT controls 1 April 2026 to 31 March 2027",
				"source": source,
				"effective_from": VAT_PACK_EFFECTIVE_FROM,
				"effective_to": VAT_PACK_EFFECTIVE_TO,
				"notes": (
					"DRAFT PREPARED BY za_local_core. Not approved, and not usable until it is.\n\n"
					"Check every value below against the SARS evidence attached to the linked "
					"statutory source, set Reviewed By to yourself and submit. Approval must come "
					"from a user holding ZA Compliance Reviewer or ZA Compliance Manager who did "
					"not create this document.\n\n"
					"The window ends 31 March 2027 deliberately: a later period needs its own "
					"reviewed pack, never an extended end date."
				),
				"items": [
					{
						"rule_key": rule_key,
						"numeric_value": values[rule_key],
						"unit": VAT_CONTROL_UNITS[rule_key],
						"precision": 2,
					}
					for rule_key in VAT_CONTROL_RULE_KEYS
				],
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def _overlapping_vat_pack_exists() -> bool:
	pack = frappe.qb.DocType("ZA Statutory Rate Pack")
	return bool(
		(
			frappe.qb.from_(pack)
			.select(pack.name)
			.where(pack.domain == VAT_DOMAIN)
			.where(pack.docstatus < 2)
			.where(pack.effective_from <= VAT_PACK_EFFECTIVE_TO)
			.where(pack.effective_to >= VAT_PACK_EFFECTIVE_FROM)
			.limit(1)
		).run(pluck=True)
	)


def claim_vat_module_ownership() -> None:
	"""Move existing Module Def ownership without renaming any DocType or table."""
	for module_name in VAT_MODULES:
		if not frappe.db.exists("Module Def", module_name):
			continue
		current_owner = frappe.db.get_value("Module Def", module_name, "app_name")
		if current_owner != "za_local_core":
			frappe.db.set_value(
				"Module Def",
				module_name,
				"app_name",
				"za_local_core",
				update_modified=False,
			)

	if frappe.db.exists("Workspace", "SA VAT"):
		frappe.db.set_value(
			"Workspace",
			"SA VAT",
			"app",
			"za_local_core",
			update_modified=False,
		)


def seed_vat_readiness(company: str | None = None) -> None:
	"""Advertise finance capabilities conservatively without overwriting sign-off."""
	if not frappe.db.exists("DocType", "ZA Feature Readiness"):
		return
	for company_name in resolve_south_african_companies(company):
		for feature_code, feature_name, domain, status, limitation in VAT_FEATURES:
			key = f"{company_name}|{feature_code}"
			if frappe.db.exists("ZA Feature Readiness", key):
				continue
			frappe.get_doc(
				{
					"doctype": "ZA Feature Readiness",
					"company": company_name,
					"feature_code": feature_code,
					"feature_name": feature_name,
					"domain": domain,
					"status": status,
					"blocking_reason": limitation,
					"remediation_route": "Complete the practitioner sign-off checklist and attach filing evidence.",
				}
			).insert(ignore_permissions=True)


VAT_MODULE = "SA VAT"

VAT_NUMBER_CARDS = (
	{
		"label": "Output VAT (Submitted Returns)",
		"document_type": "VAT201 Return",
		"function": "Sum",
		"aggregate_function_based_on": "total_output_tax",
		"filters": [["docstatus", "=", 1]],
	},
	{
		"label": "Input VAT (Submitted Returns)",
		"document_type": "VAT201 Return",
		"function": "Sum",
		"aggregate_function_based_on": "total_input_tax",
		"filters": [["docstatus", "=", 1]],
	},
	{
		"label": "VAT Payable (Submitted Returns)",
		"document_type": "VAT201 Return",
		"function": "Sum",
		"aggregate_function_based_on": "total_amount_payable",
		"filters": [["docstatus", "=", 1]],
	},
	{
		"label": "VAT201 Returns Awaiting Approval",
		"document_type": "VAT201 Return",
		"function": "Count",
		"filters": [["status", "in", ["Draft", "Prepared"]]],
	},
	{
		"label": "VAT201 Returns Needing Reconciliation Review",
		"document_type": "VAT201 Return",
		"function": "Count",
		"filters": [["reconciliation_status", "=", "Needs Review"]],
	},
)

VAT_CHARTS = (
	{
		"chart_name": "SA VAT Payable by Period",
		"chart_type": "Sum",
		"document_type": "VAT201 Return",
		"based_on": "to_date",
		"aggregate_function_based_on": "total_amount_payable",
		"time_interval": "Monthly",
		"timespan": "Last Year",
		"type": "Bar",
		"filters": [["docstatus", "=", 1]],
	},
	{
		"chart_name": "SA VAT201 Returns by Status",
		"chart_type": "Group By",
		"document_type": "VAT201 Return",
		"group_by_type": "Count",
		"group_by_based_on": "status",
		"type": "Donut",
	},
	# The only shipped report that runs without a mandatory Company filter.
	{
		"chart_name": "SA VAT by Classification",
		"chart_type": "Report",
		"report_name": "VAT Analysis",
		"use_report_chart": 1,
		"type": "Bar",
	},
)


def seed_vat_dashboards() -> dict:
	"""Create the SA VAT number cards and charts when missing."""
	return seed_dashboards(VAT_MODULE, cards=VAT_NUMBER_CARDS, charts=VAT_CHARTS, workspace="SA VAT")
