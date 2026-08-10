"""Regression coverage for the shared South African Desk shell."""

from pathlib import Path

import frappe
from frappe.tests.classes import IntegrationTestCase, UnitTestCase

from za_local_core import hooks
from za_local_core.navigation import (
	APP_NAME,
	APP_ROUTE,
	APP_TITLE,
	LOCALISATION_APPS,
	WORKSPACE_SPECS,
	get_available_workspaces,
	sync_shared_navigation,
)

# The apps the suite currently ships. LOCALISATION_APPS is deliberately wider: it is
# a cleanup allow-list that still names the retired apps, so it cannot be used to
# assert that a workspace points at a live one.
CURRENT_SUITE_APPS = frozenset({"za_local_core", "za_local_payroll"})


class TestSharedNavigationContract(UnitTestCase):
	def test_required_runtime_apps_are_declared(self):
		self.assertEqual(set(hooks.required_apps), {"erpnext"})
		# frappe is always installed, so the marketplace review rejects it here.
		self.assertNotIn("frappe", hooks.required_apps)
		self.assertTrue(all(hooks.required_apps))
		self.assertEqual(len(hooks.required_apps), len(set(hooks.required_apps)))

	def test_core_is_the_only_apps_screen_owner(self):
		self.assertEqual("SA Localisation", hooks.app_title)
		self.assertEqual(APP_TITLE, hooks.add_to_apps_screen[0]["title"])
		self.assertEqual(APP_ROUTE, hooks.add_to_apps_screen[0]["route"])

		# Each app's CI checks out only its own dependency chain, so assert the
		# invariant for the sibling apps that are actually present on this bench.
		bench_apps = Path(frappe.get_app_path(APP_NAME)).parents[1]
		for app in sorted(LOCALISATION_APPS - {"za_local", APP_NAME}):
			hooks_path = bench_apps / app / app / "hooks.py"
			if not hooks_path.exists():
				continue
			self.assertNotIn("add_to_apps_screen", hooks_path.read_text(encoding="utf-8"))

	def test_every_workspace_is_attributed_to_an_app_that_ships_it(self):
		"""A workspace attributed to a retired app disappears from the Desk.

		``get_available_workspaces`` filters on ``spec.app in installed_apps`` and
		``_cleanup_stale_navigation`` then deletes the sidebar and desktop entries of
		anything it excluded. Naming an app that no longer exists therefore silently
		removes a workspace from navigation while leaving the Workspace record intact.
		"""
		bench_apps = Path(frappe.get_app_path(APP_NAME)).resolve().parents[1]
		for spec in WORKSPACE_SPECS:
			# A retired or misspelt app name must fail even on a bench that does not
			# carry it, so check the name against the suite before touching the disk.
			self.assertIn(
				spec.app, CURRENT_SUITE_APPS, f"{spec.label} names an app outside the suite: {spec.app}"
			)
			modules = bench_apps / spec.app / spec.app / "modules.txt"
			if not modules.is_file():
				# Each app's CI clones only its own dependency chain, so a sibling is
				# legitimately absent here. Its own CI asserts the rest.
				continue
			owning_module = frappe.db.get_value("Workspace", spec.label, "module")
			if owning_module:
				self.assertIn(
					owning_module,
					modules.read_text(encoding="utf-8").split("\n"),
					f"{spec.label} is attributed to {spec.app}, which does not declare {owning_module}",
				)

	def test_legacy_domain_icons_are_packaged_by_core(self):
		public = Path(frappe.get_app_path(APP_NAME, "public"))
		for spec in WORKSPACE_SPECS:
			filename = f"{frappe.scrub(spec.label)}.svg"
			self.assertTrue((public / "desktop_icons" / filename).is_file())
			solid = public / "icons" / "desktop_icons" / "solid" / filename
			subtle = public / "icons" / "desktop_icons" / "subtle" / filename
			self.assertTrue(solid.is_file())
			self.assertEqual(solid.read_bytes(), subtle.read_bytes())


