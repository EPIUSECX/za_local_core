"""Shared company fixtures for the localisation test suites.

Tests must provision what they depend on. Each app's CI site installs only that
app's dependency chain and holds no company, so a suite that assumes one is
already present fails in setUp before it asserts anything.
"""

from __future__ import annotations

import frappe

from za_local_core.localisation import COUNTRY

TEST_COMPANY = "_ZA Core Test Company"


def ensure_south_african_company() -> str:
	"""Return a South African company, creating a test one when none exists."""
	existing = frappe.get_all("Company", filters={"country": COUNTRY}, pluck="name", limit=1)
	if existing:
		return existing[0]
	return ensure_company(TEST_COMPANY, "ZACT", COUNTRY, "ZAR")


def ensure_company(company_name: str, abbr: str, country: str, currency: str) -> str:
	"""Create a company for tests, including the masters ERPNext expects."""
	if frappe.db.exists("Company", company_name):
		return company_name

	_ensure_erpnext_setup_fixtures()
	company = frappe.new_doc("Company")
	company.company_name = company_name
	company.abbr = abbr
	company.country = country
	company.default_currency = currency
	template = frappe.db.get_value("Company", {}, "name", order_by="creation asc")
	if template:
		company.create_chart_of_accounts_based_on = "Existing Company"
		company.existing_company = template
	company.insert(ignore_permissions=True)
	return company_name


def ensure_gender(gender: str) -> str:
	"""Return a Gender record, creating it when the setup wizard never ran."""
	if not frappe.db.exists("Gender", gender):
		frappe.get_doc({"doctype": "Gender", "gender": gender}).insert(ignore_permissions=True)
	return gender


def _ensure_erpnext_setup_fixtures() -> None:
	"""Install the ERPNext masters a Company needs but `install-app` does not create.

	Company creation links records such as Warehouse Type "Transit" that ERPNext
	ships through its setup wizard. A CI site never runs that wizard.
	"""
	if frappe.db.exists("Warehouse Type", "Transit"):
		return
	from erpnext.setup.setup_wizard.operations.install_fixtures import install

	install(COUNTRY)
