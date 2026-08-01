"""Read-only control totals used before and after localisation migrations."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.query_builder.functions import Count, Sum
from frappe.utils import flt


_COUNT_DOCTYPES = (
	"Company",
	"Employee",
	"Salary Component",
	"Salary Structure",
	"Salary Structure Assignment",
	"Salary Slip",
	"Payroll Entry",
	"EMP201 Submission",
	"EMP501 Reconciliation",
	"IRP5 Certificate",
	"VAT201 Return",
	"COIDA Annual Return",
	"Workplace Injury",
	"OID Claim",
)


def collect() -> dict[str, Any]:
	"""Return deterministic, non-personal row counts and monetary controls."""
	return {
		"site": frappe.local.site,
		"installed_apps": list(frappe.get_installed_apps()),
		"row_counts": _row_counts(),
		"salary_slip_controls": _salary_slip_controls(),
		"declaration_controls": _declaration_controls(),
		"vat_controls": _vat_controls(),
		"coida_controls": _coida_controls(),
		"module_owners": _module_owners(),
	}


def _row_counts() -> dict[str, int]:
	return {
		doctype: frappe.db.count(doctype)
		for doctype in _COUNT_DOCTYPES
		if frappe.db.exists("DocType", doctype)
	}


def _salary_slip_controls() -> dict[str, float | int]:
	if not frappe.db.exists("DocType", "Salary Slip"):
		return {}
	return _aggregate(
		"Salary Slip",
		("gross_pay", "total_deduction", "net_pay", "za_monthly_eti"),
		submitted_only=True,
		aliases={"za_monthly_eti": "eti"},
	)


def _declaration_controls() -> dict[str, dict[str, float | int]]:
	result = {}
	for doctype, fields in {
		"EMP201 Submission": (
			"gross_paye_before_eti",
			"uif_payable",
			"sdl_payable",
			"eti_utilized_current_month",
		),
		"EMP501 Reconciliation": ("total_paye", "total_uif", "total_sdl", "total_eti"),
		"IRP5 Certificate": ("gross_taxable_income", "paye", "uif", "eti"),
	}.items():
		if not frappe.db.exists("DocType", doctype):
			continue
		result[doctype] = _aggregate(doctype, fields, submitted_only=True)
	return result


def _vat_controls() -> dict[str, float | int]:
	if not frappe.db.exists("DocType", "VAT201 Return"):
		return {}
	meta = frappe.get_meta("VAT201 Return")
	fields = [
		field
		for field in ("total_output_tax", "total_input_tax", "vat_payable", "vat_refundable", "total_amount_payable")
		if meta.has_field(field)
	]
	return _aggregate("VAT201 Return", fields)


def _coida_controls() -> dict[str, float | int]:
	if not frappe.db.exists("DocType", "COIDA Annual Return"):
		return {}
	meta = frappe.get_meta("COIDA Annual Return")
	fields = [field for field in ("total_annual_earnings", "assessment_fee") if meta.has_field(field)]
	return _aggregate("COIDA Annual Return", fields)


def _module_owners() -> dict[str, str]:
	modules = frappe.get_all(
		"Module Def",
		filters={"name": ["like", "SA %"]},
		fields=["name", "app_name"],
		order_by="name",
	)
	return {row.name: row.app_name for row in modules}


def _aggregate(
	doctype: str,
	fields: tuple[str, ...] | list[str],
	*,
	submitted_only: bool = False,
	aliases: dict[str, str] | None = None,
) -> dict[str, float | int]:
	table = frappe.qb.DocType(doctype)
	aliases = aliases or {}
	selections = [Count(table.name).as_("documents")]
	selections.extend(Sum(table[field]).as_(aliases.get(field, field)) for field in fields)
	query = frappe.qb.from_(table).select(*selections)
	if submitted_only:
		query = query.where(table.docstatus == 1)
	return _normalise_aggregate(query.run(as_dict=True))


def _normalise_aggregate(rows: list[dict]) -> dict[str, float | int]:
	if not rows:
		return {}
	result = {}
	for key, value in rows[0].items():
		result[key] = int(value or 0) if key == "documents" else flt(value, 6)
	return result
