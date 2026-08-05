"""Immutable VAT source-to-ledger snapshot controls."""

import json

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from za_local_core.governance import canonical_sha256

RECONCILIATION_TOLERANCE = 0.01
RECONCILED = "Reconciled"
NEEDS_REVIEW = "Needs Review"
EXCLUDED = "Excluded"


def enrich_invoice_rows(rows, invoice, taxes, tax_account: str, voucher_type: str) -> None:
	"""Attach a deterministic source and GL allocation to classified invoice rows."""
	if not rows:
		return
	is_purchase = voucher_type == "Purchase Invoice"
	sign = -1 if int(invoice.is_return or 0) and flt(invoice.base_net_total) > 0 else 1
	source_tax = sum(flt(row.source_tax_amount) for row in taxes) * sign
	source_base_tax = sum(flt(row.base_tax_amount) for row in taxes) * sign
	gl_entries = get_invoice_gl_entries(voucher_type, invoice.name, tax_account)
	gl_total = sum(
		(flt(entry.debit) - flt(entry.credit)) if is_purchase else (flt(entry.credit) - flt(entry.debit))
		for entry in gl_entries
	)
	weights = [abs(flt(row.get("gross_tax_amount", row.get("tax_amount")))) for row in rows]
	source_tax_allocations = distribute_amount(source_tax, weights)
	source_base_allocations = distribute_amount(source_base_tax, weights)
	gl_allocations = distribute_amount(gl_total, weights)
	source_rows = json.dumps(
		[
			{
				"name": row.name,
				"tax_amount": flt(row.source_tax_amount, 9),
				"base_tax_amount": flt(row.base_tax_amount, 9),
			}
			for row in taxes
		],
		sort_keys=True,
		separators=(",", ":"),
	)
	gl_rows = json.dumps(
		[
			{
				"name": row.name,
				"account": row.account,
				"debit": flt(row.debit, 9),
				"credit": flt(row.credit, 9),
			}
			for row in gl_entries
		],
		sort_keys=True,
		separators=(",", ":"),
	)

	for index, row in enumerate(rows):
		row.update(
			{
				"gl_entry": gl_entries[0].name if len(gl_entries) == 1 else None,
				"source_rows_json": source_rows,
				"source_modified": invoice.modified,
				"source_currency": invoice.currency,
				"exchange_rate": flt(invoice.conversion_rate, 9),
				"source_tax_amount": source_tax_allocations[index],
				"source_base_tax_amount": source_base_allocations[index],
				"tax_account": tax_account,
				"gl_entries_json": gl_rows,
				"gl_tax_amount": gl_allocations[index],
			}
		)
		finalize_row_snapshot(row)


def enrich_journal_row(row, entry) -> None:
	"""Snapshot one Journal Entry VAT leg, whose source is the posted GL row itself."""
	amount = flt(entry.debit) - flt(entry.credit)
	row.update(
		{
			"source_rows_json": json.dumps([{"name": entry.name}], separators=(",", ":")),
			"source_modified": entry.modified,
			"source_currency": frappe.get_cached_value("Company", entry.company, "default_currency"),
			"exchange_rate": 1,
			"source_tax_amount": amount,
			"source_base_tax_amount": amount,
			"tax_account": entry.account,
			"gl_entries_json": json.dumps(
				[
					{
						"name": entry.name,
						"account": entry.account,
						"debit": flt(entry.debit, 9),
						"credit": flt(entry.credit, 9),
					}
				],
				sort_keys=True,
				separators=(",", ":"),
			),
			"gl_tax_amount": amount,
		}
	)
	finalize_row_snapshot(row)


def finalize_row_snapshot(row) -> None:
	row["reconciliation_difference"] = flt(
		flt(row.get("source_base_tax_amount")) - flt(row.get("gl_tax_amount")), 2
	)
	row["reconciliation_status"] = (
		RECONCILED if abs(flt(row["reconciliation_difference"])) <= RECONCILIATION_TOLERANCE else NEEDS_REVIEW
	)
	row["source_snapshot_sha256"] = canonical_sha256(source_payload(row))
	row["gl_snapshot_sha256"] = canonical_sha256(gl_payload(row))


