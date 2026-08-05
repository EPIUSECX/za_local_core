"""Shared preconditions for the VAT integration tests."""

import frappe


def get_configured_vat_company() -> str | None:
	"""A South African company that actually has VAT Settings, or None.

	Picking the first South African company is not enough. Test runs commit
	fixture companies, so a later run on the same site can pick one that was
	never given VAT Settings, and the VAT code then throws instead of the test
	skipping. Requiring the settings makes these tests re-runnable.
	"""
	return next(
		(
			company
			for company in frappe.get_all("Company", filters={"country": "South Africa"}, pluck="name")
			if frappe.db.exists("South Africa VAT Settings", {"company": company})
		),
		None,
	)
