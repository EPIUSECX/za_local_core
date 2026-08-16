"""Point the VAT controls source at the page SARS maintains, not the Budget FAQ.

The seeded source cited the Budget 2026 FAQ, which belongs to one budget cycle and
is archived once the next one lands. SARS's standing VAT page carries the same three
values and stays put. Seeding only creates sources that are missing, so a site
installed before this keeps the old link.

The amounts themselves were correct and are not touched.
"""

import frappe

CATALOG_KEY = "SARS-VAT-CONTROLS-2026-04-01"
STALE_URL_FRAGMENT = "budget-2026-frequently-asked-questions"


def execute() -> None:
	if not frappe.db.exists("DocType", "ZA Statutory Source"):
		return

	source = frappe.db.get_value(
		"ZA Statutory Source",
		{"catalog_key": CATALOG_KEY},
		["name", "docstatus", "source_url"],
		as_dict=True,
	)
	if not source or STALE_URL_FRAGMENT not in (source.source_url or ""):
		return

	if source.docstatus != 0:
		# An approved record stands. Re-pointing its evidence underneath the reviewer
		# would break the link between what they checked and what the record claims.
		frappe.log_error(
			title="VAT controls source cites the Budget FAQ",
			message=(
				f"{source.name} was approved against the Budget 2026 FAQ, which SARS archives "
				f"each budget cycle. The standing reference carrying the same values is "
				f"https://www.sars.gov.za/types-of-tax/value-added-tax/. Amend and re-approve "
				f"the source when convenient; the recorded amounts are unaffected."
			),
		)
		return

	from za_local_core.sa_vat.statutory import CURRENT_APPROVED_SOURCE_METADATA

	frappe.db.set_value(
		"ZA Statutory Source",
		source.name,
		"source_url",
		CURRENT_APPROVED_SOURCE_METADATA["registration_source_url"],
		update_modified=False,
	)
