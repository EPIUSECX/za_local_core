"""Deterministic end-to-end data for the isolated za_local test site."""

import hashlib
import json
from calendar import month_name, monthrange
from pathlib import Path

import frappe
from frappe import _
from frappe.utils import flt, getdate, today
from frappe.utils.file_manager import save_file

E2E_COMPANY = "Cohenix Localisation E2E"
E2E_COMPANY_ABBR = "CLE2E"
E2E_HOLIDAY_LIST = "ZA Local E2E Working Calendar 2026-2027"
E2E_EMPLOYEE_TYPE = "E2E Full-time"
E2E_PAYROLL_PAYABLE = f"Payroll Payable - {E2E_COMPANY_ABBR}"
E2E_SALARY_STRUCTURE = "ZA Local E2E Monthly Salary Structure"
E2E_TIMESHEET_STRUCTURE = "ZA Local E2E Timesheet Salary Structure"
E2E_MONTHLY_DEPARTMENT = f"Operations - {E2E_COMPANY_ABBR}"
E2E_TIMESHEET_DEPARTMENT = f"Research & Development - {E2E_COMPANY_ABBR}"
E2E_RECURRING_COMPONENT = "E2E Recurring Allowance"
E2E_BONUS_COMPONENT = "E2E Annual Bonus"
E2E_VAT_CUSTOMER = "ZA Local E2E VAT Customer"
E2E_VAT_SUPPLIER = "ZA Local E2E VAT Supplier"
E2E_VAT_ITEM = "ZA-LOCAL-E2E-SERVICE"


def stage_foundation():
	"""Run ERPNext's supported setup flow for a South African test company."""
	_require_isolated_test_site()
	if not frappe.db.get_single_value("System Settings", "language"):
		frappe.db.set_single_value("System Settings", "language", "en")

	if not frappe.db.exists("Company", E2E_COMPANY):
		from erpnext.setup.setup_wizard.setup_wizard import setup_complete

		setup_complete(
			frappe._dict(
				{
					"fy_start_date": "2026-03-01",
					"fy_end_date": "2027-02-28",
					"company_name": E2E_COMPANY,
					"company_abbr": E2E_COMPANY_ABBR,
					"currency": "ZAR",
					"country": "South Africa",
					"language": "en",
					"chart_of_accounts": "Standard",
					"domain": "Services",
					"bank_account": "E2E Bank",
				}
			)
		)

	# A restored E2E database can already contain the deterministic company while
	# retaining fresh-site setup flags. Keep this isolated staging helper
	# self-healing so browser and API sign-off runs open Desk, not Setup Wizard.
	frappe.db.set_value(
		"Installed Application",
		{"app_name": ["in", ["frappe", "erpnext"]]},
		"is_setup_complete",
		1,
		update_modified=False,
	)
	frappe.db.set_single_value("System Settings", "setup_complete", 1)
	frappe.db.set_default("desktop:home_page", "workspace")

	from za_local_payroll.setup.masters import repair_salary_component_accounts, seed_payroll_masters
	from za_local_payroll.setup.statutory import ensure_company_tax_configuration

	from za_local_core.accounts.setup_chart import load_sa_chart_of_accounts

	company_address = _ensure_address("ZA Local E2E Business Address", "Company", E2E_COMPANY)
	frappe.db.set_value(
		"Company",
		E2E_COMPANY,
		{
			"tax_id": "4123456789",
			"za_vat_number": "4123456789",
			"za_paye_reference_number": "7123456789",
			"za_sdl_reference_number": "L123456789",
			"za_uif_reference_number": "U123456789",
			"za_business_address": company_address,
		},
	)
	ensure_company_tax_configuration(E2E_COMPANY)
	load_sa_chart_of_accounts(E2E_COMPANY)
	frappe.db.set_single_value("Payroll Settings", "za_eti_unregulated_minimum_monthly_wage", 2500)
	seed_payroll_masters()
	repair_salary_component_accounts(E2E_COMPANY)
	frappe.db.commit()

	return {
		"company": E2E_COMPANY,
		"payroll_periods": frappe.db.count("Payroll Period", {"company": E2E_COMPANY}),
		"income_tax_slabs": frappe.db.count("Income Tax Slab", {"company": E2E_COMPANY}),
		"travel_rates": frappe.db.count("Travel Allowance Rate", {"company": E2E_COMPANY}),
	}


def stage_payroll_masters():
	"""Create employees, working calendar, structures and assignments."""
	_require_isolated_test_site()
	stage_foundation()

	holiday_list = _ensure_working_calendar()
	frappe.db.set_value("Company", E2E_COMPANY, "default_holiday_list", holiday_list)
	_ensure_holiday_list_assignment(holiday_list)
	frappe.db.set_value("Account", E2E_PAYROLL_PAYABLE, "account_type", "Payable")
	frappe.db.set_value(
		"Company",
		E2E_COMPANY,
		"default_payroll_payable_account",
		E2E_PAYROLL_PAYABLE,
	)
	_ensure_company_bank_account()
	frappe.db.set_value("Salary Component", "Basic", "za_eti_wage_component", 1)
	for gender in ("Male", "Female"):
		if not frappe.db.exists("Gender", gender):
			frappe.get_doc({"doctype": "Gender", "gender": gender}).insert(ignore_permissions=True)

	if not frappe.db.exists("Employee Type", E2E_EMPLOYEE_TYPE):
		frappe.get_doc(
			{
				"doctype": "Employee Type",
				"employee_type": E2E_EMPLOYEE_TYPE,
				"payroll_payable_account": E2E_PAYROLL_PAYABLE,
			}
		).insert(ignore_permissions=True)

	employees = {
		"regular": _ensure_employee(
			"Regular", "1990-01-15", "e2e.regular@cohenix.test", 5000, E2E_MONTHLY_DEPARTMENT
		),
		"eti": _ensure_employee("ETI", "2002-05-10", "e2e.eti@cohenix.test", 5001, E2E_MONTHLY_DEPARTMENT),
		"timesheet": _ensure_employee(
			"Timesheet",
			"1995-07-20",
			"e2e.timesheet@cohenix.test",
			5002,
			E2E_TIMESHEET_DEPARTMENT,
		),
	}

	_ensure_salary_structure(E2E_SALARY_STRUCTURE)
	_ensure_salary_structure(E2E_TIMESHEET_STRUCTURE, timesheet_based=True)
	_ensure_salary_structure_assignment(employees["regular"], E2E_SALARY_STRUCTURE, 30000)
	_ensure_salary_structure_assignment(employees["eti"], E2E_SALARY_STRUCTURE, 6000)
	_ensure_salary_structure_assignment(employees["timesheet"], E2E_TIMESHEET_STRUCTURE, 0)
	frappe.db.commit()
	return {
		"employees": employees,
		"holiday_list": holiday_list,
		"salary_structures": [E2E_SALARY_STRUCTURE, E2E_TIMESHEET_STRUCTURE],
	}


def stage_monthly_payroll():
	"""Run and submit the September 2026 monthly payroll scenario."""
	_require_isolated_test_site()
	masters = stage_payroll_masters()
	_ensure_payroll_additional_salaries(masters["employees"])
	return _stage_payroll_month(2026, 9)


def stage_payroll_year_to_date():
	"""Run chronological monthly payrolls from March through September 2026."""
	_require_isolated_test_site()
	masters = stage_payroll_masters()
	_ensure_payroll_additional_salaries(masters["employees"])
	payrolls = [_stage_payroll_month(2026, month) for month in range(3, 10)]
	return {
		"company": E2E_COMPANY,
		"payrolls": payrolls,
		"submitted_salary_slips": frappe.db.count(
			"Salary Slip",
			{
				"company": E2E_COMPANY,
				"start_date": [">=", "2026-03-01"],
				"end_date": ["<=", "2026-09-30"],
				"docstatus": 1,
			},
		),
	}