class TestSharedNavigationSync(IntegrationTestCase):
	def test_installed_domains_share_one_app_icon_and_switcher(self):
		sync_shared_navigation()
		available = get_available_workspaces()
		labels = [spec.label for spec in available]

		app_icons = frappe.get_all(
			"Desktop Icon",
			filters={"icon_type": "App", "app": ["in", sorted(LOCALISATION_APPS)]},
			fields=["label", "app", "link", "logo_url"],
		)
		self.assertEqual(1, len(app_icons))
		self.assertEqual(APP_TITLE, app_icons[0].label)
		self.assertEqual(APP_NAME, app_icons[0].app)
		self.assertEqual(APP_ROUTE, app_icons[0].link)

		children = frappe.get_all(
			"Desktop Icon",
			filters={"parent_icon": APP_TITLE},
			fields=["label", "app", "link_type", "link_to", "hidden", "logo_url"],
			order_by="idx asc",
		)
		self.assertEqual(labels, [child.label for child in children])
		for child, spec in zip(children, available, strict=True):
			self.assertEqual(APP_NAME, child.app)
			self.assertEqual("Workspace Sidebar", child.link_type)
			self.assertEqual(child.label, child.link_to)
			self.assertEqual(0, child.hidden)
			self.assertEqual(spec.logo_url, child.logo_url)

		for label in labels:
			sidebar = frappe.get_doc("Workspace Sidebar", label)
			self.assertEqual(APP_NAME, sidebar.app)
			self.assertEqual(label, sidebar.items[0].link_to)
			self.assertEqual("Workspace", sidebar.items[0].link_type)
			self.assertGreater(len(sidebar.items), 1)

		for stale_label in (
			"SA Compliance",
			"SA Localisation Core",
			"SA Localisation Finance",
			"SA Localisation Payroll",
			"SA Localisation Workplace",
		):
			self.assertFalse(frappe.db.exists("Desktop Icon", stale_label))


class TestWorkspaceOnboarding(IntegrationTestCase):
	"""The sidebar is what surfaces a module's onboarding checklist in v16.

	Nothing set ``module_onboarding``, so every checklist these apps ship was
	unreachable from the Desk while still appearing in the Module Onboarding list.
	"""

	def test_every_installed_workspace_links_its_onboarding(self):
		sync_shared_navigation()
		for spec in get_available_workspaces():
			self.assertTrue(spec.onboarding, f"{spec.label} declares no onboarding")
			self.assertTrue(
				frappe.db.exists("Module Onboarding", spec.onboarding),
				f"{spec.label} names a Module Onboarding that is not installed: {spec.onboarding}",
			)
			self.assertEqual(
				spec.onboarding,
				frappe.db.get_value("Workspace Sidebar", spec.label, "module_onboarding"),
				f"{spec.label} sidebar does not link its onboarding",
			)

	def test_onboarding_steps_use_the_canonical_desk_route(self):
		"""v16 redirects /app/* to /desk/*, so a shipped /app/ path costs a round trip."""
		modules = [spec.onboarding for spec in get_available_workspaces()]
		steps = frappe.get_all("Onboarding Step Map", filters={"parent": ("in", modules)}, pluck="step")
		self.assertTrue(steps)
		for step in steps:
			path = frappe.db.get_value("Onboarding Step", step, "path") or ""
			self.assertFalse(path.startswith("/app/"), f"{step} uses the legacy /app/ route")

	def test_every_shipped_step_explains_itself(self):
		"""A checklist of bare titles is a list, not guidance."""
		modules = [spec.onboarding for spec in get_available_workspaces()]
		steps = frappe.get_all("Onboarding Step Map", filters={"parent": ("in", modules)}, pluck="step")
		undescribed = [
			step
			for step in steps
			if not (frappe.db.get_value("Onboarding Step", step, "description") or "").strip()
		]
		self.assertEqual([], undescribed)
