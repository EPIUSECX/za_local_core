"""The BCEA earnings threshold source must cite the gazette, not a press release."""

import frappe
from frappe.tests.classes import IntegrationTestCase, UnitTestCase

from za_local_core.migration.backfill import _source_catalog
from za_local_core.patches.v1_4.correct_bcea_threshold_source import (
	CATALOG_KEY,
	STALE_AMOUNT,
	STALE_URL,
	execute,
)

# Government Notice 7384, Government Gazette 54544, 17 April 2026.
GAZETTED_ANNUAL = 269600.90
GAZETTED_MONTHLY = 22466.74


class TestSeededCatalogueEntry(UnitTestCase):
	def _entry(self) -> dict:
		entry = next((row for row in _source_catalog() if row["catalog_key"] == CATALOG_KEY), None)
		self.assertIsNotNone(entry, f"{CATALOG_KEY} is missing from the catalogue")
		return entry

	def test_it_cites_a_retrievable_document_not_a_media_statement(self):
		"""A press release is a secondary source and is weak evidence under query.

		Its siblings, the national minimum wage and COIDA notices, both link the
		gazette itself.
		"""
		url = self._entry()["source_url"]
		self.assertNotEqual(STALE_URL, url)
		self.assertNotIn("Media-Desk", url, "the source still points at a media statement")
		self.assertTrue(url.lower().endswith(".pdf"), f"the source is not a document: {url}")

	def test_it_records_the_gazette_and_notice_numbers(self):
		entry = self._entry()
		self.assertIn("54544", entry["version"])
		self.assertIn("7384", entry["version"])
		self.assertEqual("2026-04-17", entry["publication_date"])

	def test_the_recorded_threshold_is_internally_consistent(self):
		"""R269,900.90 was a transposed digit. The monthly figure is what catches it.

		A note quoting the wrong threshold is what a practitioner transcribes into a
		Labour rate pack, so it has to be arithmetically checkable.
		"""
		notes = self._entry()["notes"]
		self.assertNotIn(STALE_AMOUNT, notes)
		self.assertIn("R269,600.90", notes)
		self.assertAlmostEqual(GAZETTED_ANNUAL / 12, GAZETTED_MONTHLY, places=2)
		self.assertIn("R22,466.74", notes)


class TestCorrectionPatch(IntegrationTestCase):
	def setUp(self):
		self.name = frappe.db.get_value("ZA Statutory Source", {"catalog_key": CATALOG_KEY}, "name")
		if not self.name:
			self.skipTest("the BCEA source is not seeded on this site")
		self.restore = frappe.db.get_value(
			"ZA Statutory Source", self.name, ["source_url", "notes", "docstatus"], as_dict=True
		)

	def tearDown(self):
		frappe.db.set_value("ZA Statutory Source", self.name, dict(self.restore), update_modified=False)

	def _make_stale(self, docstatus: int = 0):
		frappe.db.set_value(
			"ZA Statutory Source",
			self.name,
			{
				"source_url": STALE_URL,
				"notes": f"Records the {STALE_AMOUNT} annual threshold.",
				"docstatus": docstatus,
			},
			update_modified=False,
		)

	def test_a_draft_still_holding_the_old_values_is_corrected(self):
		self._make_stale()
		execute()
		self.assertNotIn(STALE_AMOUNT, frappe.db.get_value("ZA Statutory Source", self.name, "notes") or "")

	def test_running_it_again_changes_nothing(self):
		self._make_stale()
		execute()
		once = frappe.db.get_value("ZA Statutory Source", self.name, ["source_url", "notes"], as_dict=True)
		execute()
		self.assertEqual(
			dict(once),
			dict(
				frappe.db.get_value("ZA Statutory Source", self.name, ["source_url", "notes"], as_dict=True)
			),
		)

	def test_an_approved_record_is_never_rewritten(self):
		"""Someone signed that record off. Correcting it silently would hide that."""
		self._make_stale(docstatus=1)
		execute()
		self.assertEqual(STALE_URL, frappe.db.get_value("ZA Statutory Source", self.name, "source_url"))

	def test_an_approved_record_is_flagged_for_a_human(self):
		self._make_stale(docstatus=1)
		before = frappe.db.count("Error Log", {"method": ["like", "%BCEA earnings threshold%"]})
		execute()
		self.assertGreater(
			frappe.db.count("Error Log", {"method": ["like", "%BCEA earnings threshold%"]}),
			before,
			"an approved record holding the wrong threshold was neither fixed nor reported",
		)


class TestVatControlsSource(UnitTestCase):
	"""The VAT source cites SARS's standing page rather than a budget-cycle FAQ."""

	def _metadata(self) -> dict:
		from za_local_core.sa_vat.statutory import CURRENT_APPROVED_SOURCE_METADATA

		return CURRENT_APPROVED_SOURCE_METADATA

	def test_the_primary_source_is_the_page_sars_maintains(self):
		"""A Budget FAQ is archived once the next budget lands, taking the evidence."""
		url = self._metadata()["registration_source_url"]
		self.assertNotIn("budget-2026-frequently-asked-questions", url)
		self.assertIn("sars.gov.za", url)

	def test_the_budget_announcement_is_kept_for_provenance(self):
		"""Dropping it would lose when and how the thresholds changed."""
		self.assertIn("budget-2026", self._metadata()["announcement_source_url"])

	def test_the_recorded_control_values_are_the_gazetted_ones(self):
		"""Budget 2026 raised both registration thresholds with effect from 1 April.

		Asserted because they look wrong against the figures that stood for the
		previous seventeen years, and someone will eventually "correct" them back.
		"""
		from za_local_core.sa_vat.statutory import (
			COMPULSORY_REGISTRATION_THRESHOLD,
			FULL_INVOICE_THRESHOLD,
			NO_INVOICE_THRESHOLD,
			STANDARD_RATE,
			VOLUNTARY_REGISTRATION_THRESHOLD,
		)

		values = self._metadata()["expected_current_values"]
		self.assertEqual(15, values[STANDARD_RATE])
		self.assertEqual(2_300_000, values[COMPULSORY_REGISTRATION_THRESHOLD])
		self.assertEqual(120_000, values[VOLUNTARY_REGISTRATION_THRESHOLD])
		self.assertEqual(50, values[NO_INVOICE_THRESHOLD])
		self.assertEqual(5_000, values[FULL_INVOICE_THRESHOLD])