def set_parent_reconciliation(vat_return) -> None:
	"""Aggregate child snapshots without reading mutable source documents."""
	active_rows = [row for row in vat_return.transactions if not row.is_cancelled]
	vat_return.source_vat_total = flt(sum(flt(row.source_base_tax_amount) for row in active_rows), 2)
	vat_return.gl_vat_total = flt(sum(flt(row.gl_tax_amount) for row in active_rows), 2)
	vat_return.reconciliation_difference = flt(vat_return.source_vat_total - vat_return.gl_vat_total, 2)
	vat_return.reconciliation_status = (
		RECONCILED
		if active_rows
		and all(row.reconciliation_status in {RECONCILED, EXCLUDED} for row in active_rows)
		and abs(flt(vat_return.reconciliation_difference)) <= RECONCILIATION_TOLERANCE
		else NEEDS_REVIEW
	)
	vat_return.source_snapshot_sha256 = canonical_sha256(
		parent_payload(vat_return, active_rows, "source_snapshot_sha256")
	)
	vat_return.gl_snapshot_sha256 = canonical_sha256(
		parent_payload(vat_return, active_rows, "gl_snapshot_sha256")
	)


def verify_snapshots(vat_return) -> None:
	"""Reject missing or altered snapshots before the working paper is submitted."""
	active_rows = [row for row in vat_return.transactions if not row.is_cancelled]
	if not active_rows or not vat_return.snapshot_generated_on:
		frappe.throw(_("Generate the immutable VAT source-to-GL snapshot before submitting."))
	for row in active_rows:
		if row.source_snapshot_sha256 != canonical_sha256(source_payload(row)):
			frappe.throw(
				_("VAT source snapshot for {0} was altered; refresh the return.").format(row.voucher_no)
			)
		if row.gl_snapshot_sha256 != canonical_sha256(gl_payload(row)):
			frappe.throw(_("VAT GL snapshot for {0} was altered; refresh the return.").format(row.voucher_no))
	if vat_return.source_snapshot_sha256 != canonical_sha256(
		parent_payload(vat_return, active_rows, "source_snapshot_sha256")
	):
		frappe.throw(_("The VAT source snapshot digest is invalid; refresh the return."))
	if vat_return.gl_snapshot_sha256 != canonical_sha256(
		parent_payload(vat_return, active_rows, "gl_snapshot_sha256")
	):
		frappe.throw(_("The VAT GL snapshot digest is invalid; refresh the return."))
	if vat_return.reconciliation_status != RECONCILED:
		frappe.throw(_("Resolve all source-to-GL differences before submitting the VAT201 working paper."))


