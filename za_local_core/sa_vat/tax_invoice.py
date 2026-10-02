import frappe
from frappe import _
from frappe.utils import cint, flt

from za_local_core.localisation import is_south_african_company
from za_local_core.sa_vat.statutory import (
	FULL_INVOICE_THRESHOLD,
	NO_INVOICE_THRESHOLD,
	resolve_vat_controls,
)


@frappe.whitelist(methods=["GET"])
def check_tax_invoice_readiness(sales_invoice: str):
	# check_permission=True is required: frappe.get_doc does NOT check permissions,
	# and the response exposes customer name, posting date and invoice totals.
	doc = frappe.get_doc("Sales Invoice", sales_invoice, check_permission=True)
	company_vat_number = get_company_vat_registration_number(doc.company) or getattr(
		doc, "company_tax_id", None
	)
	company_currency = get_company_currency(doc.company)
	recipient_vat_details = get_party_vat_details("Customer", getattr(doc, "customer", None))
	recipient_vat_number = getattr(doc, "tax_id", None) or recipient_vat_details.get("tax_id")
	profile = build_sales_invoice_print_profile(
		company=doc.company,
		posting_date=str(doc.posting_date),
		base_grand_total=getattr(doc, "base_grand_total", None),
		grand_total=getattr(doc, "grand_total", None),
		is_pos=getattr(doc, "is_pos", 0),
		is_return=getattr(doc, "is_return", 0),
		company_currency=company_currency,
		is_zero_rated_only=is_zero_rated_only_invoice(doc),
		is_exempt_only=is_exempt_only_invoice(doc),
	)
	full_invoice = profile["invoice_type"] == "full_tax_invoice"
	tax_invoice_required = profile["invoice_type"] not in {"no_tax_invoice_required", "exempt_supply_invoice"}

	checks = [
		check(
			"invoice_label",
			_("Invoice heading"),
			True,
			_("Use the recommended SA tax invoice or credit note print format."),
			required=tax_invoice_required,
		),
		check(
			"supplier_name", _("Supplier name"), bool(doc.company), doc.company, required=tax_invoice_required
		),
		check(
			"supplier_address",
			_("Supplier address"),
			bool(getattr(doc, "company_address_display", None)),
			_("Missing company address"),
			required=tax_invoice_required,
		),
		check(
			"supplier_vat_number",
			_("Supplier VAT number"),
			bool(company_vat_number),
			company_vat_number or _("Missing company VAT number"),
			required=tax_invoice_required,
		),
		check(
			"customer_name",
			_("Recipient name"),
			bool(getattr(doc, "customer_name", None)),
			getattr(doc, "customer_name", None) or _("Missing recipient name"),
			required=full_invoice,
		),
		check(
			"customer_address",
			_("Recipient address"),
			bool(getattr(doc, "address_display", None)),
			getattr(doc, "address_display", None) or _("Missing recipient address"),
			required=full_invoice,
		),
		check(
			"recipient_vat_number",
			_("Recipient VAT number"),
			bool(recipient_vat_number),
			recipient_vat_number or _("Required on a full tax invoice when the recipient is a VAT vendor."),
			required=bool(full_invoice and recipient_vat_details.get("za_is_vat_vendor")),
		),
		check(
			"serial_number",
			_("Invoice number"),
			bool(doc.name),
			doc.name,
			required=tax_invoice_required,
		),
		check(
			"issue_date",
			_("Issue date"),
			bool(getattr(doc, "posting_date", None)),
			getattr(doc, "posting_date", None),
			required=tax_invoice_required,
		),
		check(
			"line_descriptions",
			_("Item descriptions"),
			bool(doc.items) and all(bool((item.description or "").strip()) for item in doc.items),
			_("One or more items are missing a description"),
			required=tax_invoice_required,
		),
		check(
			"quantities",
			_("Item quantities"),
			bool(doc.items) and all(abs(flt(item.qty)) > 0 for item in doc.items),
			_("One or more items are missing quantity information"),
			required=full_invoice,
		),
		check(
			"value_of_supply",
			_("Value of supply"),
			profile["consideration"] > 0,
			profile["consideration"],
			required=tax_invoice_required,
		),
		check(
			"tax_amount",
			_("Tax amount"),
			doc.total_taxes_and_charges is not None,
			doc.total_taxes_and_charges,
			required=tax_invoice_required,
		),
		check(
			"total_consideration",
			_("Total consideration"),
			getattr(doc, "grand_total", None) is not None,
			getattr(doc, "grand_total", None),
			required=tax_invoice_required,
		),
	]

	if profile["invoice_type"] == "credit_note":
		# Section 21(3): a credit note must identify the original tax invoice and
		# briefly explain the circumstances that gave rise to it.
		checks += [
			check(
				"original_tax_invoice",
				_("Original tax invoice reference"),
				bool(getattr(doc, "return_against", None)),
				getattr(doc, "return_against", None) or _("Missing the invoice this note adjusts"),
			),
			check(
				"adjustment_reason",
				_("Reason for the adjustment"),
				bool((getattr(doc, "za_adjustment_reason", None) or "").strip()),
				_("Missing the reason for the credit note"),
			),
		]

	missing = [item["label"] for item in checks if item["required"] and not item["ok"]]
	return {
		"sales_invoice": doc.name,
		"status": (
			"not_required"
			if profile["invoice_type"] in {"no_tax_invoice_required", "exempt_supply_invoice"}
			else ("ready" if not missing else "attention")
		),
		"invoice_type": profile["invoice_type"],
		"recommended_print_format": profile["print_format"],
		"consideration": profile["consideration"],
		"checks": checks,
		"missing": missing,
		"threshold_guidance": {
			"full_tax_invoice_over": profile["full_invoice_threshold"],
			"no_tax_invoice_at_or_below": profile["no_invoice_threshold"],
			"currency": "ZAR",
			"basis": profile["threshold_basis"],
			"statutory_source": profile["statutory_source"],
			"statutory_rate_pack": profile["statutory_rate_pack"],
			"effective_from": profile["statutory_effective_from"],
			"effective_to": profile["statutory_effective_to"],
		},
	}


