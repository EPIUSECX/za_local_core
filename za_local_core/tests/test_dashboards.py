"""The workspace metrics must ship, stay idempotent and never render an error.

A customer site can be installed long before any payroll or VAT data exists, so
a metric that raises on an empty table would break the workspace on day one.
"""

import frappe
from frappe.desk.doctype.dashboard_chart.dashboard_chart import get as render_chart
from frappe.desk.doctype.number_card.number_card import get_result as render_card
from frappe.tests.classes import IntegrationTestCase

from za_local_core.dashboards import (
	CARD_DOCTYPE,
	CHART_DOCTYPE,
	display_currency,
	repair_metric_presentation,
	seed_dashboards,
)
from za_local_core.install import CORE_CHARTS, CORE_MODULE, CORE_NUMBER_CARDS, seed_core_dashboards

WORKSPACE = "SA Overview"


class TestCoreDashboards(IntegrationTestCase):
	def test_every_declared_metric_is_seeded(self):
		seed_core_dashboards()
		for spec in CORE_NUMBER_CARDS:
			self.assertTrue(frappe.db.exists(CARD_DOCTYPE, spec["label"]), spec["label"])
		for spec in CORE_CHARTS:
			self.assertTrue(frappe.db.exists(CHART_DOCTYPE, spec["chart_name"]), spec["chart_name"])

	def test_seeding_is_idempotent(self):
		seed_core_dashboards()
		before = frappe.db.count(CARD_DOCTYPE, {"module": CORE_MODULE})
		result = seed_core_dashboards()
		self.assertEqual(before, frappe.db.count(CARD_DOCTYPE, {"module": CORE_MODULE}))
		self.assertEqual([], result["skipped"])

	def test_metrics_declare_their_module_so_uninstall_reclaims_them(self):
		seed_core_dashboards()
		for doctype, specs, key in (
			(CARD_DOCTYPE, CORE_NUMBER_CARDS, "label"),
			(CHART_DOCTYPE, CORE_CHARTS, "chart_name"),
		):
			for spec in specs:
				self.assertEqual(CORE_MODULE, frappe.db.get_value(doctype, spec[key], "module"))

	def test_a_metric_reading_an_absent_doctype_is_skipped_not_created(self):
		"""Fail-safe: a metric this site cannot compute must not be created."""
		result = seed_dashboards(
			CORE_MODULE,
			cards=({"label": "_Test Absent DocType Card", "document_type": "_ZA No Such DocType"},),
			charts=(
				{
					"chart_name": "_Test Absent DocType Chart",
					"document_type": "_ZA No Such DocType",
					"group_by_based_on": "status",
				},
			),
		)
		self.assertEqual([], result["cards"])
		self.assertEqual([], result["charts"])
		self.assertFalse(frappe.db.exists(CARD_DOCTYPE, "_Test Absent DocType Card"))
		self.assertFalse(frappe.db.exists(CHART_DOCTYPE, "_Test Absent DocType Chart"))

	def test_a_metric_reading_an_absent_field_is_skipped_not_created(self):
		result = seed_dashboards(
			CORE_MODULE,
			cards=(
				{
					"label": "_Test Absent Field Card",
					"document_type": "ZA Filing",
					"function": "Sum",
					"aggregate_function_based_on": "za_no_such_field",
				},
			),
		)
		self.assertEqual([], result["cards"])
		self.assertFalse(frappe.db.exists(CARD_DOCTYPE, "_Test Absent Field Card"))

	def test_workspace_shows_the_seeded_metrics(self):
		seed_core_dashboards()
		workspace = frappe.get_doc("Workspace", WORKSPACE)
		shown_cards = {row.number_card_name for row in workspace.number_cards}
		shown_charts = {row.chart_name for row in workspace.charts}
		for spec in CORE_NUMBER_CARDS:
			self.assertIn(spec["label"], shown_cards)
		for spec in CORE_CHARTS:
			self.assertIn(spec["chart_name"], shown_charts)

	def test_every_core_metric_renders_without_data(self):
		"""The whole point: an empty site must not raise when the workspace loads."""
		seed_core_dashboards()
		for spec in CORE_NUMBER_CARDS:
			card = frappe.get_doc(CARD_DOCTYPE, spec["label"])
			render_card(card.as_dict(), card.filters_json)
		for spec in CORE_CHARTS:
			render_chart(chart_name=spec["chart_name"], refresh=1)

	def test_metrics_are_denominated_in_the_site_currency(self):
		"""Frappe stamps a currency at creation, and the metrics are seeded during
		app installation -- before the setup wizard has set the real one. Left alone
		they render South African statutory figures with the installer's default."""
		seed_core_dashboards()
		expected = display_currency()
		self.assertTrue(expected)

		for doctype in (CARD_DOCTYPE, CHART_DOCTYPE):
			for name in frappe.get_all(doctype, filters={"module": CORE_MODULE}, pluck="name"):
				self.assertEqual(
					frappe.db.get_value(doctype, name, "currency"),
					expected,
					f"{doctype} {name} is not denominated in the site currency",
				)

	def test_repair_restamps_a_stale_currency(self):
		seed_core_dashboards()
		card = CORE_NUMBER_CARDS[0]["label"]
		frappe.db.set_value(CARD_DOCTYPE, card, "currency", "INR")

		repair_metric_presentation(CORE_MODULE, cards=CORE_NUMBER_CARDS, charts=CORE_CHARTS)

		self.assertEqual(frappe.db.get_value(CARD_DOCTYPE, card, "currency"), display_currency())

	def test_the_repair_is_reachable_on_a_fresh_install(self):
		"""The repair itself was correct; nothing ever called it.

		``install_app`` marks every patch complete before it runs ``after_install``,
		so the repair patch could not execute on a fresh install, and
		``seed_dashboards`` skips records that already exist. The currency stamped
		during install was therefore permanent. Both call sites are asserted here
		because the defect was the wiring, not the repair.
		"""
		from za_local_core import hooks
		from za_local_core.install import after_migrate, repair_core_metrics

		self.assertEqual("za_local_core.install.repair_core_metrics", hooks.setup_wizard_complete)
		self.assertIs(frappe.get_attr(hooks.setup_wizard_complete), repair_core_metrics)
		self.assertIn("repair_core_metrics", after_migrate.__code__.co_names)

	def test_the_repair_covers_every_module_this_app_owns(self):
		"""A module left out of the repair keeps the installer's currency forever."""
		from za_local_core.install import repair_core_metrics
		from za_local_core.sa_vat.install import VAT_NUMBER_CARDS, seed_vat_dashboards

		seed_core_dashboards()
		seed_vat_dashboards()
		stale = [CORE_NUMBER_CARDS[0]["label"], VAT_NUMBER_CARDS[0]["label"]]
		for card in stale:
			frappe.db.set_value(CARD_DOCTYPE, card, "currency", "INR")

		# The setup wizard passes its payload positionally; it must be optional.
		repair_core_metrics(None)

		for card in stale:
			self.assertEqual(
				frappe.db.get_value(CARD_DOCTYPE, card, "currency"),
				display_currency(),
				f"{card} was not restamped",
			)
