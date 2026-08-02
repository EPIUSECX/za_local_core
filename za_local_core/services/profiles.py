"""Date-effective company compliance profile resolution for domain apps."""

import frappe
from frappe import _
from frappe.utils import getdate


def resolve_company_profile(company: str, on_date: str) -> dict:
	"""Return exactly one approved profile for a company and transaction date."""
	if not isinstance(company, str) or not company.strip():
		raise TypeError("company must be a non-empty string")
	date_value = getdate(on_date)
	profile = frappe.qb.DocType("ZA Company Compliance Profile")
	rows = (
		frappe.qb.from_(profile)
		.select(
			profile.name,
			profile.company,
			profile.effective_from,
			profile.effective_to,
			profile.review_checksum,
			profile.vat_registered,
			profile.paye_registered,
			profile.uif_registered,
			profile.sdl_registered,
			profile.coida_registered,
			profile.employment_equity_designated,
			profile.seta,
			profile.bargaining_council,
			profile.coida_industry_class,
			profile.filing_contact,
		)
		.where(profile.company == company.strip())
		.where(profile.docstatus == 1)
		.where(profile.status == "Approved")
		.where(profile.enabled == 1)
		.where(profile.effective_from <= date_value)
		.where((profile.effective_to.isnull()) | (profile.effective_to >= date_value))
	).run(as_dict=True)
	if not rows:
		frappe.throw(
			_("No approved compliance profile for {0} applies on {1}.").format(company, date_value),
			title=_("Missing Company Compliance Profile"),
		)
	if len(rows) > 1:
		frappe.throw(
			_("Multiple approved compliance profiles for {0} apply on {1}.").format(company, date_value),
			title=_("Overlapping Company Compliance Profiles"),
		)
	row = rows[0]
	row.effective_from = str(row.effective_from)
	row.effective_to = str(row.effective_to or "")
	return dict(row)