@frappe.whitelist(methods=["GET"])
def get_sales_invoice_print_profile(
	company: str | None = None,
	posting_date: str | None = None,
	base_grand_total: float | None = None,
	grand_total: float | None = None,
	is_pos: int = 0,
	is_return: int = 0,
	is_zero_rated_only: int = 0,
	is_exempt_only: int = 0,
):
	frappe.has_permission("Sales Invoice", "read", throw=True)
	if company:
		frappe.has_permission("Company", "read", company, throw=True)
	return build_sales_invoice_print_profile(
		company=company,
		posting_date=posting_date,
		base_grand_total=base_grand_total,
		grand_total=grand_total,
		is_pos=is_pos,
		is_return=is_return,
		is_zero_rated_only=is_zero_rated_only,
		is_exempt_only=is_exempt_only,
		company_currency=get_company_currency(company),
	)


def build_sales_invoice_print_profile(
	company: str | None,
	posting_date: str | None,
	base_grand_total: float | None = None,
	grand_total: float | None = None,
	is_pos: int = 0,
	is_return: int = 0,
	company_currency: str | None = None,
	is_zero_rated_only: int = 0,
	statutory_controls: dict | None = None,
	is_exempt_only: int = 0,
):
	if not posting_date:
		frappe.throw(
			_("Posting Date is required to resolve the approved tax-invoice thresholds."),
			title=_("Missing VAT Control Date"),
		)
	controls = statutory_controls or resolve_vat_controls(str(posting_date))
	values = controls["values"]
	no_invoice_threshold = flt(values[NO_INVOICE_THRESHOLD])
	full_invoice_threshold = flt(values[FULL_INVOICE_THRESHOLD])
	consideration = abs(flt(base_grand_total or grand_total or 0))
	threshold_basis = "base_grand_total_zar"
	if cint(is_return):
		invoice_type = "credit_note"
	elif cint(is_exempt_only):
		# Section 20 tax invoices are issued for taxable supplies only. A document for
		# exempt supplies alone is an ordinary invoice and must not be headed "tax invoice".
		invoice_type = "exempt_supply_invoice"
		threshold_basis = "exempt_supply"
	elif company_currency and company_currency != "ZAR":
		# The statutory thresholds are rand amounts. Without a ZAR company-currency
		# amount, use the stricter format instead of understating invoice requirements.
		invoice_type = "full_tax_invoice"
		threshold_basis = "conservative_non_zar_company_currency"
	else:
		invoice_type = get_invoice_type(
			consideration,
			no_invoice_threshold=no_invoice_threshold,
			full_invoice_threshold=full_invoice_threshold,
		)
		if cint(is_zero_rated_only) and invoice_type == "abridged_tax_invoice":
			invoice_type = "full_tax_invoice"
			threshold_basis = "zero_rated_full_particulars"
	recommended = get_recommended_print_format(invoice_type)
	is_sa_company = is_company_in_south_africa(company)
	preserve_existing = bool(cint(is_pos))
	return {
		"company": company,
		"consideration": consideration,
		"invoice_type": invoice_type,
		"threshold_basis": threshold_basis,
		"is_south_africa_company": is_sa_company,
		"preserve_existing_default": preserve_existing,
		"override_default": bool(is_sa_company and not preserve_existing and recommended),
		"print_format": recommended if is_sa_company else None,
		"no_invoice_threshold": no_invoice_threshold,
		"full_invoice_threshold": full_invoice_threshold,
		"statutory_source": controls["source"],
		"statutory_source_sha256": controls["source_sha256"],
		"statutory_rate_pack": controls["rate_pack"],
		"statutory_rate_pack_sha256": controls["rate_pack_sha256"],
		"statutory_effective_from": controls["effective_from"],
		"statutory_effective_to": controls["effective_to"],
	}