def stage_interim_statutory_reconciliation():
	"""Create submitted March-August EMP201s, IRP5s and the interim EMP501."""
	_require_isolated_test_site()
	stage_payroll_year_to_date()

	emp201_names = []
	for month in range(3, 9):
		emp201_names.append(_ensure_emp201(month_name[month]))

	existing = frappe.db.get_value(
		"EMP501 Reconciliation",
		{
			"company": E2E_COMPANY,
			"tax_year": "2026-2027",
			"reconciliation_period": "Interim",
			"docstatus": ["<", 2],
		},
		"name",
	)
	if existing:
		emp501 = frappe.get_doc("EMP501 Reconciliation", existing)
	else:
		emp501 = frappe.get_doc(
			{
				"doctype": "EMP501 Reconciliation",
				"company": E2E_COMPANY,
				"tax_year": "2026-2027",
				"reconciliation_period": "Interim",
				"submission_date": "2026-10-01",
			}
		)
		emp501.insert(ignore_permissions=True)

	if emp501.docstatus == 0:
		emp501.fetch_emp201_submissions()
		generation = emp501.generate_irp5_certificates()
		if generation.get("errors"):
			frappe.throw(
				_("IRP5 generation failed for the isolated E2E reconciliation: {0}").format(
					frappe.as_json(generation["errors"])
				)
			)

		for row in emp501.irp5_certificates:
			certificate = frappe.get_doc("IRP5 Certificate", row.irp5_certificate)
			if certificate.docstatus != 0:
				continue
			if not certificate.paye:
				certificate.reason_for_non_deduction = "02"
			certificate.save(ignore_permissions=True)
			certificate.submit()

		emp501.reload()
		emp501.submit()
	frappe.db.commit()
	return {
		"emp201_submissions": emp201_names,
		"emp501": emp501.name,
		"emp501_docstatus": emp501.docstatus,
		"certificates": frappe.get_all(
			"IRP5 Certificate",
			filters={"emp501_reconciliation": emp501.name},
			fields=["name", "employee", "certificate_type", "paye", "docstatus", "status"],
			order_by="employee asc",
		),
	}


def stage_coida_assessment():
	"""Create a submitted COIDA annual return from the staged payroll evidence."""
	_require_isolated_test_site()
	stage_test_coida_governance()
	stage_payroll_year_to_date()
	stage_timesheet_payroll()

	settings = frappe.get_single("COIDA Settings")
	settings.registration_number = "E2E-COIDA-001"
	settings.reference_number = "E2E-ROE-001"
	settings.assessment_year = "2026-2027"
	if not any(
		row.company == E2E_COMPANY and row.industry_class == "E2E Services" for row in settings.industry_rates
	):
		settings.append(
			"industry_rates",
			{
				"company": E2E_COMPANY,
				"industry_class": "E2E Services",
				"industry_description": "Isolated test-site professional services",
				"assessment_rate": 1.25,
			},
		)
	settings.save(ignore_permissions=True)

	name = f"COIDA-{E2E_COMPANY}-2026-2027"
	if frappe.db.exists("COIDA Annual Return", name):
		doc = frappe.get_doc("COIDA Annual Return", name)
	else:
		doc = frappe.get_doc(
			{
				"doctype": "COIDA Annual Return",
				"company": E2E_COMPANY,
				"industry_class": "E2E Services",
				"fiscal_year": "2026-2027",
				"total_annual_earnings": 0,
				"total_employees": 0,
			}
		)
		doc.insert(ignore_permissions=True)

	if doc.docstatus == 0:
		doc.fetch_employee_data()
		doc.save(ignore_permissions=True)
		doc.submit()
	frappe.db.commit()
	return {
		"coida_return": doc.name,
		"docstatus": doc.docstatus,
		"employees": doc.total_employees,
		"assessable_earnings": doc.total_annual_earnings,
		"assessment_fee": doc.assessment_fee,
	}


def stage_test_coida_governance():
	"""Approve deterministic COIDA controls only on the isolated E2E site.

	The attachment is synthetic test evidence. Production sites must retrieve,
	independently review, and approve the applicable Compensation Fund source.
	"""
	_require_isolated_test_site()
	if "za_local_workplace" not in frappe.get_installed_apps():
		frappe.throw(_("Install ZA Local Workplace before staging COIDA governance."))

	from za_local_core.services.rates import resolve_rate

	try:
		return resolve_rate("COIDA", "coida.annual_earnings_cap", "2026-03-01")
	except frappe.ValidationError:
		frappe.clear_messages()

	reviewer = _ensure_test_compliance_reviewer()
	source_key = "TEST-E2E-COIDA-CONTROLS-2026"
	source_name = frappe.db.get_value("ZA Statutory Source", {"catalog_key": source_key}, "name")
	if source_name:
		source = frappe.get_doc("ZA Statutory Source", source_name)
	else:
		source = frappe.get_doc(
			{
				"doctype": "ZA Statutory Source",
				"catalog_key": source_key,
				"authority": "Compensation Fund",
				"title": "_E2E COIDA controls (test evidence only)",
				"document_type": "Test Governance Evidence",
				"version": "2026-E2E",
				"publication_date": "2026-04-17",
				"effective_from": "2026-03-01",
				"effective_to": "2027-02-28",
				"source_url": "https://www.labour.gov.za/DocumentCenter/Pages/default.aspx",
				"reviewed_by": reviewer,
				"notes": (
					"Synthetic, deterministic evidence for the isolated E2E site. It must never be "
					"copied into a production source register."
				),
			}
		).insert(ignore_permissions=True)

	if source.docstatus == 0:
		content = json.dumps(
			{
				"scope": "isolated-e2e-only",
				"authority_reference": "COIDA-GAZETTE-54577-NOTICE-3910",
				"values": {
					"coida.annual_earnings_cap": 668000,
					"coida.minimum_assessment": 1621,
					"coida.domestic_minimum_assessment": 560,
					f"coida.assessment_rate.{E2E_COMPANY}.E2E Services": 1.25,
				},
			},
			sort_keys=True,
		).encode()
		file_doc = save_file(
			"_e2e-coida-governance.json",
			content,
			"ZA Statutory Source",
			source.name,
			is_private=1,
		)
		source.source_file = file_doc.file_url
		source.sha256_checksum = hashlib.sha256(content).hexdigest()
		source.reviewed_by = reviewer
		source.save(ignore_permissions=True)
		_submit_as(source, reviewer)

	pack_title = "_E2E Approved COIDA Controls 2026-2027"
	pack_name = frappe.db.get_value(
		"ZA Statutory Rate Pack", {"title": pack_title, "docstatus": ["<", 2]}, "name"
	)
	pack = (
		frappe.get_doc("ZA Statutory Rate Pack", pack_name)
		if pack_name
		else frappe.new_doc("ZA Statutory Rate Pack")
	)
	if pack.docstatus == 0:
		pack.update(
			{
				"domain": "COIDA",
				"title": pack_title,
				"source": source.name,
				"effective_from": "2026-03-01",
				"effective_to": "2027-02-28",
				"reviewed_by": reviewer,
				"notes": "Approved only for deterministic isolated-site E2E execution.",
			}
		)
		pack.set("items", [])
		for rule_key, value, unit in (
			("coida.annual_earnings_cap", 668000, "Amount"),
			("coida.minimum_assessment", 1621, "Amount"),
			("coida.domestic_minimum_assessment", 560, "Amount"),
			(f"coida.assessment_rate.{E2E_COMPANY}.E2E Services", 1.25, "Percentage"),
		):
			pack.append(
				"items",
				{"rule_key": rule_key, "numeric_value": value, "unit": unit, "precision": 2},
			)
		if pack.is_new():
			pack.insert(ignore_permissions=True)
		else:
			pack.save(ignore_permissions=True)
		_submit_as(pack, reviewer)
	frappe.db.commit()
	return resolve_rate("COIDA", "coida.annual_earnings_cap", "2026-03-01")


