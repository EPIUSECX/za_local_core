"""Take over the SA VAT module from za_local_finance.

The module moved into this app unchanged: same name, same DocTypes, same tables.
Only the owning app differs, so this re-points the Module Def and Workspace
records and then de-registers the old app.

The old app is dropped with ``remove_from_installed_apps`` rather than
``bench uninstall-app``, because ``remove_app`` would delete every DocType it
owned and take the customer's VAT201 returns and tax-document history with it.
Nothing is deleted here except the empty module the retired app declared but
never used.
"""

import frappe
from frappe.installer import remove_from_installed_apps

RETIRED_APP = "za_local_finance"
RETIRED_EMPTY_MODULE = "SA Localisation Finance"


def execute() -> None:
	from za_local_core.sa_vat.install import claim_vat_module_ownership

	claim_vat_module_ownership()
	drop_unused_module()
	if RETIRED_APP in frappe.get_installed_apps():
		remove_from_installed_apps(RETIRED_APP)


def drop_unused_module() -> None:
	"""Remove the placeholder module the retired app declared but never populated.

	It is deleted only when nothing references it, so a site that somehow put
	records there keeps them and the module.
	"""
	if not frappe.db.exists("Module Def", RETIRED_EMPTY_MODULE):
		return
	for doctype in ("DocType", "Report", "Print Format", "Workspace", "Number Card", "Dashboard Chart"):
		if frappe.db.exists(doctype, {"module": RETIRED_EMPTY_MODULE}):
			return
	frappe.delete_doc("Module Def", RETIRED_EMPTY_MODULE, ignore_permissions=True)
