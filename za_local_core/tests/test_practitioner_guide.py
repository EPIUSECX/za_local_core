"""Regression tests for the federated practitioner and end-user guides."""

import re
from pathlib import Path

import frappe
from frappe.tests import UnitTestCase

from za_local_core.practitioner_guide.registry import PROVIDER_HOOK, get_guides

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

		# Each app's CI installs only its own dependency chain, so the contract is
		# "every installed contributor publishes pages", not a fixed list of four.
		contributors = {
			app for app in frappe.get_installed_apps() if frappe.get_hooks(PROVIDER_HOOK, app_name=app)
		}
		self.assertEqual(apps, contributors)
		self.assertIn("za_local_core", contributors)

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
				f"{group['key']}/{page['slug']}" for group in guide["groups"] for page in group["pages"]
			}
			# The guide is federated, so core's pages legitimately point into payroll's
			# sections. On a core-only bench those groups are absent entirely, and a
			# link into one cannot be checked here; payroll's own CI installs both and
			# does check it. A link into a group that IS present must still resolve, so
			# a wrong slug is still caught.
			present_groups = {group["key"] for group in guide["groups"]}
			for group in guide["groups"]:
				for page in group["pages"]:
					path = Path(
						frappe.get_app_path(page["app"], "practitioner_guide", "content", page["file"])
					)
					for link in RELATIVE_LINK.findall(path.read_text(encoding="utf-8")):
						clean = link.split("#", 1)[0].strip().rstrip("/")
						if not clean or clean.endswith((".png", ".jpg", ".jpeg", ".svg", ".pdf")):
							continue
						if clean.startswith("/"):
							self.assertIn(
								clean.lstrip("/"), all_routes, msg=f"Broken guide link in {path.name}: {link}"
							)
							continue
						target = clean[3:] if clean.startswith("../") else f"{group['key']}/{clean}"
						if target.split("/", 1)[0] not in present_groups:
							continue
						self.assertIn(target, targets, msg=f"Broken guide link in {path.name}: {link}")

	def test_the_first_declared_page_is_start_here(self):
		"""A guided path is only guided if the reader meets it first."""
		practitioner = next(g for g in get_guides() if g["space"]["route"] == "sa-guide")
		first_group = practitioner["groups"][0]
		self.assertEqual("getting-started", first_group["key"])
		self.assertEqual("start-here", first_group["pages"][0]["slug"])

	def test_published_order_never_uses_the_sort_order_wiki_treats_as_unset(self):
		"""Wiki Document.set_sort_order_for_new_document moves a record whose
		sort_order is 0 to the end of its siblings, treating 0 as "not set". A newly
		declared first page therefore sorted last in an already published group.

		Asserted against the source because the alternative is a live publish: the
		numbering is a property of the staging loop, and every value it can emit has
		to be non-zero, not just the ones a given site happens to exercise.
		"""
		from za_local_core.practitioner_guide import stage

		source = Path(stage.__file__).read_text(encoding="utf-8")
		enumerations = re.findall(r"enumerate\((?:guide\[\"groups\"\]|group\[\"pages\"\])[^)]*\)", source)

		self.assertEqual(2, len(enumerations), f"staging loop changed shape: {enumerations}")
		for enumeration in enumerations:
			self.assertIn("start=1", enumeration)