def stage_vat_cycle():
	"""Post sales and purchase VAT evidence and submit a VAT201 working paper."""
	_require_isolated_test_site()
	stage_foundation()

	if "za_local_core" not in frappe.get_installed_apps():
		frappe.throw(_("Install ZA Local Finance before staging the VAT end-to-end scenario."))

	from za_local_core.sa_vat.setup import bootstrap_company_vat_setup, get_vat_settings

	stage_test_vat_governance()
	settings = get_vat_settings(E2E_COMPANY, create_if_missing=True)
	settings.output_vat_account = _get_e2e_account("VAT Collected - Sales")
	settings.input_vat_account = _get_e2e_account("VAT Paid - Purchases")
	settings.statutory_control_date = "2026-07-15"
	settings.standard_vat_rate = 15
	settings.vat_filing_category = "Category C"
	settings.vat_filing_frequency = "Monthly"
	settings.vat201_compliance_obligation = _ensure_test_vat_obligation()
	settings.flags.ignore_permissions = True
	if settings.is_new():
		settings.insert()
	else:
		settings.save()
	bootstrap_company_vat_setup(E2E_COMPANY)
	settings.reload()

	customer = _ensure_vat_customer()
	supplier = _ensure_vat_supplier()
	_ensure_vat_item()
	sales_invoice = _ensure_vat_invoice(
		"Sales Invoice",
		customer,
		settings.standard_rate_non_capital,
		1_000,
	)
	purchase_invoice = _ensure_vat_invoice(
		"Purchase Invoice",
		supplier,
		settings.input_goods_local,
		400,
	)

	existing = frappe.db.get_value(
		"VAT201 Return",
		{
			"company": E2E_COMPANY,
			"from_date": "2026-07-01",
			"to_date": "2026-07-31",
			"docstatus": ["<", 2],
		},
		"name",
	)
	if existing:
		vat_return = frappe.get_doc("VAT201 Return", existing)
	else:
		vat_return = frappe.get_doc(
			{
				"doctype": "VAT201 Return",
				"company": E2E_COMPANY,
				"tax_period": "Monthly",
				"filing_category": "Category C",
				"from_date": "2026-07-01",
				"to_date": "2026-07-31",
				"submission_date": "2026-08-01",
				"status": "Draft",
			}
		)
		vat_return.insert(ignore_permissions=True)

	if vat_return.docstatus == 0:
		vat_return.filing_due_date = "2026-08-25"
		vat_return.filing_reviewer = _ensure_test_compliance_reviewer()
		vat_return.filing_approver = _ensure_test_compliance_approver()
		vat_return.get_vat_transactions()
		vat_return.save(ignore_permissions=True)
		if vat_return.unresolved_transaction_count:
			diagnostics = frappe.get_all(
				"Sales Taxes and Charges",
				filters={"parent": sales_invoice},
				fields=["account_head", "rate", "base_tax_amount"],
			)
			frappe.throw(
				_("VAT201 E2E transactions need review: {0}. Template: {1}. Sales tax rows: {2}").format(
					vat_return.unresolved_issues_summary,
					frappe.db.get_value("Sales Invoice", sales_invoice, "taxes_and_charges"),
					frappe.as_json(diagnostics),
				)
			)
		vat_return.submit()
	frappe.db.commit()
	return {
		"sales_invoice": sales_invoice,
		"purchase_invoice": purchase_invoice,
		"vat201_return": vat_return.name,
		"docstatus": vat_return.docstatus,
		"linked_transactions": len(vat_return.transactions),
		"output_tax": vat_return.total_output_tax,
		"input_tax": vat_return.total_input_tax,
		"vat_payable": vat_return.vat_payable,
	}


def stage_vat_filing_lifecycle():
	"""Complete the isolated VAT review, approval, and synthetic receipt lifecycle."""
	_require_isolated_test_site()
	result = stage_vat_cycle()
	vat_return = frappe.get_doc("VAT201 Return", result["vat201_return"])
	if not vat_return.za_filing:
		frappe.throw(_("The staged VAT201 Return did not create its governed filing."))

	reviewer = _ensure_test_compliance_reviewer()
	approver = _ensure_test_compliance_approver()
	filing = frappe.get_doc("ZA Filing", vat_return.za_filing)
	if filing.docstatus == 0 and filing.status == "Draft":
		original_user = frappe.session.user
		try:
			frappe.set_user(reviewer)
			filing.mark_reviewed()
		finally:
			frappe.set_user(original_user)
		filing.reload()
	if filing.docstatus == 0:
		_submit_as(filing, approver)
		filing.reload()

	authority_reference = "_E2E-SARS-VAT201-ACCEPTED-2026-07"
	receipt_name = frappe.db.get_value(
		"ZA Submission Receipt",
		{
			"filing": filing.name,
			"authority_reference": authority_reference,
			"docstatus": ["<", 2],
		},
		"name",
	)
	if receipt_name:
		receipt = frappe.get_doc("ZA Submission Receipt", receipt_name)
	else:
		receipt_content = b"Synthetic accepted VAT201 receipt for isolated E2E evidence only."
		receipt_file = save_file(
			"_e2e-accepted-vat201.txt",
			receipt_content,
			None,
			None,
			is_private=1,
		)
		original_user = frappe.session.user
		try:
			frappe.set_user(reviewer)
			receipt_name = vat_return.record_submission_receipt(
				authority_reference=authority_reference,
				response_status="Accepted",
				evidence_file=receipt_file.file_url,
				sha256_checksum=hashlib.sha256(receipt_content).hexdigest(),
				submitted_by=approver,
				submitted_at="2026-08-20 10:00:00",
				notes="Synthetic isolated-site evidence; not a real SARS response.",
			)
		finally:
			frappe.set_user(original_user)
		receipt = frappe.get_doc("ZA Submission Receipt", receipt_name)
	if receipt.docstatus == 0:
		_submit_as(receipt, approver)
		receipt.reload()
	vat_return.reload()
	frappe.db.commit()
	return {
		"vat201_return": vat_return.name,
		"vat201_status": vat_return.status,
		"filing": filing.name,
		"filing_docstatus": filing.docstatus,
		"filing_status": filing.status,
		"receipt": receipt.name,
		"receipt_docstatus": receipt.docstatus,
		"receipt_status": receipt.response_status,
	}


def stage_test_vat_governance():
	"""Approve deterministic VAT controls only on the isolated E2E site.

	This is test evidence, not a production statutory seed. Production sources
	must be independently retrieved, checked and approved through the core UI.
	"""
	_require_isolated_test_site()
	if "za_local_core" not in frappe.get_installed_apps():
		frappe.throw(_("Install ZA Local Finance before staging VAT governance."))

	from za_local_core.sa_vat.statutory import (
		CURRENT_APPROVED_SOURCE_METADATA,
		VAT_CONTROL_UNITS,
		resolve_vat_controls,
	)

	try:
		return resolve_vat_controls("2026-07-15")
	except frappe.ValidationError:
		frappe.clear_messages()

	reviewer = _ensure_test_compliance_reviewer()
	source_key = "TEST-E2E-VAT-CONTROLS-2026"
	source_name = frappe.db.get_value("ZA Statutory Source", {"catalog_key": source_key}, "name")
	if source_name:
		source = frappe.get_doc("ZA Statutory Source", source_name)
	else:
		source = frappe.get_doc(
			{
				"doctype": "ZA Statutory Source",
				"catalog_key": source_key,
				"authority": "SARS",
				"title": "_E2E VAT control source (test evidence only)",
				"document_type": "Test Governance Evidence",
				"version": "2026-E2E",
				"publication_date": "2026-04-01",
				"effective_from": "2026-04-01",
				"effective_to": "2027-03-31",
				"source_url": CURRENT_APPROVED_SOURCE_METADATA["rate_source_url"],
				"reviewed_by": reviewer,
				"notes": (
					"Synthetic, deterministic evidence for the isolated E2E site. It must never be "
					"copied into a production source register."
				),
			}
		).insert(ignore_permissions=True)

	if source.docstatus == 0:
		content = json.dumps(
			{
				"scope": "isolated-e2e-only",
				"source_metadata": CURRENT_APPROVED_SOURCE_METADATA,
			},
			sort_keys=True,
		).encode()
		file_doc = save_file(
			"_e2e-vat-governance.json",
			content,
			"ZA Statutory Source",
			source.name,
			is_private=1,
		)
		source.source_file = file_doc.file_url
		source.sha256_checksum = hashlib.sha256(content).hexdigest()
		source.reviewed_by = reviewer
		source.save(ignore_permissions=True)
		_submit_as(source, reviewer)

	pack_title = "_E2E Approved VAT Controls 2026-2027"
	pack_name = frappe.db.get_value(
		"ZA Statutory Rate Pack", {"title": pack_title, "docstatus": ["<", 2]}, "name"
	)
	pack = (
		frappe.get_doc("ZA Statutory Rate Pack", pack_name)
		if pack_name
		else frappe.new_doc("ZA Statutory Rate Pack")
	)
	if pack.docstatus == 0:
		pack.update(
			{
				"domain": "VAT",
				"title": pack_title,
				"source": source.name,
				"effective_from": "2026-04-01",
				"effective_to": "2027-03-31",
				"reviewed_by": reviewer,
				"notes": "Approved only for deterministic isolated-site E2E execution.",
			}
		)
		pack.set("items", [])
		for rule_key, value in CURRENT_APPROVED_SOURCE_METADATA["expected_current_values"].items():
			pack.append(
				"items",
				{
					"rule_key": rule_key,
					"numeric_value": value,
					"unit": VAT_CONTROL_UNITS[rule_key],
					"precision": 2,
				},
			)
		if pack.is_new():
			pack.insert(ignore_permissions=True)
		else:
			pack.save(ignore_permissions=True)
		_submit_as(pack, reviewer)
	frappe.db.commit()
	return resolve_vat_controls("2026-07-15")


