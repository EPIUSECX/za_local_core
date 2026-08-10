"""SA VAT must be configurable on a fresh install without inventing a rate.

Resolution deliberately has no numeric fallback, so a site with no approved rate
pack cannot save VAT Settings at all. Shipping the pack the reviewer approves
turns that from a dead end into one review step, and these tests hold the line on
both halves: the draft must be complete, and it must never arrive approved.
"""

import frappe
from frappe.tests.classes import IntegrationTestCase

from za_local_core.sa_vat.install import (
	VAT_PACK_EFFECTIVE_FROM,
	VAT_PACK_EFFECTIVE_TO,
	seed_vat_statutory_rate_pack,
	seed_vat_statutory_source_catalog,
)
from za_local_core.sa_vat.statutory import (
	CURRENT_APPROVED_SOURCE_METADATA,
	VAT_CONTROL_RULE_KEYS,
	VAT_CONTROL_UNITS,
	VAT_DOMAIN,
)
from za_local_core.services.rates import describe_resolution_gap

PACK_DOCTYPE = "ZA Statutory Rate Pack"


class TestVATStatutoryBootstrap(IntegrationTestCase):
	def seeded_pack(self):
		return seed_vat_statutory_rate_pack(seed_vat_statutory_source_catalog())

	def test_the_draft_pack_answers_every_control_key(self):
		"""A pack missing one key blocks just as hard as no pack at all."""
		pack = frappe.get_doc(PACK_DOCTYPE, self.seeded_pack())
		expected = CURRENT_APPROVED_SOURCE_METADATA["expected_current_values"]

		self.assertEqual(VAT_DOMAIN, pack.domain)
		self.assertEqual({row.rule_key for row in pack.items}, set(VAT_CONTROL_RULE_KEYS))
		for row in pack.items:
			self.assertEqual(expected[row.rule_key], row.numeric_value, row.rule_key)
			self.assertEqual(VAT_CONTROL_UNITS[row.rule_key], row.unit, row.rule_key)

	def test_the_draft_pack_is_never_shipped_approved(self):
		"""Auto-approving a tax rate would defeat the control this app exists to keep."""
		pack = frappe.get_doc(PACK_DOCTYPE, self.seeded_pack())

		self.assertEqual(0, pack.docstatus)
		self.assertNotEqual("Approved", pack.status)
		self.assertFalse(pack.approved_on)
		self.assertEqual(0, frappe.db.get_value("ZA Statutory Source", pack.source, "docstatus"))

	def test_the_pack_is_closed_ended_and_linked_to_its_source(self):
		"""effective_to is mandatory, and a later period needs its own reviewed pack."""
		pack = frappe.get_doc(PACK_DOCTYPE, self.seeded_pack())

		self.assertEqual(VAT_PACK_EFFECTIVE_FROM, str(pack.effective_from))
		self.assertEqual(VAT_PACK_EFFECTIVE_TO, str(pack.effective_to))
		self.assertTrue(pack.source)

	def test_seeding_twice_does_not_create_an_overlapping_pack(self):
		first = self.seeded_pack()
		second = self.seeded_pack()

		self.assertEqual(first, second)
		self.assertEqual(
			1,
			frappe.db.count(
				PACK_DOCTYPE, {"domain": VAT_DOMAIN, "effective_from": VAT_PACK_EFFECTIVE_FROM}
			),
		)

	def test_the_gap_message_names_the_approval_steps(self):
		"""The old message named a rule key and stopped, which read as a bug."""
		self.seeded_pack()

		guidance = describe_resolution_gap(VAT_DOMAIN, "2026-06-30")

		self.assertIn("still a draft", guidance)
		self.assertIn("Reviewed By", guidance)
		self.assertIn("ZA Compliance Reviewer", guidance)
		# v16 redirects /app/* to /desk/*, so the canonical route avoids a round trip.
		self.assertIn("/desk/za-statutory-rate-pack/", guidance)
		self.assertIn("/desk/za-statutory-source/", guidance)

	def test_the_gap_message_lists_the_windows_that_do_exist(self):
		"""A date outside every window is the mistake the shipped date invites."""
		self.seeded_pack()

		guidance = describe_resolution_gap(VAT_DOMAIN, "2026-01-01")

		self.assertIn("No VAT rate pack covers 2026-01-01", guidance)
		self.assertIn(VAT_PACK_EFFECTIVE_FROM, guidance)
		self.assertIn(VAT_PACK_EFFECTIVE_TO, guidance)
		self.assertIn("Never widen an existing window", guidance)

	def test_the_gap_message_survives_a_site_with_no_pack(self):
		_clear_vat_packs()

		guidance = describe_resolution_gap(VAT_DOMAIN, "2026-06-30")

		self.assertIn("bench migrate", guidance)


def _clear_vat_packs() -> None:
	for name in frappe.get_all(PACK_DOCTYPE, filters={"domain": VAT_DOMAIN}, pluck="name"):
		frappe.delete_doc(PACK_DOCTYPE, name, force=True, ignore_permissions=True)


class TestVATStatutoryBootstrapAroundAPractitionerPack(IntegrationTestCase):
	"""Separate class: IntegrationTestCase rolls back once per class, and a pack
	spanning the seeded window would otherwise starve every sibling test."""

	def test_a_practitioner_pack_is_left_alone(self):
		"""Overlaps are rejected on validate, and an install is no place to raise."""
		source = seed_vat_statutory_source_catalog()
		_clear_vat_packs()
		theirs = frappe.get_doc(
			{
				"doctype": PACK_DOCTYPE,
				"domain": VAT_DOMAIN,
				"title": "Practitioner owned window",
				"source": source,
				"effective_from": "2026-01-01",
				"effective_to": "2027-12-31",
				"items": [{"rule_key": "vat.standard_rate", "numeric_value": 15, "unit": "Percentage"}],
			}
		).insert(ignore_permissions=True)

		self.assertIsNone(seed_vat_statutory_rate_pack(source))
		self.assertEqual([theirs.name], frappe.get_all(PACK_DOCTYPE, pluck="name"))