def calculate_live_ledger_sha256(vat_return, settings) -> str:
	"""Fingerprint all in-period source documents and VAT ledger rows."""
	invoice_rows = []
	for doctype in ("Sales Invoice", "Purchase Invoice"):
		for row in frappe.get_all(
			doctype,
			filters={
				"company": vat_return.company,
				"docstatus": 1,
				"posting_date": ["between", [vat_return.from_date, vat_return.to_date]],
			},
			fields=["name", "posting_date", "modified", "currency", "conversion_rate", "base_net_total"],
			order_by="name asc",
		):
			invoice_rows.append(
				{
					"doctype": doctype,
					"name": row.name,
					"posting_date": str(row.posting_date),
					"modified": str(row.modified),
					"currency": row.currency,
					"conversion_rate": flt(row.conversion_rate, 9),
					"base_net_total": flt(row.base_net_total, 9),
				}
			)

	vat_accounts = {settings.output_vat_account, settings.input_vat_account}
	vat_accounts.update(row.account for row in (settings.vat_accounts or []) if row.account)
	classified_accounts = frappe.get_all(
		"Account",
		filters={"company": vat_return.company},
		or_filters=[
			["custom_vat_return_debit_classification", "not in", ["", None]],
			["custom_vat_return_credit_classification", "not in", ["", None]],
		],
		pluck="name",
	)
	vat_accounts.update(classified_accounts)
	vat_accounts.discard(None)
	gl_rows = frappe.get_all(
		"GL Entry",
		filters={
			"company": vat_return.company,
			"posting_date": ["between", [vat_return.from_date, vat_return.to_date]],
			"account": ["in", sorted(vat_accounts)],
			"is_cancelled": 0,
		},
		fields=[
			"name",
			"voucher_type",
			"voucher_no",
			"posting_date",
			"account",
			"debit",
			"credit",
			"modified",
		],
		order_by="name asc",
	)
	ledger_payload = [
		{
			"name": row.name,
			"voucher_type": row.voucher_type,
			"voucher_no": row.voucher_no,
			"posting_date": str(row.posting_date),
			"account": row.account,
			"debit": flt(row.debit, 9),
			"credit": flt(row.credit, 9),
			"modified": str(row.modified),
		}
		for row in gl_rows
	]
	return canonical_sha256({"invoices": invoice_rows, "ledger": ledger_payload})


def stamp_snapshot(vat_return, settings) -> None:
	vat_return.snapshot_generated_on = now_datetime()
	set_parent_reconciliation(vat_return)
	vat_return.live_ledger_sha256 = calculate_live_ledger_sha256(vat_return, settings)


def verify_live_ledger(vat_return, settings) -> None:
	if vat_return.live_ledger_sha256 != calculate_live_ledger_sha256(vat_return, settings):
		frappe.throw(_("VAT source documents or GL entries changed after the snapshot; refresh the return."))


def get_invoice_gl_entries(voucher_type: str, voucher_no: str, account: str):
	return frappe.get_all(
		"GL Entry",
		filters={
			"voucher_type": voucher_type,
			"voucher_no": voucher_no,
			"account": account,
			"is_cancelled": 0,
		},
		fields=["name", "account", "debit", "credit"],
		order_by="name asc",
	)


def distribute_amount(total: float, weights: list[float]) -> list[float]:
	"""Allocate a currency total deterministically while preserving its rounded sum."""
	if not weights:
		return []
	weight_total = sum(weights)
	if not weight_total:
		return [0.0 for _weight in weights]
	allocations = []
	remaining = flt(total, 2)
	for index, weight in enumerate(weights):
		if index == len(weights) - 1:
			allocation = remaining
		else:
			allocation = flt(flt(total) * weight / weight_total, 2)
			remaining = flt(remaining - allocation, 2)
		allocations.append(allocation)
	return allocations


def source_payload(row) -> dict:
	return {
		"voucher_type": row.get("voucher_type"),
		"voucher_no": row.get("voucher_no"),
		"posting_date": str(row.get("posting_date")),
		"source_rows_json": row.get("source_rows_json") or "[]",
		"source_modified": str(row.get("source_modified")),
		"source_currency": row.get("source_currency"),
		"exchange_rate": flt(row.get("exchange_rate"), 9),
		"source_tax_amount": flt(row.get("source_tax_amount"), 9),
		"source_base_tax_amount": flt(row.get("source_base_tax_amount"), 9),
	}


def gl_payload(row) -> dict:
	return {
		"voucher_type": row.get("voucher_type"),
		"voucher_no": row.get("voucher_no"),
		"tax_account": row.get("tax_account"),
		"gl_entries_json": row.get("gl_entries_json") or "[]",
		"gl_tax_amount": flt(row.get("gl_tax_amount"), 9),
	}


def parent_payload(vat_return, rows, digest_field: str) -> dict:
	return {
		"company": vat_return.company,
		"from_date": str(vat_return.from_date),
		"to_date": str(vat_return.to_date),
		"rows": sorted(row.get(digest_field) or "" for row in rows),
	}
