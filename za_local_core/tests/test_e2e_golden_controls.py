import json
from pathlib import Path

import frappe
from frappe.tests.classes import IntegrationTestCase


class TestE2EGoldenControls(IntegrationTestCase):
	def setUp(self):
		path = Path(frappe.get_app_path("za_local_core", "tests", "golden", "2026_27_e2e.json"))
		self.controls = json.loads(path.read_text())

	def test_statutory_controls_are_explicit_and_source_backed(self):
		self.assertEqual("2026-2027", self.controls["tax_year"])
		self.assertEqual(17712.0, self.controls["uif"]["monthly_remuneration_cap"])
		self.assertEqual(0.01, self.controls["uif"]["employee_rate"])
		self.assertEqual(0.01, self.controls["uif"]["employer_rate"])
		self.assertEqual(0.01, self.controls["sdl"]["rate"])
		self.assertEqual(0.15, self.controls["vat"]["standard_rate"])
		for key in ("uif", "sdl", "vat", "employees_tax"):
			source = self.controls["sources"][key]
			self.assertTrue(source.startswith("https://www.sars.gov.za/"), source)
		self.assertTrue(self.controls["sources"]["coida"].startswith("https://www.gov.za/"))

	def test_expected_vat_control_reconciles(self):
		vat = self.controls["vat"]
		self.assertAlmostEqual(
			vat["expected_output_tax"] - vat["expected_input_tax"],
			vat["expected_payable"],
			places=2,
		)

	def test_expected_coida_control_reconciles(self):
		coida = self.controls["coida"]
		self.assertAlmostEqual(
			coida["expected_assessable_earnings"] * 0.0125,
			coida["expected_assessment_fee"],
			places=2,
		)
