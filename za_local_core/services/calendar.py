"""Idempotent compliance-calendar operations."""

from __future__ import annotations

import frappe
from frappe.utils import getdate, today


def ensure_entry(
	company: str,
	obligation: str,
	period_start: str,
	period_end: str,
	due_date: str,
) -> str:
	"""Create or return one calendar entry for a company obligation period."""
	calendar_key = "|".join((company, obligation, str(period_start), str(period_end)))
	if existing := frappe.db.exists("ZA Compliance Calendar Entry", calendar_key):
		return existing
	entry = frappe.get_doc(
		{
			"doctype": "ZA Compliance Calendar Entry",
			"company": company,
			"obligation": obligation,
			"period_start": period_start,
			"period_end": period_end,
			"due_date": due_date,
		}
	).insert(ignore_permissions=True)
	return entry.name


def mark_overdue_entries(reference_date: str | None = None) -> int:
	"""Mark open entries overdue without re-notifying or changing completed entries."""
	reference_date = getdate(reference_date or today())
	entries = frappe.get_all(
		"ZA Compliance Calendar Entry",
		filters={"status": ["in", ("Open", "In Progress")], "due_date": ["<", reference_date]},
		pluck="name",
	)
	for name in entries:
		frappe.db.set_value("ZA Compliance Calendar Entry", name, "status", "Overdue", update_modified=False)
	return len(entries)