def _ensure_test_vat_obligation() -> str:
	obligation_code = "TEST-E2E-VAT201-2026"
	existing = frappe.db.get_value(
		"ZA Compliance Obligation",
		{"obligation_code": obligation_code, "docstatus": ["<", 2]},
		"name",
	)
	if existing:
		return existing

	source = frappe.db.get_value(
		"ZA Statutory Source",
		{"catalog_key": "TEST-E2E-VAT-CONTROLS-2026", "docstatus": 1},
		"name",
	)
	if not source:
		frappe.throw(_("Stage the approved E2E VAT source before creating its obligation."))

	doc = frappe.get_doc(
		{
			"doctype": "ZA Compliance Obligation",
			"obligation_code": obligation_code,
			"title": "_E2E VAT201 controlled-manual obligation",
			"domain": "VAT",
			"authority": "SARS",
			"source": source,
			"frequency": "Monthly",
			"due_rule": "E2E practitioner-confirmed due date",
			"capability": "Controlled Manual",
			"effective_from": "2026-04-01",
			"effective_to": "2027-03-31",
			"notes": "Synthetic obligation for isolated end-to-end testing only.",
		}
	).insert(ignore_permissions=True)
	doc.submit()
	return doc.name


def stage_eft_payment_batch():
	"""Submit a payroll payment batch and generate its private FNB OBE CSV."""
	_require_isolated_test_site()
	payroll = stage_monthly_payroll()
	payroll_entry = payroll["payroll_entry"]
	bank_account = _ensure_company_bank_account()

	existing = frappe.db.get_value(
		"Payroll Payment Batch",
		{"payroll_entry": payroll_entry, "docstatus": ["<", 2]},
		"name",
	)
	if existing:
		batch = frappe.get_doc("Payroll Payment Batch", existing)
	else:
		batch = frappe.get_doc(
			{
				"doctype": "Payroll Payment Batch",
				"payroll_entry": payroll_entry,
				"company": E2E_COMPANY,
				"payment_date": today(),
				"bank_account": bank_account,
				"bank_format": "FNB OBE CSV",
			}
		)
		batch.insert(ignore_permissions=True)
	if batch.docstatus == 0:
		batch.submit()

	from za_local_payroll.utils.integrations.eft_file_generator import generate_eft_file

	result = generate_eft_file(payment_batch=batch.name)
	batch.reload()
	file_doc = frappe.db.get_value(
		"File",
		{
			"file_url": batch.eft_file_path,
			"attached_to_doctype": "Payroll Payment Batch",
			"attached_to_name": batch.name,
		},
		["name", "file_name", "file_url", "is_private"],
		as_dict=True,
	)
	frappe.db.commit()
	return {
		"payment_batch": batch.name,
		"docstatus": batch.docstatus,
		"employees": batch.total_employees,
		"amount": batch.total_amount,
		"source_hash": batch.eft_source_hash,
		"fnb_hash_total": batch.fnb_hash_total,
		"file": file_doc,
		"reused": result["reused"],
	}


def stage_timesheet_payroll():
	"""Submit an hourly timesheet and its mapped Salary Slip."""
	_require_isolated_test_site()
	employee = stage_payroll_masters()["employees"]["timesheet"]
	activity_type = "ZA Local E2E Payroll Work"
	if not frappe.db.exists("Activity Type", activity_type):
		frappe.get_doc(
			{
				"doctype": "Activity Type",
				"activity_type": activity_type,
				"costing_rate": 0,
				"billing_rate": 0,
			}
		).insert(ignore_permissions=True)

	timesheet_name = frappe.db.get_value(
		"Timesheet",
		{
			"employee": employee,
			"start_date": "2026-09-15",
			"end_date": "2026-09-15",
			"docstatus": ["<", 2],
		},
		"name",
	)
	if timesheet_name:
		timesheet = frappe.get_doc("Timesheet", timesheet_name)
	else:
		timesheet = frappe.get_doc(
			{
				"doctype": "Timesheet",
				"employee": employee,
				"company": E2E_COMPANY,
				"time_logs": [
					{
						"activity_type": activity_type,
						"from_time": "2026-09-15 08:00:00",
						"to_time": "2026-09-15 16:00:00",
						"hours": 8,
					}
				],
			}
		)
		timesheet.insert(ignore_permissions=True)
		timesheet.submit()

	slip_name = frappe.db.get_value(
		"Salary Slip",
		{
			"employee": employee,
			"start_date": "2026-09-15",
			"end_date": "2026-09-15",
			"salary_slip_based_on_timesheet": 1,
			"docstatus": ["<", 2],
		},
		"name",
	)
	if slip_name:
		slip = frappe.get_doc("Salary Slip", slip_name)
	else:
		from hrms.payroll.doctype.salary_slip.salary_slip import make_salary_slip_from_timesheet

		slip = make_salary_slip_from_timesheet(timesheet.name)
		slip.insert(ignore_permissions=True)
		slip.submit()
	frappe.db.commit()
	return {
		"timesheet": timesheet.name,
		"salary_slip": slip.name,
		"hours": slip.total_working_hours,
		"hour_rate": slip.hour_rate,
		"gross_pay": slip.gross_pay,
		"docstatus": slip.docstatus,
	}


def stage_workplace_injury_cycle():
	"""Submit an injury and complete its linked OID claim workflow."""
	_require_isolated_test_site()
	employee = stage_payroll_masters()["employees"]["regular"]
	injury_name = frappe.db.get_value(
		"Workplace Injury",
		{
			"employee": employee,
			"injury_date": "2026-07-15",
			"docstatus": ["<", 2],
		},
		"name",
	)
	if injury_name:
		injury = frappe.get_doc("Workplace Injury", injury_name)
	else:
		injury = frappe.get_doc(
			{
				"doctype": "Workplace Injury",
				"employee": employee,
				"injury_date": "2026-07-15",
				"injury_time": "10:30:00",
				"injury_location": "E2E office",
				"injury_type": "Moderate",
				"severity": "Medium",
				"injury_description": "Deterministic isolated-site workplace injury scenario.",
				"incident_mechanism": "Slip on a controlled office walkway during normal duties.",
				"body_part_affected": "Right ankle",
				"investigation_summary": "Area inspected; no continuing hazard identified in the isolated E2E scenario.",
				"medical_attention_required": 1,
				"medical_provider": "E2E Occupational Health",
				"expected_recovery_date": "2026-07-18",
				"requires_claim": 1,
			}
		)
		injury.insert(ignore_permissions=True)
	if injury.docstatus == 0:
		injury.submit()
	injury.reload()
	if not injury.oid_claim:
		injury.create_oid_claim_after_submit()
		injury.reload()

	claim = frappe.get_doc("OID Claim", injury.oid_claim)
	if claim.docstatus == 0:
		claim.submit()
		claim.reload()
	if not claim.medical_reports:
		claim.add_medical_report(
			"2026-07-16",
			"E2E Occupational Health",
			"Initial Assessment",
			"E2E soft-tissue injury",
		)
		claim.reload()
	if claim.claim_status == "Submitted":
		claim.update_claim_status("Under Review")
		claim.reload()
	if claim.claim_status == "Under Review":
		claim.update_claim_status("Approved", compensation_amount=1250)
		claim.reload()
	if claim.claim_status == "Approved":
		payment_date = max(getdate("2026-08-01"), getdate(claim.claim_date or claim.injury_date))
		claim.update_claim_status("Paid", payment_date=payment_date)
		claim.reload()
	injury.reload()
	frappe.db.commit()
	return {
		"workplace_injury": injury.name,
		"injury_docstatus": injury.docstatus,
		"injury_status": injury.status,
		"oid_claim": claim.name,
		"claim_docstatus": claim.docstatus,
		"claim_status": claim.claim_status,
		"compensation_amount": claim.compensation_amount,
		"payment_date": claim.payment_date,
		"medical_reports": len(claim.medical_reports),
	}