def is_zero_rated_only_invoice(doc) -> bool:
	"""Return true only when every line is explicitly classified as zero-rated."""
	if flt(getattr(doc, "total_taxes_and_charges", 0)) != 0 or not getattr(doc, "items", None):
		return False
	zero_categories = {"Zero Rated", "Export Zero Rated"}
	return all(
		getattr(item, "custom_sa_vat_category", None) in zero_categories
		or cint(getattr(item, "is_zero_rated", 0))
		for item in doc.items
	)


def is_exempt_only_invoice(doc) -> bool:
	"""Return true only when every line is explicitly classified as an exempt supply."""
	if flt(getattr(doc, "total_taxes_and_charges", 0)) != 0 or not getattr(doc, "items", None):
		return False
	return all(getattr(item, "custom_sa_vat_category", None) == "Exempt" for item in doc.items)


def get_invoice_type(consideration, *, no_invoice_threshold, full_invoice_threshold):
	if consideration <= flt(no_invoice_threshold):
		return "no_tax_invoice_required"
	if consideration <= flt(full_invoice_threshold):
		return "abridged_tax_invoice"
	return "full_tax_invoice"


def get_recommended_print_format(invoice_type):
	if invoice_type == "credit_note":
		return "SA Credit Note"
	if invoice_type == "full_tax_invoice":
		return "SA Full Tax Invoice"
	if invoice_type == "abridged_tax_invoice":
		return "SA Abridged Tax Invoice"
	return None


def is_company_in_south_africa(company: str | None):
	return is_south_african_company(company)


def get_company_vat_registration_number(company: str | None):
	if not company:
		return None
	values = frappe.db.get_value("Company", company, ["za_vat_number", "tax_id"], as_dict=True)
	if isinstance(values, dict):
		return values.get("za_vat_number") or values.get("tax_id")
	if isinstance(values, list | tuple):
		return next((value for value in values if value), None)
	return values


def get_company_currency(company: str | None):
	if not company:
		return None
	return frappe.db.get_value("Company", company, "default_currency", cache=True)


def get_party_vat_details(doctype: str, name: str | None):
	if not name:
		return frappe._dict()
	return frappe.db.get_value(doctype, name, ["tax_id", "za_is_vat_vendor"], as_dict=True) or frappe._dict()


def check(key, label, ok, detail=None, required=True):
	return {"key": key, "label": label, "ok": bool(ok), "detail": detail, "required": bool(required)}
