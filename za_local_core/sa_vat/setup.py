import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from za_local_core.sa_vat.statutory import apply_vat_controls

CLASSIFICATION_OPTIONS = "\n".join(
	[
		"",
		"Output - A Standard rate (excl capital goods)",
		"Output - B Standard rate (only capital goods)",
		"Output - C Zero Rated (excl goods exported)",
		"Output - D Zero Rated (only goods exported)",
		"Output - E Exempt",
		"Input - A Capital goods and/or services supplied to you (local)",
		"Input - B Capital goods imported",
		"Input - C Other goods supplied to you (excl capital goods)",
		"Input - D Other goods imported (excl capital goods)",
		"SARS Payment/Receipt",
	]
)

ITEM_VAT_CATEGORY_OPTIONS = "\n".join(
	[
		"",
		"Standard Rated",
		"Zero Rated",
		"Export Zero Rated",
		"Exempt",
		"Capital Goods",
		"Imported Capital Goods",
		"Imported Other Goods",
	]
)

INPUT_TREATMENT_OPTIONS = "\n".join(
	[
		"Fully Deductible",
		"Blocked",
		"Apportioned",
		"Imported Services",
		"Second-hand Goods",
	]
)

VAT_RETURN_SETTING_FIELD_MAP = [
	{
		"field_name": "standard_rate_non_capital",
		"classification": "Output - A Standard rate (excl capital goods)",
		"reference_doctype": "Sales Invoice",
	},
	{
		"field_name": "standard_rate_non_capital_2",
		"classification": "Output - A Standard rate (excl capital goods)",
		"reference_doctype": "Sales Invoice",
	},
	{
		"field_name": "standard_rate_capital",
		"classification": "Output - B Standard rate (only capital goods)",
		"reference_doctype": "Sales Invoice",
	},
	{
		"field_name": "zero_rate_non_exported",
		"classification": "Output - C Zero Rated (excl goods exported)",
		"reference_doctype": "Sales Invoice",
	},
	{
		"field_name": "zero_rate_exported",
		"classification": "Output - D Zero Rated (only goods exported)",
		"reference_doctype": "Sales Invoice",
	},
	{
		"field_name": "exempt",
		"classification": "Output - E Exempt",
		"reference_doctype": "Sales Invoice",
	},
	{
		"field_name": "input_capital_local",
		"classification": "Input - A Capital goods and/or services supplied to you (local)",
		"reference_doctype": "Purchase Invoice",
	},
	{
		"field_name": "input_capital_import",
		"classification": "Input - B Capital goods imported",
		"reference_doctype": "Purchase Invoice",
	},
	{
		"field_name": "input_goods_local",
		"classification": "Input - C Other goods supplied to you (excl capital goods)",
		"reference_doctype": "Purchase Invoice",
	},
	{
		"field_name": "input_goods_import",
		"classification": "Input - D Other goods imported (excl capital goods)",
		"reference_doctype": "Purchase Invoice",
	},
]

DEFAULT_TEMPLATE_SPECS = {
	"sales": [
		{
			"field_name": "standard_rate_non_capital",
			"title": "SA Standard Rated Sales {rate:g}%",
			"rate": None,
		},
		{"field_name": "standard_rate_capital", "title": "SA Capital Goods Sales {rate:g}%", "rate": None},
		{"field_name": "zero_rate_non_exported", "title": "SA Zero Rated Sales 0%", "rate": 0},
		{"field_name": "zero_rate_exported", "title": "SA Export Zero Rated Sales 0%", "rate": 0},
		{"field_name": "exempt", "title": "SA Exempt Sales 0%", "rate": 0},
	],
	"purchase": [
		{"field_name": "input_capital_local", "title": "SA Capital Purchases {rate:g}%", "rate": None},
		{"field_name": "input_capital_import", "title": "SA Capital Imports {rate:g}%", "rate": None},
		{"field_name": "input_goods_local", "title": "SA Standard Rated Purchases {rate:g}%", "rate": None},
		{"field_name": "input_goods_import", "title": "SA Other Imports {rate:g}%", "rate": None},
	],
}