def collect_signoff_evidence():
	"""Return deterministic control totals for migration and restore comparisons."""
	_require_isolated_test_site()
	slips = frappe.get_all(
		"Salary Slip",
		filters={"company": E2E_COMPANY, "docstatus": 1},
		fields=["gross_pay", "total_deduction", "net_pay", "za_monthly_eti"],
	)
	emp201_rows = frappe.get_all(
		"EMP201 Submission",
		filters={"company": E2E_COMPANY, "docstatus": 1},
		fields=["net_paye_payable", "uif_payable", "sdl_payable", "eti_utilized_current_month"],
	)
	vat_rows = frappe.get_all(
		"VAT201 Return",
		filters={"company": E2E_COMPANY, "docstatus": 1},
		fields=["total_output_tax", "total_input_tax", "vat_payable"],
	)
	coida_rows = frappe.get_all(
		"COIDA Annual Return",
		filters={"company": E2E_COMPANY, "docstatus": 1},
		fields=["total_annual_earnings", "assessment_fee"],
	)
	payment_rows = frappe.get_all(
		"Payroll Payment Batch",
		filters={"company": E2E_COMPANY, "docstatus": 1},
		fields=["total_amount"],
	)

	def total(rows, fieldname):
		return flt(sum(flt(row.get(fieldname)) for row in rows), 2)

	return {
		"installed_apps": frappe.get_installed_apps(),
		"site": {
			"setup_complete": int(frappe.is_setup_complete()),
			"company": E2E_COMPANY,
		},
		"salary_slips": {
			"count": len(slips),
			"gross_pay": total(slips, "gross_pay"),
			"total_deduction": total(slips, "total_deduction"),
			"net_pay": total(slips, "net_pay"),
			"eti": total(slips, "za_monthly_eti"),
		},
		"emp201": {
			"count": len(emp201_rows),
			"paye": total(emp201_rows, "net_paye_payable"),
			"uif": total(emp201_rows, "uif_payable"),
			"sdl": total(emp201_rows, "sdl_payable"),
			"eti_utilised": total(emp201_rows, "eti_utilized_current_month"),
		},
		"statutory_documents": {
			"emp501": frappe.db.count("EMP501 Reconciliation", {"company": E2E_COMPANY, "docstatus": 1}),
			"irp5": frappe.db.count("IRP5 Certificate", {"company": E2E_COMPANY, "docstatus": 1}),
		},
		"vat201": {
			"count": len(vat_rows),
			"output_tax": total(vat_rows, "total_output_tax"),
			"input_tax": total(vat_rows, "total_input_tax"),
			"vat_payable": total(vat_rows, "vat_payable"),
			"submitted_filings": frappe.db.count("ZA Filing", {"company": E2E_COMPANY, "docstatus": 1}),
			"accepted_receipts": frappe.db.count(
				"ZA Submission Receipt",
				{"docstatus": 1, "response_status": "Accepted"},
			),
		},
		"coida": {
			"count": len(coida_rows),
			"assessable_earnings": total(coida_rows, "total_annual_earnings"),
			"assessment_fee": total(coida_rows, "assessment_fee"),
		},
		"payments": {
			"count": len(payment_rows),
			"total_amount": total(payment_rows, "total_amount"),
		},
		"workplace": {
			"submitted_injuries": frappe.db.count(
				"Workplace Injury", {"company": E2E_COMPANY, "docstatus": 1}
			),
			"submitted_claims": frappe.db.count("OID Claim", {"company": E2E_COMPANY, "docstatus": 1}),
		},
	}


def validate_signoff_invariants():
	"""Fail when staged statutory results disagree with independently versioned controls."""
	_require_isolated_test_site()
	controls = json.loads(
		Path(frappe.get_app_path("za_local_core", "tests", "golden", "2026_27_e2e.json")).read_text()
	)
	tolerance = flt(controls["tolerance"])
	errors = []

	def compare(label, actual, expected):
		actual = flt(actual, 2)
		expected = flt(expected, 2)
		if abs(actual - expected) > tolerance:
			errors.append(f"{label}: expected {expected:.2f}, got {actual:.2f}")

	slips = frappe.get_all(
		"Salary Slip",
		filters={"company": E2E_COMPANY, "docstatus": 1},
		fields=["name", "gross_pay", "start_date", "end_date", "payroll_entry"],
		order_by="end_date, name",
	)
	if not slips:
		errors.append("No submitted Salary Slips exist for statutory invariant checks")

	for slip in slips:
		uif_basis = flt(slip.gross_pay)
		expected_employee_uif = min(uif_basis, flt(controls["uif"]["monthly_remuneration_cap"])) * flt(
			controls["uif"]["employee_rate"]
		)
		expected_employer_uif = min(uif_basis, flt(controls["uif"]["monthly_remuneration_cap"])) * flt(
			controls["uif"]["employer_rate"]
		)
		expected_sdl = uif_basis * flt(controls["sdl"]["rate"])
		compare(
			f"{slip.name} employee UIF",
			_component_total(slip.name, "deductions", "UIF Employee Contribution"),
			expected_employee_uif,
		)
		compare(
			f"{slip.name} employer UIF",
			_component_total(slip.name, "company_contribution", "UIF Employer Contribution"),
			expected_employer_uif,
		)
		compare(
			f"{slip.name} SDL",
			_component_total(slip.name, "company_contribution", "SDL Contribution"),
			expected_sdl,
		)

	for declaration in frappe.get_all(
		"EMP201 Submission",
		filters={"company": E2E_COMPANY, "docstatus": 1},
		fields=["name", "submission_period_start_date", "submission_period_end_date", "uif_payable"],
		order_by="submission_period_start_date",
	):
		period_slips = frappe.get_all(
			"Salary Slip",
			filters={
				"company": E2E_COMPANY,
				"docstatus": 1,
				"end_date": [
					"between",
					[declaration.submission_period_start_date, declaration.submission_period_end_date],
				],
			},
			pluck="name",
		)
		expected_uif = sum(
			_component_total(name, "deductions", "UIF Employee Contribution")
			+ _component_total(name, "company_contribution", "UIF Employer Contribution")
			for name in period_slips
		)
		compare(f"{declaration.name} total UIF", declaration.uif_payable, expected_uif)

	evidence = collect_signoff_evidence()
	for fieldname, expected in {
		"output_tax": controls["vat"]["expected_output_tax"],
		"input_tax": controls["vat"]["expected_input_tax"],
		"vat_payable": controls["vat"]["expected_payable"],
	}.items():
		compare(f"VAT201 {fieldname}", evidence["vat201"][fieldname], expected)
	compare(
		"COIDA assessable earnings",
		evidence["coida"]["assessable_earnings"],
		controls["coida"]["expected_assessable_earnings"],
	)
	compare(
		"COIDA assessment fee",
		evidence["coida"]["assessment_fee"],
		controls["coida"]["expected_assessment_fee"],
	)
	if evidence["vat201"]["submitted_filings"] != 1:
		errors.append("Expected exactly one submitted ZA Filing for the staged VAT201 cycle")
	if evidence["vat201"]["accepted_receipts"] != 1:
		errors.append("Expected exactly one accepted submission receipt for the staged VAT201 cycle")

	_validate_company_contribution_journals(slips, errors, tolerance)
	_validate_payment_batches(errors, tolerance)

	if errors:
		frappe.throw(
			_("Statutory E2E invariant checks failed:<br>{0}").format(
				"<br>".join(frappe.utils.escape_html(error) for error in errors)
			),
			title=_("Production Sign-off Blocked"),
		)
	return {
		"status": "passed",
		"tax_year": controls["tax_year"],
		"verified_on": controls["verified_on"],
		"salary_slips_checked": len(slips),
		"sources": controls["sources"],
	}


def _component_total(parent, parentfield, component):
	doctype = "Salary Detail" if parentfield in {"earnings", "deductions"} else "Company Contribution"
	return flt(
		sum(
			flt(row.amount)
			for row in frappe.get_all(
				doctype,
				filters={
					"parent": parent,
					"parentfield": parentfield,
					"salary_component": component,
				},
				fields=["amount"],
			)
		),
		2,
	)


