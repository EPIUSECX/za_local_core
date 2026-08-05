import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import patch

import frappe
from frappe.tests.classes import IntegrationTestCase, UnitTestCase
from frappe.utils.file_manager import save_file

from za_local_core.sa_vat.doctype.vat201_return.vat201_return import (
	CLASSIFIED,
	EXCLUDED,
	INPUT_OTHER_LOCAL,
	NEEDS_REVIEW,
	VAT201Return,
)
from za_local_core.sa_vat.filing import record_submission_receipt
from za_local_core.sa_vat.reconciliation import (
	calculate_live_ledger_sha256,
	distribute_amount,
	enrich_invoice_rows,
	finalize_row_snapshot,
	set_parent_reconciliation,
	verify_snapshots,
)
from za_local_core.sa_vat.setup import get_vat_settings
from za_local_core.sa_vat.statutory import (
	COMPULSORY_REGISTRATION_THRESHOLD,
	CURRENT_APPROVED_SOURCE_METADATA,
	FULL_INVOICE_THRESHOLD,
	NO_INVOICE_THRESHOLD,
	STANDARD_RATE,
	VAT_CONTROL_RULE_KEYS,
	VOLUNTARY_REGISTRATION_THRESHOLD,
	resolve_vat_controls,
)
from za_local_core.tests.e2e_setup import stage_approved_test_vat_governance
from za_local_core.tests.vat_fixtures import get_configured_vat_company

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


