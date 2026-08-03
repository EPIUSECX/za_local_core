import frappe


def execute() -> None:
	"""Force the SA Overview workspace back in from the app.

	The Documentation card and its link to the guide page arrive with this
	release. Frappe re-imports a standard workspace only when the file is newer
	than the record, and ``sync_shared_navigation`` re-saves this workspace on
	every migrate, so on an existing site the record is always the newer of the
	two and the new rows would never land.
	"""
	frappe.reload_doc("sa_localisation_core", "workspace", "sa_overview", force=True)