def _validate_company_contribution_journals(slips, errors, tolerance):
	payroll_entries = sorted({slip.payroll_entry for slip in slips if slip.payroll_entry})
	for payroll_entry in payroll_entries:
		expected = flt(
			sum(
				_component_total(slip.name, "company_contribution", "UIF Employer Contribution")
				+ _component_total(slip.name, "company_contribution", "SDL Contribution")
				for slip in slips
				if slip.payroll_entry == payroll_entry
			),
			2,
		)
		if not expected:
			continue
		journal_entries = frappe.get_all(
			"Journal Entry",
			filters={
				"docstatus": 1,
				"user_remark": ["like", "Company Contribution%"],
			},
			pluck="name",
		)
		matching = []
		for journal_entry in journal_entries:
			if frappe.db.exists(
				"Journal Entry Account",
				{
					"parent": journal_entry,
					"reference_type": "Payroll Entry",
					"reference_name": payroll_entry,
				},
			):
				matching.append(journal_entry)
		if len(matching) != 1:
			errors.append(
				f"{payroll_entry} requires exactly one submitted company-contribution journal; found {len(matching)}"
			)
			continue
		actual = flt(
			sum(
				flt(row.debit_in_account_currency)
				for row in frappe.get_all(
					"Journal Entry Account",
					filters={"parent": matching[0]},
					fields=["debit_in_account_currency"],
				)
			),
			2,
		)
		if abs(actual - expected) > tolerance:
			errors.append(
				f"{payroll_entry} employer-contribution journal: expected {expected:.2f}, got {actual:.2f}"
			)


def _validate_payment_batches(errors, tolerance):
	for batch in frappe.get_all(
		"Payroll Payment Batch",
		filters={"company": E2E_COMPANY, "docstatus": 1},
		fields=["name", "payroll_entry", "total_amount"],
	):
		expected = flt(
			sum(
				flt(row.net_pay)
				for row in frappe.get_all(
					"Salary Slip",
					filters={"payroll_entry": batch.payroll_entry, "docstatus": 1},
					fields=["net_pay"],
				)
			),
			2,
		)
		if abs(flt(batch.total_amount, 2) - expected) > tolerance:
			errors.append(
				f"{batch.name} payment total: expected submitted-slip net {expected:.2f}, got {flt(batch.total_amount, 2):.2f}"
			)


def render_signoff_pdfs(output_dir="/tmp/za-local-signoff-pdfs"):
	"""Render representative statutory PDFs for visual release-gate inspection."""
	_require_isolated_test_site()
	from frappe.utils.print_utils import get_print

	output_path = Path(output_dir).resolve()
	if not output_path.is_relative_to(Path("/tmp")):
		frappe.throw(_("Sign-off PDFs may only be written below /tmp."))
	output_path.mkdir(parents=True, exist_ok=True)

	renders = (
		("Salary Slip", "SA Salary Slip", "salary_slip.pdf"),
		("IRP5 Certificate", "IRP5 Employee Certificate", "irp5_certificate.pdf"),
		("Sales Invoice", "SA Sales Invoice", "sales_invoice.pdf"),
		("VAT201 Return", "SA VAT201 Return", "vat201_return.pdf"),
		("COIDA Annual Return", "SA COIDA Annual Return", "coida_annual_return.pdf"),
	)
	result = []
	for doctype, print_format, filename in renders:
		name = frappe.db.get_value(
			doctype,
			{"company": E2E_COMPANY, "docstatus": 1},
			"name",
			order_by="name asc",
		)
		if not name:
			frappe.throw(_("No submitted {0} exists for PDF sign-off.").format(doctype))
		pdf = get_print(doctype, name, print_format=print_format, as_pdf=True)
		if not pdf.startswith(b"%PDF"):
			frappe.throw(_("{0} did not render as a PDF.").format(print_format))
		file_path = output_path / filename
		file_path.write_bytes(pdf)
		result.append(
			{
				"doctype": doctype,
				"name": name,
				"print_format": print_format,
				"path": str(file_path),
				"bytes": len(pdf),
			}
		)

	return result


def run_permission_smoke():
	"""Verify representative sensitive records reject an unauthorised session."""
	_require_isolated_test_site()
	from za_local_payroll.utils.emp501_utils import generate_emp501_csv

	from za_local_core.sa_vat.tax_invoice import check_tax_invoice_readiness

	sales_invoice = frappe.db.get_value("Sales Invoice", {"company": E2E_COMPANY, "docstatus": 1}, "name")
	emp501 = frappe.db.get_value("EMP501 Reconciliation", {"company": E2E_COMPANY, "docstatus": 1}, "name")
	injury = frappe.db.get_value("Workplace Injury", {"company": E2E_COMPANY, "docstatus": 1}, "name")
	if not all((sales_invoice, emp501, injury)):
		frappe.throw(_("Stage the complete E2E scenario before running permission smoke tests."))

	checks = (
		("sales_invoice_readiness", lambda: check_tax_invoice_readiness(sales_invoice)),
		("emp501_export", lambda: generate_emp501_csv(emp501)),
		(
			"workplace_injury_health_data",
			lambda: frappe.get_doc("Workplace Injury", injury).check_permission("read"),
		),
	)
	original_user = frappe.session.user
	denied = []
	failures = []
	try:
		frappe.set_user("Guest")
		for label, check in checks:
			try:
				check()
			except frappe.PermissionError:
				denied.append(label)
			except Exception as exc:
				failures.append({"check": label, "error": type(exc).__name__})
			else:
				failures.append({"check": label, "error": "access_was_allowed"})
	finally:
		frappe.set_user(original_user)

	if failures:
		frappe.throw(_("Permission smoke tests failed: {0}").format(frappe.as_json(failures)))
	return {"user": "Guest", "denied": denied}


def _ensure_emp201(month):
	existing = frappe.db.get_value(
		"EMP201 Submission",
		{
			"company": E2E_COMPANY,
			"fiscal_year": "2026-2027",
			"month": month,
			"docstatus": ["<", 2],
		},
		"name",
	)
	if existing:
		doc = frappe.get_doc("EMP201 Submission", existing)
	else:
		doc = frappe.get_doc(
			{
				"doctype": "EMP201 Submission",
				"company": E2E_COMPANY,
				"fiscal_year": "2026-2027",
				"month": month,
				"posting_date": "2026-09-30",
			}
		)
		doc.insert(ignore_permissions=True)

	if doc.docstatus == 0:
		values = doc.fetch_emp201_data()
		if not values:
			frappe.throw(_("No payroll data was available for the {0} EMP201.").format(month))
		doc.update(values)
		doc.save(ignore_permissions=True)
		doc.submit()
	frappe.db.commit()
	return doc.name


def _ensure_payroll_additional_salaries(employees):
	_ensure_test_salary_component(E2E_RECURRING_COMPONENT, "E2ERA", "3702")
	_ensure_test_salary_component(E2E_BONUS_COMPONENT, "E2EB", "3605", annual_bonus=True)
	_ensure_additional_salary(
		employees["regular"],
		E2E_RECURRING_COMPONENT,
		1500,
		is_recurring=True,
	)
	_ensure_additional_salary(
		employees["regular"],
		"Basic",
		35000,
		payroll_date="2026-09-30",
		overwrite=True,
	)
	_ensure_additional_salary(
		employees["regular"],
		E2E_BONUS_COMPONENT,
		10000,
		payroll_date="2026-09-30",
		full_tax=True,
	)


