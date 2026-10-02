import frappe

from za_local_core.services.calendar import sync_filing


def execute():
	"""Show filings made before the calendar link on the compliance calendar.

	Oldest first, so a cancelled filing releases its period before the amended
	filing that replaced it links itself.
	"""
	for name in frappe.get_all("ZA Filing", order_by="creation asc", pluck="name"):
		sync_filing(name)
