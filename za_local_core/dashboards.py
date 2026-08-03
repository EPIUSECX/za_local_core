"""Seed the localisation workspaces' number cards and charts.

Every domain app declares its own metrics and calls :func:`seed_dashboards` from
its install and migrate hooks. Seeding is idempotent and fail-safe: a metric
whose DocType, field or report is not present on this site is skipped rather
than created broken, and an existing record is never overwritten, so a site
administrator's edits survive a migrate.

Records carry the declaring module so ``bench uninstall-app`` reclaims them.
"""

from __future__ import annotations

import json

import frappe

CARD_DOCTYPE = "Number Card"
CHART_DOCTYPE = "Dashboard Chart"


def seed_dashboards(
	module: str,
	cards: tuple[dict, ...] = (),
	charts: tuple[dict, ...] = (),
	workspace: str | None = None,
) -> dict:
	"""Create any missing number cards and charts for one module.

	When ``workspace`` is given, the surviving metrics are also attached to it.
	"""
	created = {"cards": [], "charts": [], "skipped": []}
	if not _schema_available():
		return created

	for spec in cards:
		name = ensure_number_card(module, spec)
		(created["cards"] if name else created["skipped"]).append(spec["label"])
	for spec in charts:
		name = ensure_dashboard_chart(module, spec)
		(created["charts"] if name else created["skipped"]).append(spec["chart_name"])

	if workspace:
		attach_to_workspace(workspace, cards=created["cards"], charts=created["charts"])
	return created


def attach_to_workspace(workspace: str, cards: list[str], charts: list[str]) -> None:
	"""Show the given metrics on a workspace, adding only what is missing.

	The workspace file already declares these, but Frappe re-imports a standard
	record only when the file is newer than the database, and shared-navigation
	sync re-saves workspaces on every migrate. Converging here keeps an existing
	site correct without depending on clock comparisons.
	"""
	if not frappe.db.exists("Workspace", workspace):
		return

	doc = frappe.get_doc("Workspace", workspace)
	blocks = json.loads(doc.content or "[]")
	present_cards = {row.number_card_name for row in doc.number_cards}
	present_charts = {row.chart_name for row in doc.charts}
	shown = {
		block["data"].get("number_card_name") or block["data"].get("chart_name")
		for block in blocks
		if block.get("type") in ("number_card", "chart")
	}
	added = []

	for card in cards:
		if card not in present_cards:
			doc.append("number_cards", {"number_card_name": card, "label": card})
		if card not in shown:
			added.append(
				{
					"id": frappe.generate_hash(length=10),
					"type": "number_card",
					"data": {"number_card_name": card, "col": 4},
				}
			)
	for chart in charts:
		if chart not in present_charts:
			doc.append("charts", {"chart_name": chart, "label": chart})
		if chart not in shown:
			added.append(
				{
					"id": frappe.generate_hash(length=10),
					"type": "chart",
					"data": {"chart_name": chart, "col": 6},
				}
			)

	if not added and len(doc.number_cards) == len(present_cards) and len(doc.charts) == len(present_charts):
		return

	doc.content = json.dumps(added + blocks)
	doc.flags.ignore_permissions = True
	doc.save(ignore_permissions=True)


def ensure_number_card(module: str, spec: dict) -> str | None:
	"""Create one number card when its inputs exist and it is not already there."""
	label = spec["label"]
	if frappe.db.exists(CARD_DOCTYPE, label):
		return label
	if not _inputs_available(spec):
		return None

	card = frappe.new_doc(CARD_DOCTYPE)
	card.update(
		{
			"label": label,
			"type": spec.get("type", "Document Type"),
			"document_type": spec.get("document_type"),
			"function": spec.get("function", "Count"),
			"aggregate_function_based_on": spec.get("aggregate_function_based_on"),
			"filters_json": json.dumps(spec.get("filters") or []),
			"is_public": 1,
			"show_percentage_stats": 0,
			"module": module,
			"is_standard": 0,
		}
	)
	card.insert(ignore_permissions=True)
	return card.name


def ensure_dashboard_chart(module: str, spec: dict) -> str | None:
	"""Create one dashboard chart when its inputs exist and it is not already there."""
	chart_name = spec["chart_name"]
	if frappe.db.exists(CHART_DOCTYPE, chart_name):
		return chart_name
	if not _inputs_available(spec):
		return None

	chart = frappe.new_doc(CHART_DOCTYPE)
	chart.update(
		{
			"chart_name": chart_name,
			"chart_type": spec.get("chart_type", "Group By"),
			"document_type": spec.get("document_type"),
			"report_name": spec.get("report_name"),
			"use_report_chart": spec.get("use_report_chart", 0),
			"x_field": spec.get("x_field"),
			"group_by_type": spec.get("group_by_type"),
			"group_by_based_on": spec.get("group_by_based_on"),
			"aggregate_function_based_on": spec.get("aggregate_function_based_on"),
			"based_on": spec.get("based_on"),
			"time_interval": spec.get("time_interval", "Monthly"),
			"timespan": spec.get("timespan", "Last Year"),
			"type": spec.get("type", "Bar"),
			"filters_json": json.dumps(spec.get("filters") or []),
			"is_public": 1,
			"module": module,
			"is_standard": 0,
		}
	)
	for column in spec.get("y_axis") or []:
		chart.append("y_axis", column)
	chart.insert(ignore_permissions=True)
	return chart.name


def _schema_available() -> bool:
	return frappe.db.exists("DocType", CARD_DOCTYPE) and frappe.db.exists("DocType", CHART_DOCTYPE)


def _inputs_available(spec: dict) -> bool:
	"""Whether every DocType, report and field this metric reads is present."""
	report = spec.get("report_name")
	if report and not frappe.db.exists("Report", report):
		return False

	doctype = spec.get("document_type")
	if not doctype:
		return bool(report)
	if not frappe.db.exists("DocType", doctype):
		return False

	meta = frappe.get_meta(doctype)
	fields = [
		spec.get("aggregate_function_based_on"),
		spec.get("based_on"),
		spec.get("group_by_based_on"),
		spec.get("x_field"),
	]
	fields.extend(condition[0] for condition in spec.get("filters") or [])
	fields.extend(column.get("y_field") for column in spec.get("y_axis") or [])
	return all(_field_present(meta, fieldname) for fieldname in fields if fieldname)


def _field_present(meta, fieldname: str) -> bool:
	return fieldname in frappe.model.default_fields or bool(meta.get_field(fieldname))