class TestVATReconciliation(UnitTestCase):
	def test_currency_distribution_preserves_total(self):
		self.assertEqual([3.33, 3.33, 3.34], distribute_amount(10, [1, 1, 1]))
		self.assertEqual(-10, sum(distribute_amount(-10, [1, 2, 3])))

	def test_fx_snapshot_reconciles_transaction_source_to_company_gl(self):
		invoice = frappe._dict(
			name="PINV-FX",
			posting_date="2026-06-30",
			is_return=0,
			base_net_total=200,
			currency="USD",
			conversion_rate=20,
			modified="2026-06-30 12:00:00",
		)
		taxes = [
			frappe._dict(
				name="TAX-FX",
				source_tax_amount=1.5,
				tax_amount=30,
				base_tax_amount=30,
			)
		]
		rows = [
			{
				"voucher_type": "Purchase Invoice",
				"voucher_no": invoice.name,
				"posting_date": invoice.posting_date,
				"tax_amount": 30,
				"gross_tax_amount": 30,
			}
		]
		gl_entries = [
			frappe._dict(name="GL-FX", account="Input VAT", debit=30, credit=0),
		]
		with patch(
			"za_local_core.sa_vat.reconciliation.get_invoice_gl_entries",
			return_value=gl_entries,
		):
			enrich_invoice_rows(rows, invoice, taxes, "Input VAT", "Purchase Invoice")

		self.assertEqual(1.5, rows[0]["source_tax_amount"])
		self.assertEqual(30, rows[0]["source_base_tax_amount"])
		self.assertEqual(30, rows[0]["gl_tax_amount"])
		self.assertEqual("Reconciled", rows[0]["reconciliation_status"])
		self.assertRegex(rows[0]["source_snapshot_sha256"], r"^[0-9a-f]{64}$")

	def test_snapshot_tampering_is_rejected(self):
		row = frappe._dict(
			voucher_type="Purchase Invoice",
			voucher_no="PINV-TAMPER",
			posting_date="2026-06-30",
			source_rows_json="[]",
			source_modified="2026-06-30 12:00:00",
			source_currency="ZAR",
			exchange_rate=1,
			source_tax_amount=15,
			source_base_tax_amount=15,
			tax_account="Input VAT",
			gl_entries_json="[]",
			gl_tax_amount=15,
			is_cancelled=0,
		)
		finalize_row_snapshot(row)
		doc = frappe._dict(
			company="Test Company",
			from_date="2026-06-01",
			to_date="2026-06-30",
			transactions=[row],
			snapshot_generated_on="2026-07-01 00:00:00",
		)
		set_parent_reconciliation(doc)
		row.gl_tax_amount = 14
		with self.assertRaises(frappe.ValidationError):
			verify_snapshots(doc)

	def test_blocked_and_apportioned_input_treatments_are_explicit(self):
		worker = SimpleNamespace(classify_purchase_item_category=lambda _category: INPUT_OTHER_LOCAL)
		blocked_rows = [
			{
				"classification": INPUT_OTHER_LOCAL,
				"classification_status": CLASSIFIED,
				"tax_amount": 15,
				"tax_account_debit": 15,
				"tax_account_credit": 0,
			}
		]
		blocked_item = frappe._dict(
			base_net_amount=100,
			custom_sa_vat_category="Standard Rated",
			za_vat_input_treatment="Blocked",
			za_vat_deduction_percentage=0,
			za_vat_treatment_evidence="ENTERTAINMENT-POLICY-1",
		)
		with patch("frappe.get_all", return_value=[blocked_item]):
			VAT201Return.apply_purchase_input_treatment(worker, SimpleNamespace(name="PINV-1"), blocked_rows)
		self.assertEqual(EXCLUDED, blocked_rows[0]["classification_status"])
		self.assertEqual(0, blocked_rows[0]["tax_amount"])
		self.assertEqual(15, blocked_rows[0]["non_deductible_tax_amount"])

		apportioned_rows = [
			{
				"classification": INPUT_OTHER_LOCAL,
				"classification_status": CLASSIFIED,
				"tax_amount": 15,
				"tax_account_debit": 15,
				"tax_account_credit": 0,
			}
		]
		apportioned_item = frappe._dict(
			base_net_amount=100,
			custom_sa_vat_category="Standard Rated",
			za_vat_input_treatment="Apportioned",
			za_vat_deduction_percentage=60,
			za_vat_treatment_evidence="APPROVED-METHOD-2026",
		)
		with patch("frappe.get_all", return_value=[apportioned_item]):
			VAT201Return.apply_purchase_input_treatment(
				worker, SimpleNamespace(name="PINV-2"), apportioned_rows
			)
		self.assertEqual(CLASSIFIED, apportioned_rows[0]["classification_status"])
		self.assertEqual(9, apportioned_rows[0]["tax_amount"])
		self.assertEqual(6, apportioned_rows[0]["non_deductible_tax_amount"])

	def test_imported_services_and_second_hand_goods_remain_controlled_manual(self):
		worker = SimpleNamespace(classify_purchase_item_category=lambda _category: INPUT_OTHER_LOCAL)
		for treatment in ("Imported Services", "Second-hand Goods"):
			with self.subTest(treatment=treatment):
				rows = [
					{
						"classification": INPUT_OTHER_LOCAL,
						"classification_status": CLASSIFIED,
						"tax_amount": 15,
					}
				]
				item = frappe._dict(
					base_net_amount=100,
					custom_sa_vat_category="Standard Rated",
					za_vat_input_treatment=treatment,
					za_vat_deduction_percentage=100,
					za_vat_treatment_evidence="PRACTITIONER-REF",
				)
				with patch("frappe.get_all", return_value=[item]):
					VAT201Return.apply_purchase_input_treatment(
						worker, SimpleNamespace(name="PINV-MANUAL"), rows
					)
				self.assertEqual(NEEDS_REVIEW, rows[0]["classification_status"])
				self.assertIn("practitioner-controlled", rows[0]["classification_issue"])


