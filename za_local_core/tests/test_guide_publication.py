"""Publishing the guides into Frappe Wiki, and taking them back out again.

Wiki is optional, so every path here has to stay safe when it is absent. When it
is present the contract is: publish is idempotent, an uninstall reclaims what
this suite published, and content someone else wrote is never destroyed.

The publishing and withdrawal cases live in separate classes on purpose.
``IntegrationTestCase`` rolls back once per class rather than per test, and a full
withdrawal cascades through tens of thousands of row writes, so keeping them in
one class walks into Frappe's per-transaction write ceiling.
"""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from za_local_core.practitioner_guide import stage
from za_local_core.practitioner_guide.registry import GUIDE_SPACES

PAGE = "sa-localisation-guides"
WORKSPACE = "SA Overview"


class GuideTestCase(IntegrationTestCase):
	def require_wiki(self):
		if not stage._wiki_installed():
			self.skipTest("Frappe Wiki is not installed on this site")

	def published_routes(self) -> set[str]:
		return self._published(is_group=0)

	def published_groups(self) -> set[str]:
		return self._published(is_group=1)

	def _published(self, is_group: int) -> set[str]:
		routes = set()
		for space in GUIDE_SPACES.values():
			routes |= set(
				frappe.get_all(
					stage.DOCUMENT_DOCTYPE,
					filters={"route": ("like", f"{space['route']}/%"), "is_group": is_group},
					pluck="route",
				)
			)
		return routes

	def other_contributor(self) -> str:
		"""A contributing app other than core, or core when it is the only one.

		Each app's CI installs only its own dependency chain, so the set of
		contributors differs between repositories.
		"""
		apps = set(stage.get_declared_pages().values())
		return sorted(apps - {"za_local_core"})[0] if apps - {"za_local_core"} else "za_local_core"

	def add_page_by_hand(self, group: str, slug: str) -> str:
		"""Publish a page this suite does not declare, and take it away afterwards.

		Rollback is per class, so a stray page left here would be visible to every
		later test in the same class.
		"""
		route = f"{group}/{slug}"
		stage._upsert_document(
			route=route,
			title=slug,
			parent=frappe.db.get_value(stage.DOCUMENT_DOCTYPE, {"route": group}, "name"),
			is_group=False,
			sort_order=99,
			content="written by hand",
		)
		self.addCleanup(stage._delete_pages, {route})
		return route


class TestGuideAvailability(GuideTestCase):
	"""Everything that holds whether or not Frappe Wiki is on the site."""

	def test_publishing_without_wiki_reports_instead_of_failing(self):
		with patch.object(stage, "_wiki_installed", return_value=False):
			self.assertIn("not installed", stage.stage_space())

	def test_withdrawing_without_wiki_is_a_safe_no_op(self):
		with patch.object(stage, "_wiki_installed", return_value=False):
			self.assertIn("nothing to withdraw", stage.unpublish_app_guide("za_local_core"))
			self.assertIn("nothing to withdraw", stage.unpublish_guides())

	def test_status_is_readable_without_wiki(self):
		with patch.object(stage, "_wiki_installed", return_value=False):
			status = stage.get_guide_status()
		self.assertFalse(status["wiki_installed"])
		self.assertEqual(len(stage.get_declared_pages()), status["declared"])
		self.assertTrue(all(not space["exists"] for space in status["spaces"]))

	def test_every_declared_page_is_attributed_to_an_installed_app(self):
		declared = stage.get_declared_pages()
		self.assertTrue(declared)
		self.assertLessEqual(set(declared.values()), set(frappe.get_installed_apps()))

	def test_the_desk_page_ships_and_is_reclaimed_by_module(self):
		"""Page has a module field, so ``remove_app`` takes it back on its own."""
		self.assertTrue(frappe.db.exists("Page", PAGE))
		self.assertEqual("SA Localisation Core", frappe.db.get_value("Page", PAGE, "module"))

	def test_the_workspace_offers_the_desk_page(self):
		workspace = frappe.get_doc("Workspace", WORKSPACE)
		links = [row for row in workspace.links if row.type == "Link" and row.link_type == "Page"]
		self.assertIn(PAGE, [row.link_to for row in links])


