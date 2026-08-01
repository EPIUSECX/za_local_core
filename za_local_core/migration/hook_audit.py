"""Runtime hook ownership audit used during side-by-side cutover."""

from __future__ import annotations

from collections import defaultdict

import frappe

CRITICAL_HOOKS = {
	"override_doctype_class": (
		"Salary Slip",
		"Payroll Entry",
		"Additional Salary",
		"Salary Structure Assignment",
		"Leave Application",
		"Employee Separation",
	),
	"doctype_js": (
		"Sales Invoice",
		"Purchase Invoice",
		"Payroll Entry",
		"Salary Structure",
		"COIDA Annual Return",
		"Workplace Injury",
		"OID Claim",
	),
}


def collect() -> dict:
	"""Return all app-specific owners for the critical cutover hooks."""
	result: dict[str, dict[str, list[dict]]] = {}
	for hook_name, targets in CRITICAL_HOOKS.items():
		owners: dict[str, list[dict]] = defaultdict(list)
		for app in frappe.get_installed_apps():
			values = frappe.get_hooks(hook_name, app_name=app) or {}
			if not isinstance(values, dict):
				continue
			for target in targets:
				if target in values:
					owners[target].append({"app": app, "handler": values[target]})
		result[hook_name] = dict(owners)

	result["journal_entry_events"] = _collect_doc_event("Journal Entry", ("on_trash", "on_cancel"))
	result["scheduler"] = _collect_scheduler()
	return result


def assert_unique() -> dict:
	"""Fail when a critical runtime hook has more than one active owner."""
	audit = collect()
	duplicates = []
	for hook_name in (*CRITICAL_HOOKS, "journal_entry_events"):
		for target, owners in audit[hook_name].items():
			if len(owners) > 1:
				duplicates.append(f"{hook_name}.{target}: {owners}")
	if duplicates:
		frappe.throw("Duplicate localisation runtime hooks:<br>" + "<br>".join(duplicates))
	return audit


def _collect_doc_event(doctype: str, events: tuple[str, ...]) -> dict[str, list[dict]]:
	owners: dict[str, list[dict]] = defaultdict(list)
	for app in frappe.get_installed_apps():
		if not app.startswith("za_local"):
			continue
		values = frappe.get_hooks("doc_events", app_name=app) or {}
		for event, handler in (values.get(doctype) or {}).items():
			if event in events:
				owners[event].append({"app": app, "handler": handler})
	return dict(owners)


def _collect_scheduler() -> dict[str, list[dict]]:
	owners: dict[str, list[dict]] = defaultdict(list)
	for app in frappe.get_installed_apps():
		values = frappe.get_hooks("scheduler_events", app_name=app) or {}
		for frequency, handlers in values.items():
			for handler in handlers or ():
				if handler.startswith(("za_local.", "za_local_")):
					owners[handler].append({"app": app, "frequency": frequency})
	return dict(owners)
