import ast
import re
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from za_local_core.api import get_company_readiness
from za_local_core.practitioner_guide.stage import (
	get_guide_status,
	is_wiki_available,
	publish_practitioner_guide,
)
from za_local_core.sa_localisation_core.doctype.za_company_compliance_profile.za_company_compliance_profile import (
	ZACompanyComplianceProfile,
)
from za_local_core.sa_localisation_core.doctype.za_filing.za_filing import ZAFiling


class TestRPCContract(IntegrationTestCase):
	def test_read_endpoints_are_get_only(self):
		self.assertEqual(_allowed_methods(get_company_readiness), {"GET"})
		self.assertEqual(_allowed_methods(is_wiki_available), {"GET"})
		self.assertEqual(_allowed_methods(get_guide_status), {"GET"})

	def test_desk_page_states_an_http_method_each_endpoint_allows(self):
		"""``frappe.call`` defaults to POST, and Frappe rejects a method an endpoint
		does not allow as "Not permitted" -- which reads like a role problem and is
		not one. Every call in the page must name its method, and name it correctly.
		"""
		source = (Path(__file__).resolve().parents[1] / PAGE_JS).read_text(encoding="utf-8")
		constants = dict(METHOD_CONSTANT.findall(source))
		calls = CALL_WITH_METHOD.findall(source)

		# Guard the regex itself: a restructured page must fail here, not pass empty.
		self.assertEqual(source.count("frappe\n\t\t.call({"), len(calls), "a call states no HTTP method")
		self.assertGreaterEqual(len(calls), 2)

		for constant, http_method in calls:
			dotted = constants[constant]
			allowed = _allowed_methods(frappe.get_attr(dotted))
			self.assertIn(
				http_method, allowed, f"{dotted} allows {sorted(allowed)}, page sends {http_method}"
			)

	def test_reading_guide_status_does_not_require_a_role(self):
		"""The page hides its own action instead of erroring for a reader."""
		with patch("frappe.get_roles", return_value=["Guide Reader"]):
			status = get_guide_status()
		self.assertFalse(status["can_publish"])
		self.assertEqual(len(status["spaces"]), 2)

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


PAGE_JS = "sa_localisation_core/page/sa_localisation_guides/sa_localisation_guides.js"
METHOD_CONSTANT = re.compile(r'^const (\w+) = "([\w.]+)";$', re.MULTILINE)
CALL_WITH_METHOD = re.compile(r'\.call\(\{\s*method:\s*(\w+),\s*type:\s*"(\w+)"\s*\}\)')


def _allowed_methods(function) -> set[str]:
	return set(frappe.allowed_http_methods_for_whitelisted_func[function])


def _is_whitelist_call(decorator: ast.expr) -> bool:
	return (
		isinstance(decorator, ast.Call)
		and isinstance(decorator.func, ast.Attribute)
		and decorator.func.attr == "whitelist"
	)
