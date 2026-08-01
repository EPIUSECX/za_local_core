from pathlib import Path

from frappe.tests import UnitTestCase

from za_local_core.migration.ownership import build_manifest, classify_path


class TestOwnershipManifest(UnitTestCase):
	def test_domain_paths_have_one_explicit_owner(self):
		self.assertEqual(classify_path("za_local/sa_vat/doctype/x/x.py").owner, "za_local_finance")
		self.assertEqual(classify_path("za_local/sa_payroll/doctype/x/x.py").owner, "za_local_payroll")
		self.assertEqual(classify_path("za_local/sa_labour/doctype/x/x.py").owner, "za_local_workplace")
		self.assertEqual(classify_path("za_local/sa_coida/doctype/x/x.py").owner, "za_local_workplace")

	def test_manifest_accounts_for_every_tracked_legacy_file(self):
		legacy_repo = Path(__file__).resolve().parents[3] / "za_local"
		manifest = build_manifest(legacy_repo)
		self.assertEqual(manifest["artifact_count"], len(manifest["artifacts"]))
		self.assertEqual(
			manifest["artifact_count"],
			sum(manifest["owner_counts"].values()),
		)
		self.assertTrue(all(artifact["owner"] for artifact in manifest["artifacts"]))