class TestVATStatutoryControls(UnitTestCase):
	def test_current_approved_source_metadata_matches_sars_controls(self):
		self.assertEqual("SARS", CURRENT_APPROVED_SOURCE_METADATA["authority"])
		self.assertEqual("2026-04-01", CURRENT_APPROVED_SOURCE_METADATA["effective_from"])
		self.assertEqual(
			{
				STANDARD_RATE: 15,
				COMPULSORY_REGISTRATION_THRESHOLD: 2_300_000,
				VOLUNTARY_REGISTRATION_THRESHOLD: 120_000,
				NO_INVOICE_THRESHOLD: 50,
				FULL_INVOICE_THRESHOLD: 5_000,
			},
			CURRENT_APPROVED_SOURCE_METADATA["expected_current_values"],
		)
		self.assertTrue(
			CURRENT_APPROVED_SOURCE_METADATA["registration_source_url"].startswith("https://www.sars.gov.za/")
		)
		self.assertTrue(
			CURRENT_APPROVED_SOURCE_METADATA["invoice_source_url"].startswith("https://www.sars.gov.za/")
		)

	def test_control_bundle_preserves_approved_source_and_pack_provenance(self):
		values = CURRENT_APPROVED_SOURCE_METADATA["expected_current_values"]
		resolved = {
			key: {
				"value": value,
				"rate_pack": "ZA-RATE-VAT-2026",
				"rate_pack_sha256": "a" * 64,
				"source": "ZA-SRC-SARS-VAT-2026",
				"source_sha256": "b" * 64,
				"effective_from": "2026-04-01",
				"effective_to": "2027-03-31",
			}
			for key, value in values.items()
		}
		with patch("za_local_core.sa_vat.statutory.resolve_rates", return_value=resolved):
			controls = resolve_vat_controls("2026-04-01")

		self.assertEqual(values, controls["values"])
		self.assertEqual("ZA-RATE-VAT-2026", controls["rate_pack"])
		self.assertEqual("ZA-SRC-SARS-VAT-2026", controls["source"])

	def test_control_bundle_rejects_mixed_approved_sources(self):
		resolved = {}
		for index, key in enumerate(VAT_CONTROL_RULE_KEYS):
			resolved[key] = {
				"value": CURRENT_APPROVED_SOURCE_METADATA["expected_current_values"][key],
				"rate_pack": "ZA-RATE-A" if index == 0 else "ZA-RATE-B",
				"rate_pack_sha256": "a" * 64,
				"source": "ZA-SRC-A" if index == 0 else "ZA-SRC-B",
				"source_sha256": "b" * 64,
				"effective_from": "2026-04-01",
				"effective_to": "2027-03-31",
			}
		with (
			patch("za_local_core.sa_vat.statutory.resolve_rates", return_value=resolved),
			self.assertRaises(frappe.ValidationError),
		):
			resolve_vat_controls("2026-04-01")


class TestAppAPISecurity(UnitTestCase):
	"""Every whitelisted endpoint in this app, and the verb each one allows.

	The sets are a complete inventory on purpose: equality is what catches an
	endpoint added or removed without review. The VAT names arrived with the SA VAT
	module from the retired ``za_local_finance`` app.
	"""

	READ_ONLY: ClassVar[frozenset[str]] = frozenset(
		{
			# Governance foundation
			"get_company_readiness",
			"get_guide_status",
			"is_wiki_available",
			# SA VAT
			"get_charts_for_country_with_za",
			"check_tax_invoice_readiness",
			"get_sales_invoice_print_profile",
			# Refuses and explains; it submits nothing.
			"submit_to_sars",
			"get_summary_rows",
			"get_linked_transaction_rows",
		}
	)
	MUTATING: ClassVar[frozenset[str]] = frozenset(
		{
			# Governance foundation
			"mark_reviewed",
			"publish_practitioner_guide",
			# SA VAT
			"bootstrap_company_vat_setup",
			"bootstrap_defaults",
			"sync_vat_accounts",
			"get_vat_transactions",
			"record_submission_receipt",
		}
	)

	def test_every_whitelisted_method_declares_get_or_post(self):
		found = {}
		for path in PACKAGE_ROOT.rglob("*.py"):
			if "__pycache__" in path.parts:
				continue
			tree = ast.parse(path.read_text())
			for node in ast.walk(tree):
				if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
					continue
				for decorator in node.decorator_list:
					if not isinstance(decorator, ast.Call) or not _is_whitelist(decorator.func):
						continue
					methods = next(
						(keyword.value for keyword in decorator.keywords if keyword.arg == "methods"),
						None,
					)
					self.assertIsNotNone(methods, msg=f"{path}:{node.lineno} has no methods=")
					found[node.name] = set(ast.literal_eval(methods))

		self.assertEqual(self.READ_ONLY | self.MUTATING, set(found))
		for name in self.READ_ONLY:
			self.assertEqual({"GET"}, found[name], msg=name)
		for name in self.MUTATING:
			self.assertEqual({"POST"}, found[name], msg=name)

	def test_log_error_calls_do_not_use_swapped_two_positional_arguments(self):
		for path in PACKAGE_ROOT.rglob("*.py"):
			tree = ast.parse(path.read_text())
			for node in ast.walk(tree):
				if isinstance(node, ast.Call) and _is_log_error(node.func):
					self.assertLessEqual(
						len(node.args),
						1,
						msg=f"{path}:{node.lineno} must use title= and message=",
					)