DEFAULT_VAT_VENDOR_TYPES = [
	{
		"vendor_type": "Standard",
		"description": "Standard South African VAT vendor filing through the normal VAT system.",
		"filing_frequency": "Bi-Monthly",
		"notes": "Registration thresholds are resolved from approved date-effective statutory controls.",
	},
	{
		"vendor_type": "Micro Business",
		"description": "Smaller VAT vendor profile that may prefer lighter filing cadence where applicable.",
		"filing_frequency": "Quarterly",
		"notes": "Use only if the practitioner confirms this filing treatment applies.",
	},
	{
		"vendor_type": "Small Business",
		"description": "Small business VAT vendor profile using the standard registration threshold.",
		"filing_frequency": "Bi-Monthly",
		"notes": "Registration thresholds are resolved from approved date-effective statutory controls.",
	},
	{
		"vendor_type": "Voluntary",
		"description": "Voluntary VAT registration profile below the compulsory threshold.",
		"filing_frequency": "Bi-Monthly",
		"notes": "Use when the company has voluntarily registered for VAT; resolve the threshold by date.",
	},
	{
		"vendor_type": "Foreign Supplier",
		"description": "Foreign electronic services or offshore supplier VAT profile.",
		"filing_frequency": "Bi-Monthly",
		"notes": "Use only where the practitioner confirms the supplier falls into the foreign supplier VAT regime.",
	},
]

ALLOWED_ITEM_TAX_ACCOUNT_TYPES = {
	"Tax",
	"Chargeable",
	"Income Account",
	"Expense Account",
	"Expenses Included In Valuation",
}


def get_vat_settings(company: str | None = None, create_if_missing: bool = False):
	company = company or get_default_company()
	if not company:
		frappe.throw(_("Select a company before continuing with South Africa VAT setup."))

	existing = frappe.db.get_value("South Africa VAT Settings", {"company": company}, "name")
	if existing:
		return frappe.get_doc("South Africa VAT Settings", existing)

	if not create_if_missing:
		frappe.throw(_("South Africa VAT Settings is not configured for company {0}.").format(company))

	doc = frappe.get_doc(
		{
			"doctype": "South Africa VAT Settings",
			"company": company,
			"default_vat_report_company": company,
		}
	)
	doc.flags.ignore_permissions = True
	return doc


def get_default_company():
	return frappe.db.get_default("company") or frappe.db.get_value(
		"Company", {}, "name", order_by="creation asc"
	)


def get_default_vat_vendor_type():
	return (
		frappe.db.get_value("VAT Vendor Type", "Standard", "name")
		or frappe.db.get_value("VAT Vendor Type", "Voluntary", "name")
		or frappe.db.get_value("VAT Vendor Type", {}, "name", order_by="creation asc")
	)


def seed_vat_vendor_types():
	created = 0
	for spec in DEFAULT_VAT_VENDOR_TYPES:
		name = frappe.db.get_value("VAT Vendor Type", spec["vendor_type"], "name")
		if name:
			# These are installation defaults, not authoritative statutory records.
			# Never overwrite administrator/practitioner changes during migrate.
			continue

		doc = frappe.get_doc({"doctype": "VAT Vendor Type", **spec})
		doc.flags.ignore_permissions = True
		doc.insert()
		created += 1

	return {"created": created, "updated": 0}


