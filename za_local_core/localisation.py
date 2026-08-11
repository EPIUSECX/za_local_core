"""Country scope for the South African localisation suite.

This module is the single owner of the question "does South African
localisation apply here?". Domain apps must consult it before enforcing any
statutory rule, so a site that also runs companies outside South Africa keeps
stock Frappe, ERPNext and HRMS behaviour for those companies.
"""

from __future__ import annotations

import frappe

COUNTRY = "South Africa"


def is_south_african_company(company: str | None) -> bool:
	"""Return whether statutory South African rules apply to this company.

	An unknown or blank company returns ``False``. Localisation must never be
	the reason an incomplete document fails; the owning DocType reports its own
	missing mandatory fields.
	"""
	if not company:
		return False
	return frappe.db.get_value("Company", company, "country", cache=True) == COUNTRY


def get_south_african_companies() -> list[str]:
	"""Return every company on this site configured for South Africa."""
	return frappe.get_all("Company", filters={"country": COUNTRY}, pluck="name")


def resolve_south_african_companies(company: str | None = None) -> list[str]:
	"""Return the companies one seeding pass should cover.

	Install and migrate sweep the whole site and pass nothing. A Company insert
	hook passes the company it just created, and gets an empty list back when that
	company is not South African.
	"""
	if company is None:
		return get_south_african_companies()
	return [company] if is_south_african_company(company) else []