class TestVATSubmissionIdempotency(IntegrationTestCase):
	def test_submission_receipt_retry_returns_the_existing_submitted_receipt(self):
		content = b"_test SARS VAT receipt"
		checksum = hashlib.sha256(content).hexdigest()
		file_doc = save_file("_test-vat-receipt.txt", content, None, None, is_private=1)
		vat_return = frappe._dict(za_filing="ZA-FIL-TEST")
		existing = frappe._dict(
			name="ZA-RECEIPT-TEST",
			filing="ZA-FIL-TEST",
			authority_reference="SARS-REF-1",
			response_status="Accepted",
			submitted_by="_test.finance.approver@example.com",
			docstatus=1,
		)
		with (
			patch("frappe.has_permission"),
			patch("frappe.db.get_value", return_value=existing),
		):
			result = record_submission_receipt(
				vat_return,
				authority_reference="SARS-REF-1",
				response_status="Accepted",
				evidence_file=file_doc.file_url,
				sha256_checksum=checksum,
				submitted_by="_test.finance.approver@example.com",
			)
		self.assertEqual("ZA-RECEIPT-TEST", result)


class TestVATGovernedLifecycle(IntegrationTestCase):
	def test_prepare_review_approve_receipt_cancel_and_amend(self):
		company = get_configured_vat_company()
		if not company:
			self.skipTest("A South African company with VAT Settings is required.")
		settings = get_vat_settings(company)
		if not settings.output_vat_account or not settings.input_vat_account:
			self.skipTest("Configured VAT accounts are required.")
		reviewer = self._ensure_user(
			"_test.finance.reviewer@example.com",
			"Finance Reviewer",
			("ZA Compliance Reviewer", "Accounts Manager"),
		)
		approver = self._ensure_user(
			"_test.finance.approver@example.com",
			"Finance Approver",
			("ZA Compliance Manager", "Accounts Manager"),
		)
		obligation = self._approved_vat_obligation(reviewer)
		governance = stage_approved_test_vat_governance("2011-01-01", "2011-12-31")
		self.assertEqual(1, frappe.db.get_value("ZA Statutory Source", governance["source"], "docstatus"))
		self.assertEqual(
			1, frappe.db.get_value("ZA Statutory Rate Pack", governance["rate_pack"], "docstatus")
		)
		settings.statutory_control_date = "2011-04-01"
		settings.vat201_compliance_obligation = obligation.name
		settings.save()

		values = {
			"doctype": "VAT201 Return",
			"company": company,
			"filing_category": "Category C",
			"from_date": "2011-04-01",
			"to_date": "2011-04-30",
			"submission_date": "2011-05-01",
			"filing_due_date": "2011-05-25",
			"filing_reviewer": reviewer,
			"filing_approver": approver,
			"status": "Draft",
		}
		vat_return = VAT201Return(values).insert()
		journal_entry = frappe.db.get_value("Journal Entry", {"docstatus": 1}, "name")
		if not journal_entry:
			self.skipTest("A submitted Journal Entry is required for the governed lifecycle test.")
		row = frappe._dict(
			voucher_type="Journal Entry",
			voucher_no=journal_entry,
			posting_date="2011-04-30",
			classification="SARS Payment/Receipt",
			classification_status=CLASSIFIED,
			tax_amount=0,
			gross_tax_amount=0,
			incl_tax_amount=0,
			source_rows_json=json.dumps([{"name": journal_entry}]),
			source_modified="2011-04-30 12:00:00",
			source_currency="ZAR",
			exchange_rate=1,
			source_tax_amount=0,
			source_base_tax_amount=0,
			tax_account=settings.input_vat_account,
			gl_entries_json="[]",
			gl_tax_amount=0,
			is_cancelled=0,
		)
		finalize_row_snapshot(row)
		vat_return.append("transactions", row)
		vat_return.snapshot_generated_on = "2011-05-01 00:00:00"
		set_parent_reconciliation(vat_return)
		vat_return.live_ledger_sha256 = calculate_live_ledger_sha256(vat_return, settings)
		vat_return.save()
		vat_return.submit()

		vat_return.reload()
		self.assertEqual("Prepared", vat_return.status)
		self.assertTrue(vat_return.za_filing)
		self.assertTrue(vat_return.working_paper_file.startswith("/private/files/"))
		filing = frappe.get_doc("ZA Filing", vat_return.za_filing)
		with self.set_user(reviewer):
			filing.mark_reviewed()
		filing.reload()
		with self.set_user(approver):
			filing.submit()

		receipt_content = b"_test accepted VAT201 receipt"
		receipt_file = save_file(
			"_test-accepted-vat201.txt",
			receipt_content,
			None,
			None,
			is_private=1,
		)
		with self.set_user(reviewer):
			receipt_name = vat_return.record_submission_receipt(
				authority_reference="_TEST-SARS-VAT-ACCEPTED",
				response_status="Accepted",
				evidence_file=receipt_file.file_url,
				sha256_checksum=hashlib.sha256(receipt_content).hexdigest(),
				submitted_by=approver,
				submitted_at="2011-05-20 10:00:00",
			)
		receipt = frappe.get_doc("ZA Submission Receipt", receipt_name)
		with self.set_user(approver):
			receipt.submit()
		self.assertEqual("Accepted", frappe.db.get_value("VAT201 Return", vat_return.name, "status"))
		with self.set_user(approver):
			receipt.cancel()
		frappe.set_user("Administrator")
		vat_return.reload()
		vat_return.cancel()
		with self.set_user(approver):
			filing.reload()
			filing.cancel()
		frappe.set_user("Administrator")
		amended = VAT201Return({**values, "amended_from": vat_return.name}).insert()
		self.assertEqual("Draft", amended.status)
		self.assertFalse(amended.za_filing)
		self.assertEqual([], amended.transactions)

	def _approved_vat_obligation(self, reviewer: str):
		content = b"_test approved VAT source"
		checksum = hashlib.sha256(content).hexdigest()
		file_doc = save_file("_test-vat-source.txt", content, None, None, is_private=1)
		source = frappe.get_doc(
			{
				"doctype": "ZA Statutory Source",
				"authority": "SARS",
				"title": f"_Test VAT source {checksum[:8]}",
				"document_type": "Guide",
				"version": checksum[:8],
				"publication_date": "2011-03-01",
				"effective_from": "2011-03-01",
				"source_url": "https://www.sars.gov.za/",
				"source_file": file_doc.file_url,
				"sha256_checksum": checksum,
				"reviewed_by": reviewer,
			}
		).insert()
		with self.set_user(reviewer):
			source.submit()
		frappe.set_user("Administrator")
		obligation = frappe.get_doc(
			{
				"doctype": "ZA Compliance Obligation",
				"obligation_code": f"_TEST-FINANCE-VAT201-{checksum[:8]}",
				"title": "_Test Finance VAT201",
				"domain": "VAT",
				"authority": "SARS",
				"source": source.name,
				"frequency": "Monthly",
				"due_rule": "_Test confirmed due date",
				"capability": "Controlled Manual",
				"effective_from": "2011-03-01",
			}
		).insert()
		obligation.submit()
		return obligation

	@staticmethod
	def _ensure_user(email: str, first_name: str, roles: tuple[str, ...]) -> str:
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": first_name,
					"send_welcome_email": 0,
				}
			).insert(ignore_permissions=True)
		user = frappe.get_doc("User", email)
		for role in roles:
			if role not in frappe.get_roles(email):
				user.add_roles(role)
		return email


def _is_whitelist(node) -> bool:
	return (
		isinstance(node, ast.Attribute)
		and isinstance(node.value, ast.Name)
		and node.value.id == "frappe"
		and node.attr == "whitelist"
	)


def _is_log_error(node) -> bool:
	return (
		isinstance(node, ast.Attribute)
		and isinstance(node.value, ast.Name)
		and node.value.id == "frappe"
		and node.attr == "log_error"
	)