def ensure_vat_custom_fields():
	create_custom_fields(
		{
			"Customer": [
				{
					"fieldname": "za_company_registration",
					"fieldtype": "Data",
					"label": "Company Registration Number",
					"insert_after": "tax_id",
					"description": "CIPC company registration number used on South African tax documents.",
					"module": "SA VAT",
				},
				{
					"fieldname": "za_is_vat_vendor",
					"fieldtype": "Check",
					"label": "Is VAT Vendor",
					"insert_after": "za_company_registration",
					"default": 0,
					"description": "Check if the customer is registered for VAT in South Africa.",
					"module": "SA VAT",
				},
			],
			"Sales Invoice": [
				{
					"fieldname": "za_adjustment_reason",
					"fieldtype": "Small Text",
					"label": "Reason for Adjustment",
					"insert_after": "return_against",
					"depends_on": "eval:doc.is_return",
					"allow_on_submit": 0,
					"description": "Brief explanation of the circumstances giving rise to this credit note "
					"(VAT Act section 21(3)). Printed on the credit note.",
					"module": "SA VAT",
				},
			],
			"Item Group": [
				{
					"fieldname": "is_capital_goods",
					"fieldtype": "Check",
					"label": "Is Capital Goods",
					"insert_after": "parent_item_group",
					"default": 0,
					"description": (
						"Mark this item group as capital goods for VAT201 input tax classification."
					),
					"module": "SA VAT",
				},
			],
			"Company": [
				{
					"fieldname": "za_vat_number",
					"fieldtype": "Data",
					"label": "South African VAT Number",
					"insert_after": "tax_id",
					"description": "South African VAT registration number used on VAT working papers and tax documents.",
					"length": 10,
					"module": "SA VAT",
				},
			],
			"Account": [
				{
					"fieldname": "custom_sa_vat_compliance_section",
					"fieldtype": "Section Break",
					"label": "South Africa VAT Compliance",
					"insert_after": "include_in_gross",
					"description": "Used to classify manual journal entries for VAT201 reporting.",
				},
				{
					"fieldname": "custom_vat_return_debit_classification",
					"fieldtype": "Select",
					"label": "VAT201 Debit Classification",
					"insert_after": "custom_sa_vat_compliance_section",
					"options": CLASSIFICATION_OPTIONS,
				},
				{
					"fieldname": "custom_vat_return_credit_classification",
					"fieldtype": "Select",
					"label": "VAT201 Credit Classification",
					"insert_after": "custom_vat_return_debit_classification",
					"options": CLASSIFICATION_OPTIONS,
				},
			],
			"Item": [
				{
					"fieldname": "is_zero_rated",
					"fieldtype": "Check",
					"label": "Is Zero Rated",
					"insert_after": "item_group",
					"print_hide": 1,
				},
				{
					"fieldname": "custom_sa_vat_category",
					"fieldtype": "Select",
					"label": "South Africa VAT Category",
					"insert_after": "is_zero_rated",
					"options": ITEM_VAT_CATEGORY_OPTIONS,
					"description": "Used to support VAT201 classification and tax invoice checks.",
				},
			],
			"Sales Invoice Item": [
				{
					"fieldname": "is_zero_rated",
					"fieldtype": "Check",
					"label": "Is Zero Rated",
					"insert_after": "description",
					"fetch_from": "item_code.is_zero_rated",
					"read_only": 1,
					"print_hide": 1,
				},
				{
					"fieldname": "custom_sa_vat_category",
					"fieldtype": "Data",
					"label": "South Africa VAT Category",
					"insert_after": "is_zero_rated",
					"fetch_from": "item_code.custom_sa_vat_category",
					"read_only": 1,
					"print_hide": 1,
				},
			],
			"Purchase Invoice Item": [
				{
					"fieldname": "is_zero_rated",
					"fieldtype": "Check",
					"label": "Is Zero Rated",
					"insert_after": "description",
					"fetch_from": "item_code.is_zero_rated",
					"read_only": 1,
					"print_hide": 1,
				},
				{
					"fieldname": "custom_sa_vat_category",
					"fieldtype": "Data",
					"label": "South Africa VAT Category",
					"insert_after": "is_zero_rated",
					"fetch_from": "item_code.custom_sa_vat_category",
					"read_only": 1,
					"print_hide": 1,
				},
				{
					"fieldname": "za_vat_input_treatment",
					"fieldtype": "Select",
					"label": "SA VAT Input Treatment",
					"insert_after": "custom_sa_vat_category",
					"options": INPUT_TREATMENT_OPTIONS,
					"default": "Fully Deductible",
					"description": (
						"Controls VAT201 deductibility. Imported services and second-hand goods "
						"remain practitioner-reviewed unless supported by an approved adjustment."
					),
					"module": "SA VAT",
				},
				{
					"fieldname": "za_vat_deduction_percentage",
					"fieldtype": "Percent",
					"label": "SA VAT Deduction Percentage",
					"insert_after": "za_vat_input_treatment",
					"default": "100",
					"description": "Required for apportioned input VAT; use zero for blocked input.",
					"module": "SA VAT",
				},
				{
					"fieldname": "za_vat_treatment_evidence",
					"fieldtype": "Data",
					"label": "SA VAT Treatment Evidence Reference",
					"insert_after": "za_vat_deduction_percentage",
					"description": "Practitioner-approved apportionment method or blocked-input rationale reference.",
					"module": "SA VAT",
				},
			],
		},
		update=True,
	)


