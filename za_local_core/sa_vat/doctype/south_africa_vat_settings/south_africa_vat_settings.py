import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from za_local_core.sa_vat.periods import FILING_CATEGORIES
from za_local_core.sa_vat.setup import (
	bootstrap_company_vat_setup,
	ensure_default_tax_templates,
	get_default_company,
	get_default_vat_vendor_type,
	is_valid_item_tax_account,
	sync_vat_accounts,
	validate_vat_posting_account,
)
from za_local_core.sa_vat.statutory import (
	apply_vat_controls,
)


class SouthAfricaVATSettings(Document):
	def load_from_db(self):
		super().load_from_db()
		self._set_vat_registration_number_from_company()
		self._ensure_default_vat_rates_on_load()
		self._set_mapping_doctype_defaults()

	def validate(self):
		self.ensure_company_default()
		self.apply_statutory_controls()
		self._set_mapping_doctype_defaults()
		self._default_vat_registration_number_from_company()
		self.validate_company_scope()
		self.validate_filing_category()
		self.validate_compliance_obligation()
		self.validate_vat_filing_day()
		self.validate_vat_rates()
		self.validate_vat_accounts()
		self.validate_item_tax_template_account()
		self.validate_company_vat_number()
		self.sync_vat_registration_number_to_company()
		self.validate_threshold_configuration()
		sync_vat_accounts(self)

	def apply_statutory_controls(self):
		apply_vat_controls(self)

	def ensure_company_default(self):
		if not self.company:
			self.company = get_default_company()

		if self.company:
			self.default_vat_report_company = self.company

		if not self.vat_vendor_type:
			self.vat_vendor_type = get_default_vat_vendor_type()

		if not self.vat_filing_day:
			self.vat_filing_day = 25

	def _set_mapping_doctype_defaults(self):
		self.output_tax_doctype = "Sales Taxes and Charges Template"
		self.input_tax_doctype = "Purchase Taxes and Charges Template"

	def _set_vat_registration_number_from_company(self):
		self.vat_registration_number = self._get_company_vat_registration_number()

	def _default_vat_registration_number_from_company(self):
		if not self.vat_registration_number:
			self._set_vat_registration_number_from_company()

	def _get_company_vat_registration_number(self):
		if not self.company:
			return ""

		values = frappe.db.get_value("Company", self.company, ["za_vat_number", "tax_id"], as_dict=True)
		if isinstance(values, dict):
			return values.get("za_vat_number") or values.get("tax_id") or ""
		if isinstance(values, list | tuple):
			return next((value for value in values if value), "") or ""
		return values or ""

	def _normalise_vat_registration_number(self):
		self.vat_registration_number = re.sub(r"[\s-]+", "", self.vat_registration_number or "")
		return self.vat_registration_number

	def validate_company_scope(self):
		if (
			self.company
			and self.default_vat_report_company
			and self.default_vat_report_company != self.company
		):
			frappe.throw(
				_(
					"Default VAT Report Company is a compatibility field and must match Company. Save the VAT settings against the correct company record instead of pointing to another company."
				)
			)

	def validate_vat_filing_day(self):
		if self.vat_filing_day not in (None, "") and not 1 <= int(self.vat_filing_day) <= 31:
			frappe.throw(_("VAT Filing Day must be between 1 and 31."))

	def validate_filing_category(self):
		if self.vat_filing_category in FILING_CATEGORIES:
			return
		if self.vat_filing_frequency:
			frappe.throw(
				_(
					"Legacy VAT Filing Frequency {0} is not sufficient for filing. Select the SARS-allocated VAT Filing Category A, B, C, D, or E."
				).format(frappe.bold(self.vat_filing_frequency))
			)
		frappe.throw(_("VAT Filing Category is required. Select the category allocated by SARS."))

	def validate_compliance_obligation(self):
		if not self.vat201_compliance_obligation:
			return
		values = frappe.db.get_value(
			"ZA Compliance Obligation",
			self.vat201_compliance_obligation,
			["domain", "docstatus", "active"],
			as_dict=True,
		)
		if not values:
			frappe.throw(_("VAT201 Compliance Obligation does not exist."))
		if values.domain != "VAT" or values.docstatus != 1 or not values.active:
			frappe.throw(_("VAT201 Compliance Obligation must be an active, approved VAT obligation."))

	def _ensure_default_vat_rates_on_load(self):
		self._prune_blank_vat_rates()
		self._normalise_vat_rate_rows()
		if self.vat_rates:
			return

		standard = getattr(self, "standard_vat_rate", None)
		if not standard:
			return
		self.append(
			"vat_rates",
			{
				"rate_name": "Standard Rate",
				"rate": standard,
				"is_standard_rate": 1,
				"description": "Standard VAT rate for South Africa",
			},
		)
		if getattr(self, "enable_zero_rated_items", 1):
			self.append(
				"vat_rates",
				{
					"rate_name": "Zero Rate",
					"rate": 0,
					"is_zero_rated": 1,
					"description": "Zero-rated items (0% VAT)",
				},
			)
		if getattr(self, "enable_exempt_items", 1):
			self.append(
				"vat_rates",
				{
					"rate_name": "Exempt",
					"rate": 0,
					"is_exempt": 1,
					"description": "VAT exempt items",
				},
			)
		self._normalise_vat_rate_rows()

	def _prune_blank_vat_rates(self):
		if not self.vat_rates:
			return

		clean_rows = []
		for row in self.vat_rates:
			has_content = any(
				[
					(row.rate_name or "").strip(),
					flt(row.rate),
					row.is_standard_rate,
					row.is_zero_rated,
					row.is_exempt,
					(row.description or "").strip(),
				]
			)
			if has_content:
				clean_rows.append(row.as_dict(no_default_fields=True))

		if len(clean_rows) != len(self.vat_rates):
			self.set("vat_rates", [])
			for row in clean_rows:
				self.append("vat_rates", row)

	def validate_vat_rates(self):
		self._ensure_default_vat_rates_on_load()

		rows_by_name = {(row.rate_name or "").strip().lower(): row for row in self.vat_rates if row.rate_name}

		standard_rate = rows_by_name.get("standard rate")
		if not standard_rate:
			self.append(
				"vat_rates",
				{
					"rate_name": "Standard Rate",
					"rate": self.standard_vat_rate,
					"is_standard_rate": 1,
					"description": "Standard VAT rate for South Africa",
				},
			)
		else:
			standard_rate.rate = self.standard_vat_rate
			standard_rate.is_standard_rate = 1

		if self.enable_zero_rated_items and "zero rate" not in rows_by_name:
			self.append(
				"vat_rates",
				{
					"rate_name": "Zero Rate",
					"rate": 0,
					"is_zero_rated": 1,
					"description": "Zero-rated items (0% VAT)",
				},
			)

		if self.enable_exempt_items and "exempt" not in rows_by_name:
			self.append(
				"vat_rates",
				{
					"rate_name": "Exempt",
					"rate": 0,
					"is_exempt": 1,
					"description": "VAT exempt items",
				},
			)

		self._normalise_vat_rate_rows()

	def _normalise_vat_rate_rows(self):
		standard_rate = flt(getattr(self, "standard_vat_rate", 0))
		for rate in self.vat_rates or []:
			rate_name = (rate.rate_name or "").strip().lower()
			if rate_name == "standard rate" or rate.is_standard_rate:
				rate.rate = standard_rate or flt(rate.rate)
				rate.is_standard_rate = 1
				rate.is_zero_rated = 0
				rate.is_exempt = 0
			elif rate_name == "zero rate" or rate.is_zero_rated:
				rate.rate = 0
				rate.is_standard_rate = 0
				rate.is_zero_rated = 1
				rate.is_exempt = 0
			elif rate_name == "exempt" or rate.is_exempt:
				rate.rate = 0
				rate.is_standard_rate = 0
				rate.is_zero_rated = 0
				rate.is_exempt = 1
			else:
				rate.rate = flt(rate.rate)

	def validate_vat_accounts(self):
		for account_field, label in (
			("input_vat_account", _("Input VAT Account")),
			("output_vat_account", _("Output VAT Account")),
		):
			account = getattr(self, account_field)
			if account:
				validate_vat_posting_account(account, self.company, label)

	def validate_item_tax_template_account(self):
		if not self.item_tax_template_account:
			return

		if not frappe.db.exists("Account", self.item_tax_template_account):
			frappe.throw(_("Account {0} does not exist").format(self.item_tax_template_account))

		account_company = frappe.db.get_value("Account", self.item_tax_template_account, "company")
		if account_company != self.company:
			frappe.throw(
				_("Item Tax Template Account must belong to company {0}.").format(frappe.bold(self.company))
			)

		if not is_valid_item_tax_account(self.item_tax_template_account, self.company):
			frappe.throw(
				_(
					"Item Tax Template Account must be an account of type Tax, Chargeable, Income, or Expense for company {0}."
				).format(frappe.bold(self.company))
			)

	def validate_company_vat_number(self):
		vat_number = self._normalise_vat_registration_number()
		if not vat_number:
			return

		if not re.match(r"^[0-9]{10}$", vat_number):
			frappe.throw(_("Company VAT Registration Number must be 10 digits."))

	def sync_vat_registration_number_to_company(self):
		if not self.company or not self.vat_registration_number:
			return
		frappe.has_permission("Company", "write", self.company, throw=True)

		updates = {}
		for fieldname in ("za_vat_number", "tax_id"):
			current_value = frappe.db.get_value("Company", self.company, fieldname)
			if current_value != self.vat_registration_number:
				updates[fieldname] = self.vat_registration_number

		if updates:
			frappe.db.set_value("Company", self.company, updates)

	def validate_threshold_configuration(self):
		if flt(self.standard_vat_rate) <= 0:
			frappe.throw(_("Standard VAT Rate must be greater than zero."))
		if flt(self.vat_registration_threshold) <= 0:
			frappe.throw(_("VAT Registration Threshold must be greater than zero."))
		if flt(self.vat_voluntary_threshold) <= 0:
			frappe.throw(_("VAT Voluntary Threshold must be greater than zero."))
		if flt(self.vat_voluntary_threshold) >= flt(self.vat_registration_threshold):
			frappe.throw(_("VAT Voluntary Threshold must be lower than the compulsory threshold."))
		if flt(self.no_invoice_threshold) < 0:
			frappe.throw(_("No Tax Invoice Threshold cannot be negative."))
		if flt(self.full_invoice_threshold) <= flt(self.no_invoice_threshold):
			frappe.throw(_("Full Tax Invoice Threshold must exceed the no-invoice threshold."))
		if not all(
			(
				self.statutory_rate_pack,
				self.statutory_rate_pack_sha256,
				self.statutory_source,
				self.statutory_source_sha256,
				self.statutory_effective_from,
				self.statutory_effective_to,
			)
		):
			frappe.throw(_("Approved VAT statutory provenance is incomplete."))

	def update_tax_templates(self):
		if not self.company:
			return

		ensure_default_tax_templates(self)

	def get_configuration_feedback(self, title, message, tracked=None, templates=None):
		tracked = tracked or [row.account for row in (self.vat_accounts or []) if row.account]
		template_names = list(dict.fromkeys((templates or {}).values()))
		warnings = self.get_configuration_warnings()

		return {
			"title": title,
			"indicator": "green",
			"message": message,
			"details": [
				{"label": _("Company"), "value": self.company},
				{"label": _("VAT Registration Number"), "value": self.vat_registration_number},
				{"label": _("VAT Vendor Type"), "value": self.vat_vendor_type},
				{"label": _("VAT Filing Category"), "value": self.vat_filing_category},
				{"label": _("Output VAT Account"), "value": self.output_vat_account},
				{"label": _("Input VAT Account"), "value": self.input_vat_account},
				{"label": _("Tracked VAT Accounts"), "value": tracked},
				{"label": _("Ensured Tax Templates"), "value": template_names},
			],
			"warnings": warnings,
			"next_steps": [
				_("Review the VAT201 Classification Mapping fields for this company."),
				_("Create or refresh a VAT201 Return and use Get VAT Transactions."),
				_("Run the ERPNext VAT Audit Report as a final accounting check."),
			],
			"settings": self.name,
			"vat_accounts": tracked,
			"tax_accounts": tracked,
			"templates": templates or {},
		}

	def get_configuration_warnings(self):
		warnings = []
		if not self.vat_registration_number:
			warnings.append(_("VAT Registration Number is still not configured."))
		elif not self.vat_registration_number.startswith("4"):
			warnings.append(_("South African VAT Registration Numbers typically start with '4'."))
		if self.input_vat_account and self.input_vat_account == self.output_vat_account:
			warnings.append(
				_(
					"Input VAT Account and Output VAT Account are the same. Confirm this legacy control-account pattern is intended."
				)
			)
		if not self.item_tax_template_account:
			warnings.append(_("Item Tax Template Account is optional; item tax templates were skipped."))
		if not self.statutory_source or not self.statutory_rate_pack:
			warnings.append(_("Approved date-effective VAT statutory controls are not resolved."))
		return warnings

	@frappe.whitelist(methods=["POST"])
	def bootstrap_defaults(self):
		self.check_permission("write")
		return bootstrap_company_vat_setup(self.company)

	@frappe.whitelist(methods=["POST"])
	def sync_vat_accounts(self):
		self.check_permission("write")
		tracked = sync_vat_accounts(self)
		self.flags.ignore_permissions = True
		if self.is_new():
			self.insert()
		else:
			self.save()
		return self.get_configuration_feedback(
			title=_("VAT Accounts Synced"),
			message=_("Tracked VAT tax accounts were synced for this company."),
			tracked=tracked,
		)
