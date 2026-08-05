"""Bridge VAT201 working papers to the shared compliance filing controls."""

import hashlib
import json

import frappe
from frappe import _
from frappe.utils import flt, now_datetime
from frappe.utils.file_manager import save_file

from za_local_core.governance import APPROVAL_ROLES

SALES_STANDARD_CLASSIFICATIONS = {
	"Output - A Standard rate (excl capital goods)",
	"Output - B Standard rate (only capital goods)",
}
PURCHASE_INPUT_CLASSIFICATIONS = {
	"Input - A Capital goods and/or services supplied to you (local)",
	"Input - B Capital goods imported",
	"Input - C Other goods supplied to you (excl capital goods)",
	"Input - D Other goods imported (excl capital goods)",
}


def create_filing(vat_return, settings) -> str:
	"""Create one idempotent core filing from a submitted VAT201 snapshot."""
	if vat_return.za_filing:
		return vat_return.za_filing
	frappe.has_permission("ZA Filing", "create", throw=True)
	_validate_filing_configuration(vat_return, settings)
	payload = build_working_paper(vat_return)
	content = json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True).encode()
	checksum = hashlib.sha256(content).hexdigest()
	file_doc = save_file(
		f"{vat_return.name}-working-paper.json",
		content,
		"VAT201 Return",
		vat_return.name,
		is_private=1,
		df="working_paper_file",
	)
	currency = frappe.get_cached_value("Company", vat_return.company, "default_currency")
	filing = frappe.get_doc(
		{
			"doctype": "ZA Filing",
			"company": vat_return.company,
			"obligation": settings.vat201_compliance_obligation,
			"period_start": vat_return.from_date,
			"period_end": vat_return.to_date,
			"due_date": vat_return.filing_due_date,
			"currency": currency,
			"ledger_amount": calculate_ledger_amount(vat_return),
			"declared_amount": flt(vat_return.total_amount_payable) - flt(vat_return.vat_refundable),
			"paid_amount": 0,
			"reviewed_by": vat_return.filing_reviewer,
			"approved_by": vat_return.filing_approver,
			"working_paper": file_doc.file_url,
			"working_paper_sha256": checksum,
			"notes": (vat_return.notes or "").strip(),
		}
	)
	try:
		filing.insert()
	except frappe.DuplicateEntryError:
		filing_name = frappe.db.get_value(
			"ZA Filing",
			{
				"company": vat_return.company,
				"obligation": settings.vat201_compliance_obligation,
				"period_start": vat_return.from_date,
				"period_end": vat_return.to_date,
			},
			"name",
		)
		if not filing_name:
			raise
		filing = frappe.get_doc("ZA Filing", filing_name)
	vat_return.db_set(
		{
			"working_paper_file": file_doc.file_url,
			"working_paper_sha256": checksum,
			"za_filing": filing.name,
		},
		update_modified=False,
	)
	return filing.name


def record_submission_receipt(
	vat_return,
	*,
	authority_reference: str,
	response_status: str,
	evidence_file: str,
	sha256_checksum: str,
	submitted_by: str,
	submitted_at: str | None = None,
	notes: str | None = None,
) -> str:
	"""Prepare one private SARS response for independent submission, idempotently."""
	if not vat_return.za_filing:
		frappe.throw(_("Create and approve the linked ZA Filing before recording a SARS receipt."))
	frappe.has_permission("ZA Submission Receipt", "create", throw=True)
	existing = frappe.db.get_value(
		"ZA Submission Receipt",
		{"sha256_checksum": (sha256_checksum or "").strip().lower()},
		["name", "filing", "authority_reference", "response_status", "submitted_by", "docstatus"],
		as_dict=True,
	)
	if existing:
		if (
			existing.filing == vat_return.za_filing
			and existing.authority_reference == authority_reference
			and existing.response_status == response_status
			and existing.submitted_by == submitted_by
			and existing.docstatus in (0, 1)
		):
			return existing.name
		frappe.throw(_("This submission evidence checksum is already linked to a different response."))
	if submitted_by == frappe.session.user:
		frappe.throw(
			_("The receipt preparer and recorded response submitter must be different users."),
			frappe.PermissionError,
		)
	if not frappe.db.exists("User", submitted_by) or set(frappe.get_roles(submitted_by)).isdisjoint(
		APPROVAL_ROLES
	):
		frappe.throw(
			_("Submitted By must be a user with a ZA compliance approval role."),
			frappe.PermissionError,
		)

	receipt = frappe.get_doc(
		{
			"doctype": "ZA Submission Receipt",
			"filing": vat_return.za_filing,
			"authority_reference": authority_reference,
			"submitted_at": submitted_at or now_datetime(),
			"response_status": response_status,
			"submitted_by": submitted_by,
			"evidence_file": evidence_file,
			"sha256_checksum": sha256_checksum,
			"declared_amount": frappe.db.get_value("ZA Filing", vat_return.za_filing, "declared_amount"),
			"notes": notes,
		}
	)
	try:
		receipt.insert()
	except frappe.DuplicateEntryError:
		receipt_name = frappe.db.get_value(
			"ZA Submission Receipt",
			{"sha256_checksum": (sha256_checksum or "").strip().lower()},
			"name",
		)
		if not receipt_name:
			raise
		return receipt_name
	return receipt.name