def backfill_vat201_active_period_keys():
	"""Backfill one database-enforced key per open VAT period without rewriting conflicts."""
	if not frappe.db.table_exists("VAT201 Return"):
		return {"updated": 0, "conflicts": []}
	if not frappe.get_meta("VAT201 Return").has_field("active_period_key"):
		return {"updated": 0, "conflicts": []}

	from za_local_core.sa_vat.periods import build_active_period_key

	updated = 0
	conflicts = []
	claimed_keys = {}
	rows = frappe.get_all(
		"VAT201 Return",
		filters={"docstatus": ["!=", 2]},
		fields=["name", "company", "from_date", "to_date", "active_period_key"],
		order_by="creation asc, name asc",
	)
	for row in rows:
		if not (row.company and row.from_date and row.to_date):
			continue
		key = build_active_period_key(row.company, row.from_date, row.to_date)
		owner = claimed_keys.get(key)
		if owner:
			conflicts.append({"name": row.name, "conflicts_with": owner})
			continue
		claimed_keys[key] = row.name
		if row.active_period_key != key:
			frappe.db.set_value(
				"VAT201 Return",
				row.name,
				"active_period_key",
				key,
				update_modified=False,
			)
			updated += 1

	if conflicts:
		frappe.logger("za_local_core").warning(
			"VAT201 duplicate open periods require practitioner resolution",
			extra={"conflicts": conflicts},
		)
	return {"updated": updated, "conflicts": conflicts}


def backfill_vat201_filing_categories():
	"""Populate unambiguous historical VAT201 categories without guessing settings."""
	if not frappe.db.table_exists("VAT201 Return"):
		return {"updated": 0, "unresolved": []}

	meta = frappe.get_meta("VAT201 Return")
	if not meta.has_field("filing_category"):
		return {"updated": 0, "unresolved": []}

	from za_local_core.sa_vat.periods import resolve_filing_category, validate_filing_period

	updated = 0
	unresolved = []
	rows = frappe.get_all(
		"VAT201 Return",
		fields=["name", "tax_period", "filing_category", "from_date", "to_date"],
		order_by="creation asc, name asc",
	)
	for row in rows:
		if row.filing_category:
			continue
		try:
			category = resolve_filing_category(
				None,
				row.tax_period,
				row.from_date,
				row.to_date,
			)
			validate_filing_period(category, row.from_date, row.to_date)
		except frappe.ValidationError as exc:
			frappe.clear_last_message()
			unresolved.append({"name": row.name, "reason": str(exc)})
			continue

		frappe.db.set_value(
			"VAT201 Return",
			row.name,
			"filing_category",
			category,
			update_modified=False,
		)
		updated += 1

	if unresolved:
		frappe.logger("za_local_core").warning(
			"Historical VAT201 filing categories require practitioner review",
			extra={"returns": unresolved},
		)
	return {"updated": updated, "unresolved": unresolved}


