import json
from copy import deepcopy
from pathlib import Path

from frappe.tests import UnitTestCase

from za_local_core.migration.ownership import (
	classify_path,
	validate_manifest,
	verify_checked_manifest,
)


class TestOwnershipManifest(UnitTestCase):
	def test_domain_paths_have_one_explicit_owner(self):
		self.assertEqual(classify_path("za_local/sa_vat/doctype/x/x.py").owner, "za_local_finance")
		self.assertEqual(classify_path("za_local/sa_payroll/doctype/x/x.py").owner, "za_local_payroll")
		self.assertEqual(classify_path("za_local/sa_labour/doctype/x/x.py").owner, "za_local_workplace")
		self.assertEqual(classify_path("za_local/sa_coida/doctype/x/x.py").owner, "za_local_workplace")

	def test_checked_manifest_is_internally_complete(self):
		manifest = verify_checked_manifest()

		self.assertEqual(manifest["artifact_count"], len(manifest["artifacts"]))
		self.assertEqual(
			manifest["artifact_count"],
			sum(manifest["owner_counts"].values()),
		)
		self.assertTrue(all(artifact["owner"] for artifact in manifest["artifacts"]))
		self.assertEqual(
			manifest["artifact_count"],
			len({artifact["path"] for artifact in manifest["artifacts"]}),
		)
		self.assertNotIn("migration_split", manifest["owner_counts"])
		self.assertEqual(2, manifest["schema_version"])

	def test_checked_manifest_has_a_packaged_json_schema(self):
		schema_path = Path(__file__).resolve().parents[2] / "ownership_manifest.schema.json"
		schema = json.loads(schema_path.read_text(encoding="utf-8"))
		self.assertEqual(2, schema["properties"]["schema_version"]["const"])
		self.assertFalse(schema["additionalProperties"])

	def test_manifest_validation_rejects_tampered_artifacts(self):
		manifest = verify_checked_manifest()
		for field, value, message in (
			("owner", "unknown_app", "unsupported ownership target"),
			("sha256", "not-a-digest", "invalid SHA-256"),
		):
			tampered = deepcopy(manifest)
			tampered["artifacts"][0][field] = value
			with self.assertRaisesRegex(ValueError, message):
				validate_manifest(tampered)

		duplicate = deepcopy(manifest)
		duplicate["artifacts"][1]["path"] = duplicate["artifacts"][0]["path"]
		with self.assertRaisesRegex(ValueError, "duplicate or empty ownership path"):
			validate_manifest(duplicate)
