"""Point the BCEA earnings threshold source at the gazette and fix its amount.

The seeded catalogue recorded a media statement rather than the determination, and
its note carried R269,900.90 where the gazette sets R269,600.90. Seeding only creates
sources that are missing, so a site installed before this keeps both mistakes.
"""

import frappe

CATALOG_KEY = "DEL-BCEA-EARNINGS-THRESHOLD-2026"
STALE_URL = (
	"https://www.labour.gov.za/Media-Desk/Media-Statements/Pages/"
	"Department-of-Employment-and-Labour-sets-a-new-threshold-in-the-protection-of-employees-.aspx"
)
STALE_AMOUNT = "R269,900.90"


def execute() -> None:
	if not frappe.db.exists("DocType", "ZA Statutory Source"):
		return

	source = frappe.db.get_value(
		"ZA Statutory Source",
		{"catalog_key": CATALOG_KEY},
		["name", "docstatus", "source_url", "notes"],
		as_dict=True,
	)
	if not source:
		return

	carries_stale_values = source.source_url == STALE_URL or STALE_AMOUNT in (source.notes or "")
	if not carries_stale_values:
		return

	if source.docstatus != 0:
		# Never rewrite an approved compliance record. Surface it instead: someone
		# reviewed a note quoting the wrong threshold and needs to look again.
		frappe.log_error(
			title="BCEA earnings threshold source needs re-approval",
			message=(
				f"{source.name} was approved while recording {STALE_AMOUNT}. The gazetted "
				f"threshold is R269,600.90 (Government Notice 7384, Government Gazette 54544 "
				f"of 17 April 2026). Amend the source and re-approve it."
			),
		)
		return

	from za_local_core.migration.backfill import _source_catalog

	entry = next((row for row in _source_catalog() if row["catalog_key"] == CATALOG_KEY), None)
	if not entry:
		return

	frappe.db.set_value(
		"ZA Statutory Source",
		source.name,
		{
			"document_type": entry["document_type"],
			"version": entry["version"],
			"publication_date": entry["publication_date"],
			"source_url": entry["source_url"],
			"notes": entry["notes"],
		},
		update_modified=False,
	)