def backfill_vat_settings_filing_categories():
	"""Migrate only unambiguous legacy company filing frequencies."""
	if not frappe.db.table_exists("South Africa VAT Settings"):
		return {"updated": 0, "unresolved": []}

	meta = frappe.get_meta("South Africa VAT Settings")
	if not meta.has_field("vat_filing_category"):
		return {"updated": 0, "unresolved": []}

	from za_local_core.sa_vat.periods import infer_legacy_filing_category

	updated = 0
	unresolved = []
	rows = frappe.get_all(
		"South Africa VAT Settings",
		fields=["name", "company", "vat_filing_frequency", "vat_filing_category"],
		order_by="creation asc, name asc",
	)
	for row in rows:
		if row.vat_filing_category:
			continue
		category = infer_legacy_filing_category(row.vat_filing_frequency)
		if not category:
			unresolved.append(
				{
					"name": row.name,
					"company": row.company,
					"legacy_frequency": row.vat_filing_frequency,
				}
			)
			continue
		frappe.db.set_value(
			"South Africa VAT Settings",
			row.name,
			"vat_filing_category",
			category,
			update_modified=False,
		)
		updated += 1

	if unresolved:
		frappe.logger("za_local_core").warning(
			"VAT filing categories require practitioner allocation",
			extra={"settings": unresolved},
		)
	return {"updated": updated, "unresolved": unresolved}


def sync_vat_accounts(settings):
	tracked = []
	for account in [settings.output_vat_account, settings.input_vat_account]:
		if account and account not in tracked:
			tracked.append(account)

	if hasattr(settings, "vat_accounts"):
		settings.vat_accounts = []
	if hasattr(settings, "tax_accounts"):
		settings.tax_accounts = []
	for account in tracked:
		settings.append("vat_accounts", {"doctype": "South Africa VAT Account", "account": account})
	return tracked


def is_valid_item_tax_account(account: str | None, company: str | None) -> bool:
	if not account or not company or not frappe.db.exists("Account", account):
		return False

	account_type, account_company = frappe.get_cached_value("Account", account, ["account_type", "company"])
	return account_company == company and account_type in ALLOWED_ITEM_TAX_ACCOUNT_TYPES


def validate_vat_posting_account(account: str | None, company: str, label: str):
	if not account:
		frappe.throw(_("{0} is required before VAT tax templates can be created.").format(label))

	values = frappe.db.get_value(
		"Account",
		account,
		["company", "account_type", "is_group", "disabled"],
		as_dict=True,
	)
	if not values:
		frappe.throw(_("Account {0} does not exist.").format(frappe.bold(account)))
	if values.company != company:
		frappe.throw(_("{0} must belong to company {1}.").format(label, frappe.bold(company)))
	if values.account_type != "Tax" or values.is_group or values.disabled:
		frappe.throw(_("{0} must be an enabled ledger account with Account Type Tax.").format(label))


def ensure_default_tax_templates(settings):
	company = settings.company
	if not company:
		frappe.throw(_("Select a company before applying recommended VAT templates."))
	validate_vat_posting_account(settings.output_vat_account, company, _("Output VAT Account"))
	validate_vat_posting_account(settings.input_vat_account, company, _("Input VAT Account"))
	standard_rate = frappe.utils.flt(settings.standard_vat_rate)
	if standard_rate <= 0:
		frappe.throw(_("Standard VAT Rate must be greater than zero."))

	created = {}
	for spec in DEFAULT_TEMPLATE_SPECS["sales"]:
		rate = standard_rate if spec["rate"] is None else spec["rate"]
		created[spec["field_name"]] = ensure_tax_template(
			doctype="Sales Taxes and Charges Template",
			title=f"{spec['title'].format(rate=rate)} - {company}",
			company=company,
			account=settings.output_vat_account,
			rate=rate,
		)
	for spec in DEFAULT_TEMPLATE_SPECS["purchase"]:
		rate = standard_rate if spec["rate"] is None else spec["rate"]
		created[spec["field_name"]] = ensure_tax_template(
			doctype="Purchase Taxes and Charges Template",
			title=f"{spec['title'].format(rate=rate)} - {company}",
			company=company,
			account=settings.input_vat_account,
			rate=rate,
		)

	for fieldname, template in created.items():
		if not getattr(settings, fieldname, None):
			setattr(settings, fieldname, template)

	ensure_item_tax_templates(settings, company)
	return created


