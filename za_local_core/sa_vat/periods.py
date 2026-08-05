"""South African VAT filing-category and period validation."""

from __future__ import annotations

import hashlib

import frappe
from frappe import _
from frappe.utils import add_months, get_first_day, get_last_day, getdate

FILING_CATEGORIES = ("Category A", "Category B", "Category C", "Category D", "Category E")
LEGACY_PERIOD_BY_CATEGORY = {
	"Category A": "Bi-Monthly",
	"Category B": "Bi-Monthly",
	"Category C": "Monthly",
	"Category D": "Six-Monthly",
	"Category E": "Annually",
}


def infer_legacy_filing_category(legacy_period: str | None, from_date=None, to_date=None) -> str | None:
	"""Infer only categories that are unambiguous from legacy data."""
	legacy = (legacy_period or "").strip()
	if legacy == "Monthly":
		return "Category C"
	if legacy == "Six-Monthly":
		return "Category D"
	if legacy == "Annually":
		return "Category E"
	if legacy == "Bi-Monthly" and from_date and to_date:
		return "Category A" if getdate(to_date).month % 2 else "Category B"
	return None


def resolve_filing_category(
	filing_category: str | None,
	legacy_period: str | None,
	from_date=None,
	to_date=None,
) -> str:
	"""Return an explicit SARS filing category without accepting generic quarterly periods."""
	category = (filing_category or "").strip()
	if category:
		if category not in FILING_CATEGORIES:
			frappe.throw(_("VAT Filing Category must be one of {0}.").format(", ".join(FILING_CATEGORIES)))
		return category

	legacy = (legacy_period or "").strip()
	if inferred_category := infer_legacy_filing_category(legacy, from_date, to_date):
		return inferred_category
	if legacy:
		frappe.throw(
			_(
				"Generic VAT period {0} is not a SARS filing category. Select Category A, B, C, D, or E."
			).format(frappe.bold(legacy))
		)
	frappe.throw(_("VAT Filing Category is required. Select Category A, B, C, D, or E."))


def validate_filing_period(category: str, from_date, to_date) -> None:
	"""Validate that dates are complete calendar periods for the selected SARS category."""
	start = getdate(from_date)
	end = getdate(to_date)
	if start != get_first_day(start) or end != get_last_day(end):
		frappe.throw(_("VAT periods must start on the first day and end on the last day of a month."))

	months = {
		"Category A": 2,
		"Category B": 2,
		"Category C": 1,
		"Category D": 6,
		"Category E": 12,
	}.get(category)
	if not months:
		frappe.throw(_("Unsupported VAT Filing Category {0}.").format(frappe.bold(category)))

	expected_end = get_last_day(add_months(start, months - 1))
	if end != expected_end:
		frappe.throw(_("{0} requires a complete {1}-month VAT period.").format(category, months))

	if category == "Category A" and end.month % 2 == 0:
		frappe.throw(_("Category A periods must end in January, March, May, July, September, or November."))
	if category == "Category B" and end.month % 2 != 0:
		frappe.throw(_("Category B periods must end in February, April, June, August, October, or December."))
	if category == "Category D" and end.month not in {2, 8}:
		frappe.throw(_("Category D periods must end on the last day of February or August."))


def build_active_period_key(company: str, from_date, to_date) -> str:
	"""Build the unique key used while a VAT201 working paper is active."""
	identity = "\x1f".join((company, str(getdate(from_date)), str(getdate(to_date))))
	return hashlib.sha256(identity.encode()).hexdigest()
