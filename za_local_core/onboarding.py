"""Keep the localisation setup checklists in step with the work actually done.

Frappe ticks an onboarding step only when the user follows it from the checklist:
a "Create Entry" step completes when a record is saved from the form the step
opens. A site configured from the forms directly, or by data migration, therefore
shows "Create a VAT201 Return" outstanding beside a filed VAT201, and the
checklist misstates the state of the configuration.

A "Create Entry" step here is complete once a record of its DocType exists. The
record is the evidence. Review steps ("Review", "Approve", "View") are left to
the person who opens them, because only that person can say they reviewed it.
"""

from __future__ import annotations

import json
from pathlib import Path

import frappe

APPS = ("za_local_core", "za_local_payroll")
CACHE_KEY = "za_onboarding_create_entry_doctypes"


def localisation_onboardings() -> list[str]:
	"""Module Onboarding records owned by the localisation apps."""
	modules = frappe.get_all("Module Def", filters={"app_name": ["in", APPS]}, pluck="name")
	if not modules:
		return []
	return frappe.get_all("Module Onboarding", filters={"module": ["in", modules]}, pluck="name")


def _create_entry_steps() -> dict[str, list[str]]:
	"""Map each DocType to the localisation "Create Entry" steps that create it."""
	steps: dict[str, list[str]] = {}
	for onboarding in localisation_onboardings():
		for name in frappe.get_all("Onboarding Step Map", filters={"parent": onboarding}, pluck="step"):
			step = frappe.db.get_value(
				"Onboarding Step", name, ["action", "reference_document"], as_dict=True
			)
			if step and step.action == "Create Entry" and step.reference_document:
				steps.setdefault(step.reference_document, []).append(name)
	return steps


PRESENTATION_FIELDS = ("title", "action_label", "description", "reference_report", "path")


def refresh_step_presentation() -> list[str]:
	"""Bring the wording of shipped checklist steps up to date without touching progress.

	Frappe re-imports a standard record only when its file is newer than the row,
	and ticking a step rewrites the row, so on any site where someone has used a
	checklist a later release's corrected wording never arrives. Only the fields a
	user reads are copied; completion and skip state stay as they are.
	"""
	changed = []
	for app in APPS:
		if app not in frappe.get_installed_apps():
			continue
		for path in Path(frappe.get_app_path(app)).glob("*/onboarding_step/*/*.json"):
			spec = json.loads(path.read_text(encoding="utf-8"))
			name = spec.get("name")
			if spec.get("doctype") != "Onboarding Step" or not frappe.db.exists("Onboarding Step", name):
				continue
			current = frappe.db.get_value("Onboarding Step", name, PRESENTATION_FIELDS, as_dict=True)
			update = {
				field: spec.get(field)
				for field in PRESENTATION_FIELDS
				if (spec.get(field) or None) != (current.get(field) or None)
			}
			if update:
				frappe.db.set_value("Onboarding Step", name, update, update_modified=False)
				changed.append(name)
	return changed


def create_entry_doctypes() -> set[str]:
	return set(frappe.cache.get_value(CACHE_KEY, lambda: sorted(_create_entry_steps())) or ())


def sync_onboarding_progress() -> list[str]:
	"""Tick every "Create Entry" step whose record already exists. Returns the steps ticked."""
	ticked = []
	for doctype, steps in _create_entry_steps().items():
		if not frappe.db.exists("DocType", doctype):
			continue
		if not frappe.db.exists(doctype, {"docstatus": ["<", 2]}):
			continue
		for step in steps:
			if not frappe.db.get_value("Onboarding Step", step, "is_complete"):
				frappe.db.set_value("Onboarding Step", step, "is_complete", 1, update_modified=False)
				ticked.append(step)
	frappe.cache.delete_value(CACHE_KEY)
	return ticked


def mark_created(doc, method=None) -> None:
	"""Document-event hook: a record created anywhere completes its checklist step."""
	if doc.doctype not in create_entry_doctypes():
		return
	for step in _create_entry_steps().get(doc.doctype, ()):
		if not frappe.db.get_value("Onboarding Step", step, "is_complete"):
			frappe.db.set_value("Onboarding Step", step, "is_complete", 1, update_modified=False)
