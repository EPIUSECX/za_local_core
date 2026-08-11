"""Seeding that must follow the company, not the app install."""

import frappe
from frappe.tests.classes import IntegrationTestCase, UnitTestCase

from za_local_core import hooks
from za_local_core.localisation import resolve_south_african_companies


class TestCompanyScopeResolution(UnitTestCase):
	def test_no_company_means_sweep_the_whole_site(self):
		"""Install and migrate pass nothing and must still cover every company."""
		self.assertEqual(
			sorted(frappe.get_all("Company", filters={"country": "South Africa"}, pluck="name")),
			sorted(resolve_south_african_companies()),
		)

	def test_a_named_south_african_company_scopes_to_itself(self):
		company = frappe.db.get_value("Company", {"country": "South Africa"}, "name")
		if not company:
			self.skipTest("site has no South African company")
		self.assertEqual([company], resolve_south_african_companies(company))

	def test_a_company_outside_south_africa_is_seeded_nothing(self):
		company = frappe.db.get_value("Company", {"country": ["!=", "South Africa"]}, "name")
		if not company:
			self.skipTest("site has no company outside South Africa")
		self.assertEqual([], resolve_south_african_companies(company))

	def test_an_unknown_company_is_seeded_nothing(self):
		self.assertEqual([], resolve_south_african_companies("No Such Company"))


class TestReadinessFollowsTheCompany(IntegrationTestCase):
	def test_core_hooks_seed_readiness_when_a_company_is_inserted(self):
		"""A site is installed before it has a company.

		The setup wizard creates the first one afterwards, so seeding that runs only
		at install or migrate leaves the SA Overview card counting zero capabilities
		awaiting sign-off, which reads as production ready when nothing was assessed.
		"""
		self.assertEqual(
			"za_local_core.custom.company.seed_readiness_for_new_company",
			hooks.doc_events["Company"]["after_insert"],
		)

	def test_every_south_african_company_has_readiness_recorded(self):
		"""No South African company may sit with an unassessed capability set."""
		companies = frappe.get_all("Company", filters={"country": "South Africa"}, pluck="name")
		if not companies:
			self.skipTest("site has no South African company")
		for company in companies:
			self.assertTrue(
				frappe.db.exists("ZA Feature Readiness", {"company": company}),
				f"{company} has no capability readiness records",
			)

	def test_readiness_is_never_recorded_for_a_company_outside_south_africa(self):
		for company in frappe.get_all("Company", filters={"country": ["!=", "South Africa"]}, pluck="name"):
			self.assertFalse(
				frappe.db.exists("ZA Feature Readiness", {"company": company}),
				f"{company} is not South African but carries readiness records",
			)
