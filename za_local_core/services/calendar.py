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


# A filing's own state, as the calendar shows it. A rejected or amended filing
# still has work outstanding, so its period is back in progress.
FILING_CALENDAR_STATUS = {
	"Draft": "In Progress",
	"Reviewed": "In Progress",
	"Approved": "Approved",
	"Filed": "Filed",
	"Accepted": "Accepted",
	"Rejected": "In Progress",
	"Amended": "In Progress",
}


def sync_filing(filing: str) -> str | None:
	"""Show a filing on the compliance calendar for its company, obligation and period.

	The calendar entry is created when the period has none, linked to the filing
	and given the filing's state. When the linked filing is cancelled the entry
	is released: Open again, or Overdue once its due date has passed, until the
	amended filing links itself.
	"""
	values = frappe.db.get_value(
		"ZA Filing",
		filing,
		["company", "obligation", "period_start", "period_end", "due_date", "status"],
		as_dict=True,
	)
	if not values or not all((values.company, values.obligation, values.period_start, values.period_end)):
		return None

	entry = ensure_entry(
		values.company,
		values.obligation,
		values.period_start,
		values.period_end,
		values.due_date or values.period_end,
	)
	current = frappe.db.get_value("ZA Compliance Calendar Entry", entry, ["filing", "due_date"], as_dict=True)
	if values.status == "Cancelled":
		if current.filing != filing:
			return entry
		overdue = current.due_date and getdate(current.due_date) < getdate(today())
		update = {"filing": None, "status": "Overdue" if overdue else "Open"}
	else:
		update = {"filing": filing, "status": FILING_CALENDAR_STATUS.get(values.status, "In Progress")}
		if values.due_date:
			update["due_date"] = values.due_date
	frappe.db.set_value("ZA Compliance Calendar Entry", entry, update, update_modified=False)
	return entry


def sync_filing_event(doc, method=None) -> None:
	"""Document-event adapter for ZA Filing and ZA Submission Receipt."""
	sync_filing(doc.filing if doc.doctype == "ZA Submission Receipt" else doc.name)


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