def _stage_payroll_month(year, month):
	last_day = monthrange(year, month)[1]
	start_date = f"{year:04d}-{month:02d}-01"
	end_date = f"{year:04d}-{month:02d}-{last_day:02d}"

	existing = frappe.db.get_value(
		"Payroll Entry",
		{
			"company": E2E_COMPANY,
			"start_date": start_date,
			"end_date": end_date,
			"department": E2E_MONTHLY_DEPARTMENT,
			"docstatus": ["<", 2],
		},
		"name",
	)
	if existing:
		doc = frappe.get_doc("Payroll Entry", existing)
		if doc.docstatus == 0:
			doc.submit()
			doc.reload()
		if doc.docstatus == 1:
			slip_count = frappe.db.count("Salary Slip", {"payroll_entry": doc.name, "docstatus": ["<", 2]})
			if not slip_count:
				doc.create_salary_slips()
				doc.reload()
			draft_slips = frappe.db.count("Salary Slip", {"payroll_entry": doc.name, "docstatus": 0})
			if draft_slips:
				doc.submit_salary_slips()
		frappe.db.commit()
		return _payroll_summary(existing)

	doc = frappe.new_doc("Payroll Entry")
	doc.company = E2E_COMPANY
	doc.posting_date = end_date
	doc.start_date = start_date
	doc.end_date = end_date
	doc.payroll_frequency = "Monthly"
	doc.department = E2E_MONTHLY_DEPARTMENT
	doc.payroll_payable_account = E2E_PAYROLL_PAYABLE
	doc.payment_account = f"E2E Bank - {E2E_COMPANY_ABBR}"
	doc.currency = "ZAR"
	doc.exchange_rate = 1
	doc.cost_center = frappe.db.get_value(
		"Cost Center", {"company": E2E_COMPANY, "is_group": 0}, "name", order_by="lft asc"
	)
	doc.fill_employee_details()
	doc.insert(ignore_permissions=True)
	# Match the normal Desk workflow, where a draft Payroll Entry is committed
	# before the user submits it in a later request. HRMS deliberately rolls back
	# salary-slip creation failures, which would otherwise also remove this draft.
	frappe.db.commit()
	doc.submit()
	doc.submit_salary_slips()
	frappe.db.commit()
	return _payroll_summary(doc.name)


def _payroll_summary(payroll_entry):
	return {
		"payroll_entry": payroll_entry,
		"salary_slips": frappe.get_all(
			"Salary Slip",
			filters={"payroll_entry": payroll_entry},
			fields=["name", "employee", "gross_pay", "total_deduction", "net_pay", "docstatus"],
			order_by="employee asc",
		),
	}


