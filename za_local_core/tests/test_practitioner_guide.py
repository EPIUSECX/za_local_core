"""Regression tests for the federated practitioner and end-user guides."""

import re
from pathlib import Path

import frappe
from frappe.tests import UnitTestCase

from za_local_core.practitioner_guide.registry import get_guides

RELATIVE_LINK = re.compile(r"\]\((?!https?://|#|mailto:)([^)]+)\)")


class TestPractitionerGuide(UnitTestCase):
	def test_all_installed_domains_contribute_pages_with_unique_routes(self):
		guides = get_guides()
		apps = set()
		routes = set()
		for guide in guides:
			for group in guide["groups"]:
				for page in group["pages"]:
					apps.add(page["app"])
					route = f"{guide['space']['route']}/{group['key']}/{page['slug']}"
					self.assertNotIn(route, routes)
					routes.add(route)

		self.assertEqual(
			apps,
			{"za_local_core", "za_local_finance", "za_local_payroll", "za_local_workplace"},
		)

	def test_relative_links_resolve_to_published_pages(self):
		guides = get_guides()
		all_routes = {
			f"{guide['space']['route']}/{group['key']}/{page['slug']}"
			for guide in guides
			for group in guide["groups"]
			for page in group["pages"]
		}
		for guide in guides:
			targets = {
				f"{group['key']}/{page['slug']}"
				for group in guide["groups"]
				for page in group["pages"]
			}
			for group in guide["groups"]:
				for page in group["pages"]:
					path = Path(
						frappe.get_app_path(
							page["app"], "practitioner_guide", "content", page["file"]
						)
					)
					for link in RELATIVE_LINK.findall(path.read_text(encoding="utf-8")):
						clean = link.split("#", 1)[0].strip().rstrip("/")
						if not clean or clean.endswith((".png", ".jpg", ".jpeg", ".svg", ".pdf")):
							continue
						if clean.startswith("/"):
							self.assertIn(clean.lstrip("/"), all_routes, msg=f"Broken guide link in {path.name}: {link}")
							continue
						target = clean[3:] if clean.startswith("../") else f"{group['key']}/{clean}"
						self.assertIn(target, targets, msg=f"Broken guide link in {path.name}: {link}")
