"""Resolve approved statutory values and provenance by transaction date.

This module is the public cross-app contract. Domain apps must pass the date of
the transaction or payroll period they are calculating; the resolver never
falls back to the current date and never guesses between competing records.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate


def get_rate(
	domain: str,
	rule_key: str,
	on_date: str,
	*,
	expected_unit: str | None = None,
) -> Any:
	"""Return one approved value or fail loudly when configuration is incomplete."""
	return resolve_rate(domain, rule_key, on_date, expected_unit=expected_unit)["value"]


def get_rates(
	domain: str,
	rule_keys: Iterable[str],
	on_date: str,
	*,
	expected_units: Mapping[str, str] | None = None,
) -> dict[str, Any]:
	"""Resolve several rules in one query for a downstream calculation."""
	return {
		rule_key: resolution["value"]
		for rule_key, resolution in resolve_rates(
			domain,
			rule_keys,
			on_date,
			expected_units=expected_units,
		).items()
	}


def resolve_rate(
	domain: str,
	rule_key: str,
	on_date: str,
	*,
	expected_unit: str | None = None,
) -> dict[str, Any]:
	"""Return a value together with its approved source and pack provenance."""
	return resolve_rates(
		domain,
		(rule_key,),
		on_date,
		expected_units={rule_key: expected_unit} if expected_unit else None,
	)[rule_key]


def resolve_rates(
	domain: str,
	rule_keys: Iterable[str],
	on_date: str,
	*,
	expected_units: Mapping[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
	"""Resolve approved rules for one domain/date without an implicit fallback.

	The returned dictionaries are JSON-compatible and include the exact pack,
	source, effective period and checksums used. This lets downstream documents
	persist a calculation audit trail without importing core controllers.
	"""
	domain = _non_empty_string(domain, "domain")
	date_value = getdate(_non_empty_string(on_date, "on_date"))
	if isinstance(rule_keys, str):
		raise TypeError("rule_keys must be an iterable of rule-key strings, not one string")
	keys = tuple(dict.fromkeys(_non_empty_string(key, "rule_key") for key in rule_keys))
	if not keys:
		raise TypeError("rule_keys must contain at least one non-empty string")

	pack = frappe.qb.DocType("ZA Statutory Rate Pack")
	item = frappe.qb.DocType("ZA Statutory Rate Item")
	source = frappe.qb.DocType("ZA Statutory Source")
	rows = (
		frappe.qb.from_(pack)
		.inner_join(item)
		.on((item.parent == pack.name) & (item.parenttype == "ZA Statutory Rate Pack"))
		.inner_join(source)
		.on(source.name == pack.source)
		.select(
			pack.name.as_("rate_pack"),
			pack.effective_from,
			pack.effective_to,
			pack.content_sha256.as_("rate_pack_sha256"),
			source.name.as_("source"),
			source.sha256_checksum.as_("source_sha256"),
			item.rule_key,
			item.numeric_value,
			item.text_value,
			item.unit,
			item.precision,
		)
		.where(pack.domain == domain)
		.where(pack.docstatus == 1)
		.where(pack.status == "Approved")
		.where(source.docstatus == 1)
		.where(source.status == "Approved")
		.where(pack.effective_from <= date_value)
		.where(pack.effective_to >= date_value)
		.where(item.rule_key.isin(keys))
	).run(as_dict=True)

	rows_by_key: dict[str, list] = {key: [] for key in keys}
	for row in rows:
		rows_by_key[row.rule_key].append(row)

	resolutions = {}
	for rule_key, matching_rows in rows_by_key.items():
		if not matching_rows:
			frappe.throw(
				_("No approved {0} statutory value for {1} applies on {2}.").format(
					domain, rule_key, date_value
				)
				+ describe_resolution_gap(domain, date_value),
				title=_("Missing Statutory Rate"),
			)
		if len(matching_rows) > 1:
			frappe.throw(
				_("Multiple approved {0} statutory values for {1} apply on {2}.").format(
					domain, rule_key, date_value
				),
				title=_("Overlapping Statutory Rates"),
			)

		row = matching_rows[0]
		expected_unit = (expected_units or {}).get(rule_key)
		if expected_unit and row.unit != expected_unit:
			frappe.throw(
				_("Statutory value {0} has unit {1}; {2} is required.").format(
					rule_key, row.unit, expected_unit
				),
				title=_("Unexpected Statutory Rate Unit"),
			)
		value = row.text_value if row.unit == "Text" else flt(row.numeric_value, row.precision)
		resolutions[rule_key] = {
			"domain": domain,
			"rule_key": rule_key,
			"on_date": str(date_value),
			"value": value,
			"unit": row.unit,
			"precision": row.precision,
			"rate_pack": row.rate_pack,
			"rate_pack_sha256": row.rate_pack_sha256,
			"source": row.source,
			"source_sha256": row.source_sha256,
			"effective_from": str(row.effective_from),
			"effective_to": str(row.effective_to),
		}
	return resolutions


def describe_resolution_gap(domain: str, date_value: str | Any) -> str:
	"""Explain why resolution failed and what the reviewer has to do next.

	Refusing to calculate is the intended control, but on its own it is a dead end:
	the reader learns a rule key is missing and not that a rate pack is waiting to
	be approved. This reports the packs that exist for the domain and names the one
	action that will clear the block.
	"""
	# Callers pass either a date or its string form; compare as dates either way.
	on_date = getdate(date_value)
	packs = frappe.get_all(
		"ZA Statutory Rate Pack",
		filters={"domain": domain, "docstatus": ("<", 2)},
		fields=["name", "status", "docstatus", "source", "effective_from", "effective_to"],
		order_by="effective_from",
	)
	if not packs:
		return (
			_paragraph(
				_(
					"No {0} rate pack exists on this site yet. Run <b>bench migrate</b> to seed the "
					"draft pack this app prepares, then approve it."
				).format(domain)
			)
			+ _guide_hint()
		)

	covering = [
		pack for pack in packs if getdate(pack.effective_from) <= on_date <= getdate(pack.effective_to)
	]
	if not covering:
		windows = "".join(
			f"<li>{frappe.utils.escape_html(pack.name)}: "
			f"{pack.effective_from} &rarr; {pack.effective_to} ({_pack_state(pack)})</li>"
			for pack in packs
		)
		return (
			_paragraph(
				_(
					"No {0} rate pack covers {1}. Either set a Statutory Control Date inside an "
					"approved window below, or have a reviewer approve a pack for the period you "
					"need. Never widen an existing window to reach an earlier date."
				).format(domain, on_date)
			)
			+ f"<ul>{windows}</ul>"
			+ _guide_hint()
		)

	pack = covering[0]
	if pack.docstatus == 1:
		# Submitted but still unresolvable: the pack is fine, its source is not.
		return (
			_paragraph(
				_(
					"Rate pack {0} covers {1} but did not resolve. Confirm it holds every required "
					"rule key and that its statutory source {2} is submitted and Approved."
				).format(_pack_link(pack.name), on_date, frappe.utils.escape_html(pack.source or "-"))
			)
			+ _guide_hint()
		)

	return (
		_paragraph(
			_("Rate pack {0} covers {1} and is still a draft. To approve it:").format(
				_pack_link(pack.name), on_date
			)
		)
		+ "<ol>"
		+ f"<li>{_('Open its statutory source {0} and attach the official SARS document as a private file, with its SHA-256 checksum.').format(_source_link(pack.source))}</li>"
		+ f"<li>{_('Set Reviewed By on the source to yourself and submit it.')}</li>"
		+ f"<li>{_('Open the rate pack, check every value against that evidence, set Reviewed By and submit.')}</li>"
		+ "</ol>"
		+ _paragraph(
			_(
				"Approval needs the <b>ZA Compliance Reviewer</b> or <b>ZA Compliance Manager</b> "
				"role, and the approver cannot be the user who created the record. A pack this app "
				"prepared is owned by the installing account, so approve it as a named user rather "
				"than as Administrator."
			)
		)
		+ _guide_hint()
	)


def _pack_state(pack) -> str:
	return _("approved") if pack.docstatus == 1 else _("draft, awaiting approval")


def _pack_link(name: str) -> str:
	route = f"/desk/za-statutory-rate-pack/{frappe.utils.quoted(name)}"
	return f'<a href="{route}">{frappe.utils.escape_html(name)}</a>'


def _source_link(name: str | None) -> str:
	if not name:
		return _("(none linked)")
	route = f"/desk/za-statutory-source/{frappe.utils.quoted(name)}"
	return f'<a href="{route}">{frappe.utils.escape_html(name)}</a>'


def _guide_hint() -> str:
	return _paragraph(
		_("The Statutory Source Governance page of the SA Practitioner Guide walks through this once.")
	)


def _paragraph(text: str) -> str:
	return f"<p>{text}</p>"


def _non_empty_string(value: object, label: str) -> str:
	if not isinstance(value, str) or not value.strip():
		raise TypeError(f"{label} must be a non-empty string")
	return value.strip()