def _ensure_test_salary_component(name, abbreviation, sars_code, annual_bonus=False):
	if frappe.db.exists("Salary Component", name):
		return name
	doc = frappe.get_doc(
		{
			"doctype": "Salary Component",
			"salary_component": name,
			"salary_component_abbr": abbreviation,
			"type": "Earning",
			"is_tax_applicable": 1,
			"depends_on_payment_days": 0,
			"za_sars_payroll_code": sars_code,
			"za_payroll_treatment": "Regular Remuneration",
			"za_paye_inclusion_percentage": 100,
			"za_uif_applicable": 1,
			"za_sdl_applicable": 1,
			"za_coida_applicable": 1,
			"za_is_annual_bonus": int(annual_bonus),
		}
	)
	salary_expense_account = frappe.db.get_value(
		"Account",
		{
			"company": E2E_COMPANY,
			"root_type": "Expense",
			"is_group": 0,
			"account_name": ["in", ["Salary", "Salaries and Wages"]],
		},
		"name",
	)
	if not salary_expense_account:
		frappe.throw(_("The E2E company requires a leaf Salary expense account."))
	doc.append(
		"accounts",
		{"company": E2E_COMPANY, "account": salary_expense_account},
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_additional_salary(
	employee,
	component,
	amount,
	*,
	is_recurring=False,
	payroll_date=None,
	overwrite=False,
	full_tax=False,
):
	filters = {
		"employee": employee,
		"salary_component": component,
		"amount": amount,
		"docstatus": 1,
	}
	if is_recurring:
		filters["is_recurring"] = 1
	else:
		filters["payroll_date"] = payroll_date
	existing = frappe.db.get_value("Additional Salary", filters, "name")
	if existing:
		return existing

	doc = frappe.get_doc(
		{
			"doctype": "Additional Salary",
			"employee": employee,
			"company": E2E_COMPANY,
			"salary_component": component,
			"amount": amount,
			"is_recurring": int(is_recurring),
			"from_date": "2026-03-01" if is_recurring else None,
			"to_date": "2027-02-28" if is_recurring else None,
			"payroll_date": payroll_date,
			"overwrite_salary_structure_amount": int(overwrite),
			"deduct_full_tax_on_selected_payroll_date": int(full_tax),
		}
	)
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name


def _ensure_working_calendar():
	if frappe.db.exists("Holiday List", E2E_HOLIDAY_LIST):
		return E2E_HOLIDAY_LIST

	doc = frappe.new_doc("Holiday List")
	doc.holiday_list_name = E2E_HOLIDAY_LIST
	doc.from_date = "2026-03-01"
	doc.to_date = "2027-02-28"
	doc.weekly_off = "Sunday"
	for reference_name in ("South Africa 2026", "South Africa 2027"):
		for row in frappe.get_doc("Holiday List", reference_name).holidays:
			if getdate(doc.from_date) <= getdate(row.holiday_date) <= getdate(doc.to_date):
				doc.append(
					"holidays",
					{
						"holiday_date": row.holiday_date,
						"description": row.description,
						"weekly_off": 0,
					},
				)
	doc.get_weekly_off_dates()
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_holiday_list_assignment(holiday_list):
	existing = frappe.db.get_value(
		"Holiday List Assignment",
		{
			"assigned_to": E2E_COMPANY,
			"from_date": "2026-03-01",
			"docstatus": 1,
		},
		"name",
	)
	if existing:
		return existing

	doc = frappe.get_doc(
		{
			"doctype": "Holiday List Assignment",
			"applicable_for": "Company",
			"assigned_to": E2E_COMPANY,
			"holiday_list": holiday_list,
			"from_date": "2026-03-01",
		}
	)
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name


def _ensure_employee(label, date_of_birth, email, gender_sequence, department):
	existing = frappe.db.get_value("Employee", {"personal_email": email}, "name")
	if existing:
		frappe.db.set_value("Employee", existing, "department", department)
		employee = existing
	else:
		doc = frappe.get_doc(
			{
				"doctype": "Employee",
				"first_name": "E2E",
				"last_name": label,
				"gender": "Male",
				"date_of_birth": date_of_birth,
				"date_of_joining": "2026-03-01",
				"company": E2E_COMPANY,
				"department": department,
				"status": "Active",
				"personal_email": email,
				"holiday_list": E2E_HOLIDAY_LIST,
				"za_employee_type": E2E_EMPLOYEE_TYPE,
				"za_id_number": _make_sa_id(date_of_birth, gender_sequence),
				"za_income_tax_reference_number": f"9{gender_sequence:09d}"[-10:],
				"za_hours_per_month": 160,
			}
		)
		doc.insert(ignore_permissions=True)
		employee = doc.name

	address = _ensure_address(f"ZA Local E2E {label} Residential", "Employee", employee)
	bank_account = _ensure_employee_bank_account(employee, label, gender_sequence)
	frappe.db.set_value(
		"Employee",
		employee,
		{
			"bank_name": "ZA Local E2E Test Bank",
			"bank_ac_no": f"62{gender_sequence:09d}"[-11:],
			"za_residential_address": address,
			"za_postal_address": address,
			"za_payroll_payable_bank_account": bank_account,
			"za_bank_account_type": "Current",
			"za_bank_account_holder_name": f"E2E {label}",
			"za_bank_account_holder_relationship": "Employee",
			"za_not_paid_electronically": 0,
			"za_eti_minimum_wage_basis": "No Regulating Measure or NMW Exempt",
		},
	)
	return employee


def _ensure_address(title, link_doctype, link_name):
	existing = frappe.db.get_value("Address", {"address_title": title}, "name")
	if existing:
		return existing

	doc = frappe.get_doc(
		{
			"doctype": "Address",
			"address_title": title,
			"address_type": "Billing",
			"address_line1": "1 Test Street",
			"city": "Johannesburg",
			"state": "Gauteng",
			"country": "South Africa",
			"pincode": "2001",
			"links": [{"link_doctype": link_doctype, "link_name": link_name}],
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_employee_bank_account(employee, label, sequence):
	bank_name = "ZA Local E2E Test Bank"
	if not frappe.db.exists("Bank", bank_name):
		frappe.get_doc({"doctype": "Bank", "bank_name": bank_name}).insert(ignore_permissions=True)
	if not frappe.db.exists("Bank Account Type", "Current"):
		frappe.get_doc({"doctype": "Bank Account Type", "account_type": "Current"}).insert(
			ignore_permissions=True
		)

	account_name = f"E2E {label} Payroll"
	existing = frappe.db.get_value(
		"Bank Account",
		{"account_name": account_name, "bank": bank_name},
		"name",
	)
	if existing:
		return existing

	doc = frappe.get_doc(
		{
			"doctype": "Bank Account",
			"account_name": account_name,
			"bank": bank_name,
			"account_type": "Current",
			"party_type": "Employee",
			"party": employee,
			"bank_account_no": f"62{sequence:09d}"[-11:],
			"branch_code": "250655",
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_company_bank_account():
	bank_name = "ZA Local E2E Test Bank"
	if not frappe.db.exists("Bank", bank_name):
		frappe.get_doc({"doctype": "Bank", "bank_name": bank_name}).insert(ignore_permissions=True)
	if not frappe.db.exists("Bank Account Type", "Current"):
		frappe.get_doc({"doctype": "Bank Account Type", "account_type": "Current"}).insert(
			ignore_permissions=True
		)

	gl_account = f"E2E Bank - {E2E_COMPANY_ABBR}"
	existing = frappe.db.get_value("Bank Account", {"account": gl_account}, "name")
	if existing:
		return existing

	doc = frappe.get_doc(
		{
			"doctype": "Bank Account",
			"account_name": "ZA Local E2E Company Payroll",
			"bank": bank_name,
			"account_type": "Current",
			"is_company_account": 1,
			"company": E2E_COMPANY,
			"account": gl_account,
			"bank_account_no": "62000031451",
			"branch_code": "250655",
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _make_sa_id(date_of_birth, gender_sequence):
	dob = getdate(date_of_birth)
	prefix = f"{dob:%y%m%d}{gender_sequence:04d}08"
	total = 0
	for index, digit in enumerate(prefix):
		number = int(digit)
		if index % 2:
			number *= 2
			number = number if number <= 9 else number - 9
		total += number
	return f"{prefix}{(10 - total % 10) % 10}"


def _ensure_salary_structure(name, timesheet_based=False):
	if frappe.db.exists("Salary Structure", name):
		return name

	doc = frappe.get_doc(
		{
			"doctype": "Salary Structure",
			"name": name,
			"company": E2E_COMPANY,
			"currency": "ZAR",
			"payroll_frequency": "Monthly",
			"payment_account": E2E_PAYROLL_PAYABLE,
			"salary_slip_based_on_timesheet": int(timesheet_based),
			"salary_component": "Basic" if timesheet_based else None,
			"hour_rate": 500 if timesheet_based else 0,
		}
	)
	if not timesheet_based:
		doc.append(
			"earnings",
			{
				"salary_component": "Basic",
				"amount_based_on_formula": 1,
				"formula": "base",
			},
		)
	for component in ("PAYE", "UIF Employee Contribution"):
		doc.append("deductions", {"salary_component": component})
	for component in ("UIF Employer Contribution", "SDL Contribution"):
		doc.append("company_contribution", {"salary_component": component})
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name


def _ensure_salary_structure_assignment(employee, salary_structure, base):
	existing = frappe.db.get_value(
		"Salary Structure Assignment",
		{"employee": employee, "salary_structure": salary_structure, "docstatus": 1},
		"name",
	)
	if existing:
		return existing

	income_tax_slab = frappe.db.get_value(
		"Income Tax Slab",
		{"company": E2E_COMPANY, "effective_from": ["<=", "2026-03-01"], "docstatus": 1},
		"name",
		order_by="effective_from desc",
	)
	doc = frappe.get_doc(
		{
			"doctype": "Salary Structure Assignment",
			"employee": employee,
			"salary_structure": salary_structure,
			"from_date": "2026-03-01",
			"company": E2E_COMPANY,
			"base": base,
			"income_tax_slab": income_tax_slab,
			"payroll_payable_account": E2E_PAYROLL_PAYABLE,
		}
	)
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name


def _get_e2e_account(account_name):
	account = frappe.db.get_value(
		"Account",
		{"company": E2E_COMPANY, "account_name": account_name, "is_group": 0},
		"name",
	)
	if not account:
		frappe.throw(_("E2E account {0} is not configured.").format(account_name))
	return account


def _ensure_vat_customer():
	if frappe.db.exists("Customer", E2E_VAT_CUSTOMER):
		return E2E_VAT_CUSTOMER

	customer_group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name", order_by="name asc")
	territory = frappe.db.get_value("Territory", {"is_group": 0}, "name", order_by="name asc")
	frappe.get_doc(
		{
			"doctype": "Customer",
			"customer_name": E2E_VAT_CUSTOMER,
			"customer_type": "Company",
			"customer_group": customer_group,
			"territory": territory,
			"tax_id": "4987654321",
			"za_is_vat_vendor": 1,
		}
	).insert(ignore_permissions=True)
	_ensure_address("ZA Local E2E Customer Address", "Customer", E2E_VAT_CUSTOMER)
	return E2E_VAT_CUSTOMER


def _ensure_vat_supplier():
	if frappe.db.exists("Supplier", E2E_VAT_SUPPLIER):
		return E2E_VAT_SUPPLIER

	supplier_group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name", order_by="name asc")
	frappe.get_doc(
		{
			"doctype": "Supplier",
			"supplier_name": E2E_VAT_SUPPLIER,
			"supplier_group": supplier_group,
			"supplier_type": "Company",
			"country": "South Africa",
			"tax_id": "4876543210",
		}
	).insert(ignore_permissions=True)
	_ensure_address("ZA Local E2E Supplier Address", "Supplier", E2E_VAT_SUPPLIER)
	return E2E_VAT_SUPPLIER


def _ensure_vat_item():
	if frappe.db.exists("Item", E2E_VAT_ITEM):
		return E2E_VAT_ITEM

	frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": E2E_VAT_ITEM,
			"item_name": "ZA Local E2E Professional Service",
			"item_group": "Services",
			"stock_uom": "Unit",
			"is_stock_item": 0,
			"custom_sa_vat_category": "Standard Rated",
		}
	).insert(ignore_permissions=True)
	return E2E_VAT_ITEM


def _ensure_vat_invoice(doctype, party, tax_template, amount):
	party_field = "customer" if doctype == "Sales Invoice" else "supplier"
	existing = frappe.db.get_value(
		doctype,
		{
			"company": E2E_COMPANY,
			party_field: party,
			"posting_date": "2026-07-15",
			"docstatus": 1,
		},
		"name",
	)
	if existing:
		return existing

	company = frappe.db.get_value(
		"Company",
		E2E_COMPANY,
		["default_income_account", "default_expense_account", "cost_center"],
		as_dict=True,
	)
	values = {
		"doctype": doctype,
		"company": E2E_COMPANY,
		party_field: party,
		"posting_date": "2026-07-15",
		"set_posting_time": 1,
		"taxes_and_charges": tax_template,
		"items": [
			{
				"item_code": E2E_VAT_ITEM,
				"qty": 1,
				"rate": amount,
				"cost_center": company.cost_center,
			}
		],
	}
	if doctype == "Sales Invoice":
		values["due_date"] = "2026-07-31"
		values["items"][0]["income_account"] = company.default_income_account
	else:
		values.update({"bill_no": "E2E-VAT-BILL-001", "bill_date": "2026-07-15", "due_date": "2026-07-31"})
		values["items"][0]["expense_account"] = company.default_expense_account

	doc = frappe.get_doc(values)
	doc.append_taxes_from_master()
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name


def _require_isolated_test_site():
	site = frappe.local.site or ""
	is_test_name = "e2e" in site.lower() or site.lower().endswith(".test")
	if not frappe.conf.developer_mode or not is_test_name:
		frappe.throw(
			_("E2E data may only be staged on a developer-mode .test or e2e site."),
			title=_("Isolated Test Site Required"),
		)


def _ensure_test_compliance_reviewer() -> str:
	email = "_e2e.za.compliance.reviewer@cohenix.test"
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "E2E ZA Compliance Reviewer",
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)
	if "ZA Compliance Reviewer" not in frappe.get_roles(email):
		frappe.get_doc("User", email).add_roles("ZA Compliance Reviewer")
	return email


def _ensure_test_compliance_approver() -> str:
	email = "_e2e.za.compliance.approver@cohenix.test"
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "E2E ZA Compliance Approver",
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)
	if "ZA Compliance Manager" not in frappe.get_roles(email):
		frappe.get_doc("User", email).add_roles("ZA Compliance Manager")
	return email


def _submit_as(doc, user: str) -> None:
	original_user = frappe.session.user
	try:
		frappe.set_user(user)
		doc.submit()
	finally:
		frappe.set_user(original_user)
