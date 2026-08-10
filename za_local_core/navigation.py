"""Shared Frappe Desk navigation for the South African localisation suite."""

from __future__ import annotations

import json
from dataclasses import dataclass

import frappe

APP_NAME = "za_local_core"
APP_TITLE = "SA Localisation"
APP_ROUTE = "/desk/sa-overview"
APP_LOGO = "/assets/za_local_core/images/sa_map_icon.png"

# Every app name the suite has ever shipped under, including retired ones. This is
# a cleanup allow-list, not a dependency list: a site that once had a retired app
# installed still carries its Desktop Icon, and only a name listed here is removed.
LOCALISATION_APPS = {
	"za_local",
	"za_local_core",
	"za_local_finance",
	"za_local_payroll",
	"za_local_workplace",
}

STALE_APP_LABELS = {
	"SA Localisation Core",
	"SA Localisation Finance",
	"SA Localisation Payroll",
	"SA Localisation Workplace",
}


@dataclass(frozen=True)
class WorkspaceSpec:
	label: str
	app: str
	icon: str
	asset_name: str
	onboarding: str

	@property
	def logo_url(self) -> str:
		return f"/assets/{APP_NAME}/desktop_icons/{self.asset_name}"


WORKSPACE_SPECS = (
	WorkspaceSpec(
		"SA Overview", "za_local_core", "shield-check", "sa_overview.svg", "SA Localisation Onboarding"
	),
	WorkspaceSpec("SA Payroll", "za_local_payroll", "accounting", "sa_payroll.svg", "SA Payroll Onboarding"),
	WorkspaceSpec("SA VAT", "za_local_core", "sell", "sa_vat.svg", "SA VAT Onboarding"),
	WorkspaceSpec("SA Labour", "za_local_payroll", "hr", "sa_labour.svg", "SA Labour Onboarding"),
	WorkspaceSpec("SA COIDA", "za_local_payroll", "support", "sa_coida.svg", "SA COIDA Onboarding"),
)


def sync_shared_navigation() -> None:
	"""Expose installed localisation domains through one shared Desk app."""
	if not _navigation_schema_available():
		return

	available = get_available_workspaces()
	_cleanup_stale_navigation(available)
	for spec in available:
		_sync_workspace_sidebar(spec)
	_sync_desktop_icons(available)
	_repair_saved_desktop_layouts(available)
	_clear_navigation_cache()


def get_available_workspaces() -> tuple[WorkspaceSpec, ...]:
	"""Return installed domain workspaces in their stable display order."""
	installed_apps = set(frappe.get_installed_apps() or ())
	return tuple(
		spec
		for spec in WORKSPACE_SPECS
		if spec.app in installed_apps and frappe.db.exists("Workspace", spec.label)
	)


def _navigation_schema_available() -> bool:
	return all(
		frappe.db.table_exists(doctype)
		for doctype in ("Desktop Icon", "Workspace Sidebar", "Workspace Sidebar Item")
	)


def _cleanup_stale_navigation(available: tuple[WorkspaceSpec, ...]) -> None:
	available_labels = {spec.label for spec in available}
	all_workspace_labels = {spec.label for spec in WORKSPACE_SPECS}

	for label in all_workspace_labels - available_labels:
		_delete_exact("Desktop Icon", label)
		_delete_exact("Workspace Sidebar", label)

	for label in STALE_APP_LABELS | {"SA Compliance"}:
		_delete_exact("Desktop Icon", label)
	if "SA Overview" in available_labels:
		_delete_exact("Workspace Sidebar", "SA Compliance")

	for icon in frappe.get_all(
		"Desktop Icon",
		filters={"icon_type": "App", "app": ["in", sorted(LOCALISATION_APPS)]},
		fields=["name", "label", "app"],
	):
		if icon.label == APP_TITLE and icon.app == APP_NAME:
			continue
		_delete_exact("Desktop Icon", icon.name)


def _sync_workspace_sidebar(spec: WorkspaceSpec) -> None:
	workspace = frappe.get_doc("Workspace", spec.label)
	if frappe.db.exists("Workspace Sidebar", spec.label):
		sidebar = frappe.get_doc("Workspace Sidebar", spec.label)
	else:
		sidebar = frappe.new_doc("Workspace Sidebar")
		sidebar.title = spec.label

	sidebar.app = APP_NAME
	sidebar.module = workspace.module
	sidebar.header_icon = workspace.icon or spec.icon
	sidebar.standard = 0
	# The sidebar is what surfaces a module's onboarding checklist in v16. Nothing
	# ever set the link, so every checklist these apps ship was unreachable from the
	# Desk. Clear it when the record is absent rather than point at a missing name.
	if sidebar.meta.has_field("module_onboarding"):
		sidebar.module_onboarding = (
			spec.onboarding if frappe.db.exists("Module Onboarding", spec.onboarding) else None
		)
	sidebar.set("items", [])
	for row in _build_sidebar_rows(workspace):
		sidebar.append("items", row)

	if sidebar.is_new():
		sidebar.insert(ignore_permissions=True)
	else:
		sidebar.save(ignore_permissions=True)


