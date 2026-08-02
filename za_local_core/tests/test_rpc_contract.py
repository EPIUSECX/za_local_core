import ast
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from za_local_core.api import get_company_readiness
from za_local_core.practitioner_guide.stage import is_wiki_available, publish_practitioner_guide
from za_local_core.sa_localisation_core.doctype.za_company_compliance_profile.za_company_compliance_profile import (
	ZACompanyComplianceProfile,
)
from za_local_core.sa_localisation_core.doctype.za_filing.za_filing import ZAFiling


class TestRPCContract(IntegrationTestCase):
	def test_read_endpoints_are_get_only(self):
		self.assertEqual(_allowed_methods(get_company_readiness), {"GET"})
		self.assertEqual(_allowed_methods(is_wiki_available), {"GET"})

	def test_publication_endpoint_is_post_only(self):
		self.assertEqual(_allowed_methods(publish_practitioner_guide), {"POST"})
		self.assertEqual(_allowed_methods(ZACompanyComplianceProfile.mark_reviewed), {"POST"})
		self.assertEqual(_allowed_methods(ZAFiling.mark_reviewed), {"POST"})

	def test_publication_preserves_system_manager_gate(self):
		with (
			patch("frappe.only_for") as only_for,
			patch("za_local_core.practitioner_guide.stage._wiki_installed", return_value=False),
		):
			publish_practitioner_guide()

		only_for.assert_called_once_with("System Manager")

	def test_core_has_no_whitelist_with_implicit_http_methods(self):
		package = Path(__file__).resolve().parents[1]
		for path in package.rglob("*.py"):
			tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
			for node in ast.walk(tree):
				if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
					continue
				for decorator in node.decorator_list:
					if not _is_whitelist_call(decorator):
						continue
					self.assertIn("methods", {keyword.arg for keyword in decorator.keywords}, path)


def _allowed_methods(function) -> set[str]:
	return set(frappe.allowed_http_methods_for_whitelisted_func[function])


def _is_whitelist_call(decorator: ast.expr) -> bool:
	return (
		isinstance(decorator, ast.Call)
		and isinstance(decorator.func, ast.Attribute)
		and decorator.func.attr == "whitelist"
	)
