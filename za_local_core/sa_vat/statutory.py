"""Approved, date-effective South African VAT controls.

Runtime VAT calculations must resolve these values from submitted governance
records in ``za_local_core``.  This module deliberately has no numeric fallback:
missing or overlapping statutory data is a release-blocking configuration error.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate

from za_local_core.services.rates import resolve_rates

VAT_DOMAIN = "VAT"

STANDARD_RATE = "vat.standard_rate"
COMPULSORY_REGISTRATION_THRESHOLD = "vat.registration.compulsory_threshold"
VOLUNTARY_REGISTRATION_THRESHOLD = "vat.registration.voluntary_threshold"
NO_INVOICE_THRESHOLD = "vat.invoice.no_invoice_max"
FULL_INVOICE_THRESHOLD = "vat.invoice.full_invoice_threshold"

VAT_CONTROL_RULE_KEYS = (
	STANDARD_RATE,
	COMPULSORY_REGISTRATION_THRESHOLD,
	VOLUNTARY_REGISTRATION_THRESHOLD,
	NO_INVOICE_THRESHOLD,
	FULL_INVOICE_THRESHOLD,
)

VAT_CONTROL_UNITS = {
	STANDARD_RATE: "Percentage",
	COMPULSORY_REGISTRATION_THRESHOLD: "Amount",
	VOLUNTARY_REGISTRATION_THRESHOLD: "Amount",
	NO_INVOICE_THRESHOLD: "Amount",
	FULL_INVOICE_THRESHOLD: "Amount",
}

# Practitioner-facing source catalogue metadata.  The values themselves are not
# consumed from this mapping; they must be reviewed and approved in ZA Statutory
# Source / ZA Statutory Rate Pack before use.
CURRENT_APPROVED_SOURCE_METADATA = {
	"authority": "SARS",
	"effective_from": "2026-04-01",
	"registration_source_url": (
		"https://www.sars.gov.za/about/sars-tax-and-customs-system/budget/"
		"budget-2026-frequently-asked-questions/"
	),
	"invoice_source_url": "https://www.sars.gov.za/businesses-and-employers/government/tax-invoices/",
	"rate_source_url": "https://www.sars.gov.za/tax-rates/other-taxes/",
	"expected_current_values": {
		STANDARD_RATE: 15,
		COMPULSORY_REGISTRATION_THRESHOLD: 2_300_000,
		VOLUNTARY_REGISTRATION_THRESHOLD: 120_000,
		NO_INVOICE_THRESHOLD: 50,
		FULL_INVOICE_THRESHOLD: 5_000,
	},
}


def resolve_vat_controls(on_date: str) -> dict[str, Any]:
	"""Resolve and validate the complete VAT control bundle for ``on_date``."""
	date_value = str(getdate(on_date))
	resolved = resolve_rates(
		VAT_DOMAIN,
		VAT_CONTROL_RULE_KEYS,
		date_value,
		expected_units=VAT_CONTROL_UNITS,
	)

	pack_names = {row["rate_pack"] for row in resolved.values()}
	source_names = {row["source"] for row in resolved.values()}
	if len(pack_names) != 1 or len(source_names) != 1:
		frappe.throw(
			_("All VAT controls for {0} must come from one approved source and rate pack.").format(
				date_value
			),
			title=_("Inconsistent VAT Statutory Controls"),
		)

	values = {key: flt(row["value"]) for key, row in resolved.items()}
	_validate_values(values, date_value)
	provenance = next(iter(resolved.values()))
	return {
		"on_date": date_value,
		"values": values,
		"rate_pack": provenance["rate_pack"],
		"rate_pack_sha256": provenance["rate_pack_sha256"],
		"source": provenance["source"],
		"source_sha256": provenance["source_sha256"],
		"effective_from": provenance["effective_from"],
		"effective_to": provenance["effective_to"],
	}


def apply_vat_controls(settings) -> dict[str, Any]:
	"""Resolve approved controls and persist their values/provenance on a settings document."""
	if not settings.statutory_control_date:
		frappe.throw(
			_("Statutory Control Date is required to resolve approved VAT controls."),
			title=_("Missing VAT Control Date"),
		)
	controls = resolve_vat_controls(str(settings.statutory_control_date))
	values = controls["values"]
	settings.standard_vat_rate = values[STANDARD_RATE]
	settings.vat_registration_threshold = values[COMPULSORY_REGISTRATION_THRESHOLD]
	settings.vat_voluntary_threshold = values[VOLUNTARY_REGISTRATION_THRESHOLD]
	settings.no_invoice_threshold = values[NO_INVOICE_THRESHOLD]
	settings.full_invoice_threshold = values[FULL_INVOICE_THRESHOLD]
	settings.statutory_rate_pack = controls["rate_pack"]
	settings.statutory_rate_pack_sha256 = controls["rate_pack_sha256"]
	settings.statutory_source = controls["source"]
	settings.statutory_source_sha256 = controls["source_sha256"]
	settings.statutory_effective_from = controls["effective_from"]
	settings.statutory_effective_to = controls["effective_to"]
	return controls


def _validate_values(values: Mapping[str, float], on_date: str) -> None:
	if values[STANDARD_RATE] <= 0:
		frappe.throw(_("The approved standard VAT rate for {0} must be positive.").format(on_date))
	if values[VOLUNTARY_REGISTRATION_THRESHOLD] <= 0:
		frappe.throw(
			_("The approved voluntary VAT registration threshold for {0} must be positive.").format(on_date)
		)
	if values[COMPULSORY_REGISTRATION_THRESHOLD] <= values[VOLUNTARY_REGISTRATION_THRESHOLD]:
		frappe.throw(
			_("The approved compulsory VAT threshold must exceed the voluntary threshold on {0}.").format(
				on_date
			)
		)
	if values[NO_INVOICE_THRESHOLD] < 0:
		frappe.throw(_("The approved no-invoice threshold for {0} cannot be negative.").format(on_date))
	if values[FULL_INVOICE_THRESHOLD] <= values[NO_INVOICE_THRESHOLD]:
		frappe.throw(
			_("The approved full-invoice threshold must exceed the no-invoice threshold on {0}.").format(
				on_date
			)
		)
