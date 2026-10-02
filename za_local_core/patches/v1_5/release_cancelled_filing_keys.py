"""Release the unique period key held by cancelled ZA Filings.

A cancelled filing kept its company/obligation/period key, so the amended VAT201
for the same period could not create its replacement filing and its submission
failed on the unique index. Cancellation now clears the key; this clears it on
filings cancelled before that change. Cancelled records are otherwise untouched.
"""

import frappe


def execute() -> None:
	if not frappe.db.exists("DocType", "ZA Filing"):
		return
	frappe.db.sql(
		"""update `tabZA Filing` set filing_key = null
		where docstatus = 2 and filing_key is not null"""
	)
