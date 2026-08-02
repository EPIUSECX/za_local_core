import json
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from za_local_core.install import after_migrate
from za_local_core.migration.backfill import run, seed_statutory_source_catalog
from za_local_core.migration.release import assert_legacy_app_absent, core_state_fingerprint


class TestMigrationRelease(IntegrationTestCase):
	def test_backfill_and_after_migrate_are_idempotent(self):
		run()
		after_migrate()
		first = core_state_fingerprint()
		run()
		after_migrate()
		self.assertEqual(first, core_state_fingerprint())

	def test_source_catalog_is_seeded_as_unapproved_and_is_idempotent(self):
		seed_statutory_source_catalog()
		catalog = json.loads(
			Path(frappe.get_app_path("za_local_core", "data", "statutory_source_catalog.json")).read_text(
				encoding="utf-8"
			)
		)
		catalog_keys = {entry["catalog_key"] for entry in catalog}
		by_key = {entry["catalog_key"]: entry for entry in catalog}
		self.assertEqual("2026-03-01", by_key["COIDA-GAZETTE-54577-NOTICE-3910"]["effective_from"])
		self.assertIn("R668,000", by_key["COIDA-GAZETTE-54577-NOTICE-3910"]["notes"])
		self.assertEqual("2026-05-01", by_key["DEL-BCEA-EARNINGS-THRESHOLD-2026"]["effective_from"])
		self.assertIn("R30.23", by_key["DEL-NMW-GAZETTE-54075-NOTICE-7083"]["notes"])
		rows = frappe.get_all(
			"ZA Statutory Source",
			filters={"catalog_key": ["in", sorted(catalog_keys)]},
			fields=["catalog_key", "status", "docstatus"],
		)
		self.assertEqual(5, len(rows))
		self.assertEqual(catalog_keys, {row.catalog_key for row in rows})
		self.assertTrue(all(row.status == "Draft" and row.docstatus == 0 for row in rows))
		self.assertEqual(0, seed_statutory_source_catalog())


class TestLegacyAbsence(UnitTestCase):
	def test_release_gate_rejects_legacy_app(self):
		with patch("frappe.get_installed_apps", return_value=["frappe", "erpnext", "za_local"]):
			with self.assertRaisesRegex(RuntimeError, "Legacy app za_local"):
				assert_legacy_app_absent()

	def test_core_python_has_no_legacy_imports(self):
		package = Path(__file__).resolve().parents[1]
		for path in package.rglob("*.py"):
			if path.parts[-2] == "tests":
				continue
			content = path.read_text(encoding="utf-8")
			self.assertNotIn("from za_local ", content, path)
			self.assertNotIn("import za_local\n", content, path)