class TestGuidePublishing(GuideTestCase):
	def test_publish_creates_every_declared_page_and_records_provenance(self):
		self.require_wiki()
		stage.stage_space()
		declared = stage.get_declared_pages()
		self.assertEqual(set(), set(declared) - self.published_routes())
		self.assertEqual(declared, stage._read_inventory())

	def test_publishing_twice_changes_nothing(self):
		self.require_wiki()
		stage.stage_space()
		before = frappe.db.count(stage.DOCUMENT_DOCTYPE)
		stage.stage_space()
		self.assertEqual(before, frappe.db.count(stage.DOCUMENT_DOCTYPE))

	def test_republish_withdraws_a_page_no_installed_app_declares(self):
		self.require_wiki()
		stage.stage_space()
		route = self.add_page_by_hand(sorted(self.published_groups())[0], "_test-withdrawn")
		# Claim it as ours, which is what a renamed slug leaves behind.
		stage._write_inventory({**stage._read_inventory(), route: "za_local_core"})

		stage.stage_space()
		self.assertNotIn(route, self.published_routes())

	def test_republish_keeps_a_page_this_suite_did_not_publish(self):
		self.require_wiki()
		stage.stage_space()
		route = self.add_page_by_hand(sorted(self.published_groups())[0], "_test-hand-authored")

		stage.stage_space()
		self.assertIn(route, self.published_routes())

	def test_status_counts_what_is_published(self):
		self.require_wiki()
		stage.stage_space()
		declared = stage.get_declared_pages()
		status = stage.get_guide_status()
		self.assertTrue(status["wiki_installed"])
		self.assertEqual(len(declared), status["declared"])
		self.assertEqual(len(declared), sum(row["pages"] for row in status["contributors"]))
		for space in status["spaces"]:
			self.assertTrue(space["exists"], space["route"])
			self.assertTrue(space["is_published"], space["route"])
			self.assertEqual(space["declared"], space["published"], space["route"])


class TestGuideWithdrawal(GuideTestCase):
	def test_withdrawing_an_app_removes_only_its_own_pages_and_empty_groups(self):
		self.require_wiki()
		stage.stage_space()
		declared = stage.get_declared_pages()
		app = self.other_contributor()
		mine = {route for route, owner in declared.items() if owner == app}
		others = set(declared) - mine
		emptied = {
			group
			for group in {route.rsplit("/", 1)[0] for route in mine}
			# Only a group whose every page belonged to this app ends up empty.
			if all(declared[route] == app for route in declared if route.rsplit("/", 1)[0] == group)
		}

		stage.unpublish_app_guide(app)

		published = self.published_routes()
		self.assertEqual(set(), mine & published)
		self.assertEqual(others, others & published)
		self.assertEqual(set(), emptied & self.published_groups())
		self.assertNotIn(app, set(stage._read_inventory().values()))

	def test_uninstall_removes_the_spaces_this_suite_created(self):
		self.require_wiki()
		stage.stage_space()

		stage.unpublish_guides()

		self.assertEqual(set(), self.published_routes())
		for space in GUIDE_SPACES.values():
			self.assertFalse(frappe.db.exists(stage.SPACE_DOCTYPE, {"route": space["route"]}), space["route"])
		self.assertEqual({}, stage._read_inventory())

	def test_uninstall_keeps_a_space_holding_pages_this_suite_did_not_publish(self):
		"""Deleting a Wiki Space cascades to its whole tree, so this must not happen."""
		self.require_wiki()
		stage.stage_space()
		route = sorted(space["route"] for space in GUIDE_SPACES.values())[0]
		group = sorted(group for group in self.published_groups() if group.startswith(f"{route}/"))[0]
		kept = self.add_page_by_hand(group, "_test-hand-authored")
		ours = {page for page in stage.get_declared_pages() if page.startswith(f"{route}/")}

		summary = stage.unpublish_guides()

		self.assertTrue(frappe.db.exists(stage.SPACE_DOCTYPE, {"route": route}))
		published = self.published_routes()
		self.assertIn(kept, published)
		self.assertEqual(set(), ours & published)
		self.assertIn(route, summary)