def _build_sidebar_rows(workspace) -> list[dict]:
	rows = [
		{
			"label": "Home",
			"type": "Link",
			"link_type": "Workspace",
			"link_to": workspace.name,
			"icon": "home",
		}
	]
	seen_links = {("Workspace", workspace.name)}

	quick_access = []
	for shortcut in workspace.get("shortcuts", []):
		link_type = shortcut.type
		link_to = shortcut.link_to
		if not _valid_sidebar_link(link_type, link_to) or (link_type, link_to) in seen_links:
			continue
		quick_access.append(
			{
				"label": shortcut.label or link_to,
				"type": "Link",
				"link_type": link_type,
				"link_to": link_to,
				"child": 1,
			}
		)
		seen_links.add((link_type, link_to))
	if quick_access:
		rows.append(_section_row("Quick access", "zap"))
		rows.extend(quick_access)

	pending_section = None
	for link in workspace.get("links", []):
		if link.type == "Card Break":
			pending_section = link.label
			continue
		if link.type != "Link" or not _valid_sidebar_link(link.link_type, link.link_to):
			continue
		key = (link.link_type, link.link_to)
		if key in seen_links:
			continue
		if pending_section:
			rows.append(_section_row(pending_section, "list"))
			pending_section = None
		rows.append(
			{
				"label": link.label or link.link_to,
				"type": "Link",
				"link_type": link.link_type,
				"link_to": link.link_to,
				"child": 1,
			}
		)
		seen_links.add(key)

	return rows


def _section_row(label: str, icon: str) -> dict:
	return {
		"label": label,
		"type": "Section Break",
		"icon": icon,
		"indent": 1,
		"collapsible": 1,
		"keep_closed": 1,
	}


def _valid_sidebar_link(link_type: str | None, link_to: str | None) -> bool:
	if not link_type or not link_to:
		return False
	if link_type == "URL":
		return True
	if link_type not in {"Dashboard", "DocType", "Page", "Report", "Workspace"}:
		return False
	return bool(frappe.db.exists(link_type, link_to))


def _sync_desktop_icons(available: tuple[WorkspaceSpec, ...]) -> None:
	app_icon = _get_or_create_app_icon()
	app_icon.update(
		{
			"label": APP_TITLE,
			"icon_type": "App",
			"link_type": "External",
			"link": APP_ROUTE,
			"logo_url": APP_LOGO,
			"app": APP_NAME,
			"hidden": 0,
			"standard": 0,
		}
	)
	_save_icon(app_icon)

	for index, spec in enumerate(available):
		if frappe.db.exists("Desktop Icon", spec.label):
			icon = frappe.get_doc("Desktop Icon", spec.label)
		else:
			icon = frappe.new_doc("Desktop Icon")
			icon.label = spec.label
		icon.update(
			{
				"icon_type": "Link",
				"link_type": "Workspace Sidebar",
				"link_to": spec.label,
				"link": "",
				"icon": spec.icon,
				"app": APP_NAME,
				"parent_icon": APP_TITLE,
				"hidden": 0,
				"standard": 0,
				"idx": index,
				"logo_url": spec.logo_url,
				"icon_image": "",
			}
		)
		_save_icon(icon)


def _get_or_create_app_icon():
	name = frappe.db.get_value("Desktop Icon", {"icon_type": "App", "app": APP_NAME}, "name")
	if name:
		return frappe.get_doc("Desktop Icon", name)
	if frappe.db.exists("Desktop Icon", APP_TITLE):
		return frappe.get_doc("Desktop Icon", APP_TITLE)
	icon = frappe.new_doc("Desktop Icon")
	icon.label = APP_TITLE
	return icon


def _save_icon(icon) -> None:
	if icon.is_new():
		icon.insert(ignore_permissions=True)
	else:
		icon.save(ignore_permissions=True)


def _repair_saved_desktop_layouts(available: tuple[WorkspaceSpec, ...]) -> None:
	if not frappe.db.table_exists("Desktop Layout"):
		return

	desired_labels = [APP_TITLE, *(spec.label for spec in available)]
	desired_icons = {
		row.label: dict(row)
		for row in frappe.get_all(
			"Desktop Icon",
			filters={"label": ["in", desired_labels]},
			fields=[
				"name",
				"label",
				"bg_color",
				"link",
				"link_type",
				"app",
				"icon_type",
				"parent_icon",
				"icon",
				"link_to",
				"idx",
				"standard",
				"logo_url",
				"hidden",
				"restrict_removal",
				"icon_image",
			],
		)
	}
	if APP_TITLE not in desired_icons:
		return

	relevant_labels = set(desired_labels) | STALE_APP_LABELS | {"SA Compliance"}
	for saved in frappe.get_all("Desktop Layout", fields=["name", "layout"]):
		try:
			layout = json.loads(saved.layout or "[]")
		except (TypeError, ValueError):
			continue
		if not isinstance(layout, list) or not any(
			isinstance(icon, dict) and icon.get("label") in relevant_labels for icon in layout
		):
			continue

		first_index = next(
			index
			for index, icon in enumerate(layout)
			if isinstance(icon, dict) and icon.get("label") in relevant_labels
		)
		cleaned = [
			icon for icon in layout if not (isinstance(icon, dict) and icon.get("label") in relevant_labels)
		]
		for offset, label in enumerate(desired_labels):
			cleaned.insert(first_index + offset, desired_icons[label])
		frappe.db.set_value(
			"Desktop Layout",
			saved.name,
			"layout",
			json.dumps(cleaned),
			update_modified=False,
		)


def _delete_exact(doctype: str, name: str) -> None:
	if frappe.db.exists(doctype, name):
		frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)


def _clear_navigation_cache() -> None:
	frappe.cache.delete_key("desktop_icons")
	frappe.cache.delete_key("bootinfo")
	frappe.clear_cache()