def build_working_paper(vat_return) -> dict:
	"""Serialize only immutable VAT201 values needed for statutory reconstruction."""
	return {
		"schema": "za-local-finance/vat201-working-paper/v1",
		"vat201_return": vat_return.name,
		"company": vat_return.company,
		"vat_registration_number": vat_return.vat_registration_number,
		"filing_category": vat_return.filing_category,
		"period_start": str(vat_return.from_date),
		"period_end": str(vat_return.to_date),
		"snapshot_generated_on": str(vat_return.snapshot_generated_on),
		"live_ledger_sha256": vat_return.live_ledger_sha256,
		"source_snapshot_sha256": vat_return.source_snapshot_sha256,
		"gl_snapshot_sha256": vat_return.gl_snapshot_sha256,
		"source_vat_total": flt(vat_return.source_vat_total, 9),
		"gl_vat_total": flt(vat_return.gl_vat_total, 9),
		"reconciliation_difference": flt(vat_return.reconciliation_difference, 9),
		"reconciliation_status": vat_return.reconciliation_status,
		"declared": {
			"total_output_tax": flt(vat_return.total_output_tax, 9),
			"total_input_tax": flt(vat_return.total_input_tax, 9),
			"vat_payable": flt(vat_return.vat_payable, 9),
			"vat_refundable": flt(vat_return.vat_refundable, 9),
			"total_amount_payable": flt(vat_return.total_amount_payable, 9),
		},
		"manual_adjustment": {
			"type": vat_return.other_input_adjustment_type,
			"amount": flt(vat_return.other_input_adjustment, 9),
			"evidence": vat_return.adjustment_evidence,
			"evidence_sha256": vat_return.adjustment_evidence_sha256,
		},
		"transactions": [
			{
				"voucher_type": row.voucher_type,
				"voucher_no": row.voucher_no,
				"posting_date": str(row.posting_date),
				"classification": row.classification,
				"classification_status": row.classification_status,
				"tax_amount": flt(row.tax_amount, 9),
				"non_deductible_tax_amount": flt(row.non_deductible_tax_amount, 9),
				"input_treatment": row.input_treatment,
				"deduction_percentage": flt(row.deduction_percentage, 9),
				"source_snapshot_sha256": row.source_snapshot_sha256,
				"gl_snapshot_sha256": row.gl_snapshot_sha256,
				"reconciliation_status": row.reconciliation_status,
			}
			for row in vat_return.transactions
			if not row.is_cancelled
		],
	}


def calculate_ledger_amount(vat_return) -> float:
	output = sum(
		flt(row.gl_tax_amount)
		for row in vat_return.transactions
		if row.classification in SALES_STANDARD_CLASSIFICATIONS and not row.is_cancelled
	)
	input_tax = sum(
		flt(row.gl_tax_amount)
		for row in vat_return.transactions
		if row.classification in PURCHASE_INPUT_CLASSIFICATIONS and not row.is_cancelled
	)
	return flt(output - input_tax, 2)


def _validate_filing_configuration(vat_return, settings) -> None:
	missing = [
		label
		for fieldname, label in (
			("filing_due_date", _("Filing Due Date")),
			("filing_reviewer", _("Independent Filing Reviewer")),
			("filing_approver", _("Independent Filing Approver")),
		)
		if not vat_return.get(fieldname)
	]
	if not settings.vat201_compliance_obligation:
		missing.append(_("VAT201 Compliance Obligation in South Africa VAT Settings"))
	if missing:
		frappe.throw(_("Complete the filing controls before submitting: {0}.").format(", ".join(missing)))
	if vat_return.filing_reviewer == vat_return.filing_approver:
		frappe.throw(_("The filing reviewer and approver must be different users."))
