"""Derived status synchronization for shared compliance records."""

import frappe


def sync_vat201_from_receipt(doc, _method=None) -> None:
	status = doc.response_status if doc.docstatus == 1 else "Prepared"
	_update_linked_vat201(doc.filing, status)


def sync_vat201_from_filing(doc, _method=None) -> None:
	if doc.docstatus == 2:
		_update_linked_vat201(doc.name, "Prepared")


def _update_linked_vat201(filing: str, status: str) -> None:
	for name in frappe.get_all(
		"VAT201 Return",
		filters={"za_filing": filing, "docstatus": 1},
		pluck="name",
	):
		# Status mirrors an immutable core compliance record and is not an approval transition.
		frappe.db.set_value("VAT201 Return", name, "status", status, update_modified=False)