def ensure_item_tax_templates(settings, company):
	item_tax_account = getattr(settings, "item_tax_template_account", None)
	if not item_tax_account:
		return

	if not is_valid_item_tax_account(item_tax_account, company):
		return

	standard_rate = frappe.utils.flt(settings.standard_vat_rate)
	for title, rate in [(f"SA Item Tax {standard_rate:g}%", standard_rate), ("SA Item Tax 0%", 0)]:
		existing_name = frappe.db.get_value(
			"Item Tax Template",
			{"title": f"{title} - {company}", "company": company},
			"name",
		)
		if existing_name:
			doc = frappe.get_doc("Item Tax Template", existing_name)
			doc.taxes = []
		else:
			doc = frappe.new_doc("Item Tax Template")
			doc.title = f"{title} - {company}"
			doc.company = company
		doc.append(
			"taxes",
			{
				"tax_type": item_tax_account,
				"tax_rate": rate,
			},
		)
		doc.flags.ignore_permissions = True
		if existing_name:
			doc.save()
		else:
			doc.insert()


def ensure_tax_template(doctype, title, company, account, rate):
	existing_name = frappe.db.get_value(doctype, {"title": title, "company": company}, "name")
	if existing_name:
		doc = frappe.get_doc(doctype, existing_name)
	else:
		doc = frappe.new_doc(doctype)
		doc.title = title
		doc.company = company

	doc.taxes = []
	doc.append(
		"taxes",
		{
			"charge_type": "On Net Total",
			"account_head": account,
			"rate": rate,
			"description": title,
		},
	)
	doc.flags.ignore_permissions = True
	if existing_name:
		doc.save()
	else:
		doc.insert()
	return doc.name


@frappe.whitelist(methods=["POST"])
def bootstrap_company_vat_setup(
	company: str | None = None,
	statutory_control_date: str | None = None,
):
	# Whitelisted and writes with ignore_permissions, reconfiguring VAT tax templates
	# and account mappings for a caller-supplied company.
	frappe.only_for("System Manager")

	settings = get_vat_settings(company, create_if_missing=True)
	company = company or settings.company
	if company and not settings.company:
		settings.company = company
	if statutory_control_date:
		settings.statutory_control_date = statutory_control_date
	# Resolve the approved controls before creating or updating any tax template.
	# This avoids partial setup when governance data is absent or unapproved.
	apply_vat_controls(settings)
	settings.default_vat_report_company = settings.company
	templates = ensure_default_tax_templates(settings)
	sync_vat_accounts(settings)
	settings.flags.ignore_permissions = True
	if settings.is_new():
		settings.insert()
	else:
		settings.save()
	tracked = [row.account for row in settings.vat_accounts]
	return settings.get_configuration_feedback(
		title=_("Recommended VAT Setup Applied"),
		message=_("Recommended VAT templates and VAT account tracking were applied for this company."),
		tracked=tracked,
		templates=templates,
	)


def migrate_legacy_vat_account_rows():
	if not frappe.db.table_exists("South Africa VAT Tax Account"):
		return 0

	legacy_rows = frappe.get_all(
		"South Africa VAT Tax Account",
		fields=["parent", "parenttype", "account", "idx"],
		filters={"parenttype": "South Africa VAT Settings"},
		order_by="parent asc, idx asc",
	)

	migrated = 0
	for row in legacy_rows:
		exists = frappe.db.exists(
			"South Africa VAT Account",
			{
				"parent": row.parent,
				"parenttype": "South Africa VAT Settings",
				"parentfield": "vat_accounts",
				"account": row.account,
			},
		)
		if exists:
			continue

		frappe.get_doc(
			{
				"doctype": "South Africa VAT Account",
				"parent": row.parent,
				"parenttype": "South Africa VAT Settings",
				"parentfield": "vat_accounts",
				"account": row.account,
				"idx": row.idx,
			}
		).insert(ignore_permissions=True)
		migrated += 1

	return migrated
