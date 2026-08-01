"""Resolve approved statutory values by their transaction date."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import getdate


def get_rate(domain: str, rule_key: str, on_date: str) -> Any:
	"""Return one approved rate value or fail when configuration is ambiguous."""
	for value in (domain, rule_key, on_date):
		if not isinstance(value, str) or not value.strip():
			raise TypeError("domain, rule_key and on_date must be non-empty strings")

	pack = frappe.qb.DocType("ZA Statutory Rate Pack")
	item = frappe.qb.DocType("ZA Statutory Rate Item")
	rows = (
		frappe.qb.from_(pack)
		.inner_join(item)
		.on((item.parent == pack.name) & (item.parenttype == "ZA Statutory Rate Pack"))
		.select(pack.name, item.numeric_value, item.text_value, item.unit)
		.where(pack.domain == domain)
		.where(pack.docstatus == 1)
		.where(pack.effective_from <= getdate(on_date))
		.where(pack.effective_to >= getdate(on_date))
		.where(item.rule_key == rule_key)
	).run(as_dict=True)

	if not rows:
		frappe.throw(
			_("No approved {0} statutory value for {1} applies on {2}.").format(domain, rule_key, on_date),
			title=_("Missing Statutory Rate"),
		)
	if len(rows) > 1:
		frappe.throw(
			_("Multiple approved {0} statutory values for {1} apply on {2}.").format(domain, rule_key, on_date),
			title=_("Overlapping Statutory Rates"),
		)

	row = rows[0]
	return row.text_value if row.unit == "Text" else row.numeric_value
