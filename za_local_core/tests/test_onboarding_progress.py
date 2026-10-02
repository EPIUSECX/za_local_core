"""The setup checklists must reflect the configuration that exists.

Frappe ticks a "Create Entry" step only when the record is saved from the form the
checklist opens, so a site configured from the forms directly showed every such
step outstanding beside the records it asked for.
"""

from unittest.mock import patch

import frappe
from frappe.tests.classes import IntegrationTestCase

from za_local_core import onboarding

VAT201_STEP = "Create a VAT201 Return"
REVIEW_STEP = "Review South Africa VAT Settings"


class TestOnboardingProgress(IntegrationTestCase):
	def setUp(self):
		for step in (VAT201_STEP, REVIEW_STEP):
			frappe.db.set_value("Onboarding Step", step, "is_complete", 0)
		frappe.cache.delete_value(onboarding.CACHE_KEY)

	def test_create_entry_steps_of_both_apps_are_known(self):
		doctypes = onboarding.create_entry_doctypes()
		self.assertIn("VAT201 Return", doctypes)
		if frappe.db.exists("Module Def", "SA Payroll"):
			self.assertIn("EMP201 Submission", doctypes)

	def test_creating_the_record_anywhere_completes_its_step(self):
		onboarding.mark_created(frappe._dict(doctype="VAT201 Return"))
		self.assertEqual(1, frappe.db.get_value("Onboarding Step", VAT201_STEP, "is_complete"))

	def test_other_doctypes_leave_the_checklist_alone(self):
		onboarding.mark_created(frappe._dict(doctype="ToDo"))
		self.assertEqual(0, frappe.db.get_value("Onboarding Step", VAT201_STEP, "is_complete"))

	def test_sync_ticks_only_create_steps_whose_record_exists(self):
		real_exists = frappe.db.exists

		def exists(doctype, filters=None, *args, **kwargs):
			if doctype == "VAT201 Return" and isinstance(filters, dict):
				return "VAT201-TEST"
			return real_exists(doctype, filters, *args, **kwargs)

		with patch.object(frappe.db, "exists", side_effect=exists):
			ticked = onboarding.sync_onboarding_progress()

		self.assertIn(VAT201_STEP, ticked)
		# A review step is evidenced only by someone opening it.
		self.assertEqual(0, frappe.db.get_value("Onboarding Step", REVIEW_STEP, "is_complete"))

	def test_sync_leaves_a_step_open_when_no_record_exists(self):
		real_exists = frappe.db.exists

		def exists(doctype, filters=None, *args, **kwargs):
			if doctype == "VAT201 Return" and isinstance(filters, dict):
				return None
			return real_exists(doctype, filters, *args, **kwargs)

		with patch.object(frappe.db, "exists", side_effect=exists):
			ticked = onboarding.sync_onboarding_progress()

		self.assertNotIn(VAT201_STEP, ticked)
		self.assertEqual(0, frappe.db.get_value("Onboarding Step", VAT201_STEP, "is_complete"))

	def test_refresh_corrects_wording_but_keeps_progress(self):
		"""A ticked step is newer than its file, so Frappe never re-imports its wording."""
		frappe.db.set_value(
			"Onboarding Step", REVIEW_STEP, {"action_label": "Open VAT Settings", "is_complete": 1}
		)

		self.assertIn(REVIEW_STEP, onboarding.refresh_step_presentation())

		label, done = frappe.db.get_value("Onboarding Step", REVIEW_STEP, ["action_label", "is_complete"])
		self.assertEqual(REVIEW_STEP, label)
		self.assertEqual(1, done)
		self.assertNotIn(REVIEW_STEP, onboarding.refresh_step_presentation())

	def test_wired_to_inserts_and_migrate(self):
		from za_local_core import hooks
		from za_local_core.install import after_migrate

		self.assertEqual("za_local_core.onboarding.mark_created", hooks.doc_events["*"]["after_insert"])
		self.assertIn("sync_onboarding_progress", after_migrate.__code__.co_names)
		self.assertIn("refresh_step_presentation", after_migrate.__code__.co_names)
