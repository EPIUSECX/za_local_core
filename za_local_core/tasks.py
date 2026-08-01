"""Bounded, idempotent shared compliance tasks."""

import frappe

from za_local_core.services.calendar import mark_overdue_entries


def daily() -> None:
	try:
		marked = mark_overdue_entries()
		if marked:
			frappe.logger("za_local_core").info("Marked %s compliance calendar entries overdue", marked)
	except Exception:
		frappe.log_error(title="ZA compliance calendar update failed", message=frappe.get_traceback())
		raise
