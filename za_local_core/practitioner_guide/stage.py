"""Publish federated localisation documentation into optional Frappe Wiki spaces."""

import json
from pathlib import Path

import frappe
from frappe import _
from frappe.defaults import clear_default
from frappe.utils.nestedset import get_descendants_of

from za_local_core.practitioner_guide.registry import GUIDE_SPACES, get_guides

SPACE_DOCTYPE = "Wiki Space"
DOCUMENT_DOCTYPE = "Wiki Document"

# Route -> owning app for every page this suite has published.
#
# ``remove_app`` reclaims records by module, and neither Wiki DocType has a
# module field, so an uninstall cannot find published pages on its own. Recording
# provenance here is also what keeps withdrawal safe: only routes this suite put
# on the site are ever deleted, so a page someone hand-authored inside one of
# these spaces survives both a republish and an uninstall.
INVENTORY_KEY = "za_local_guide_inventory"


def _wiki_installed() -> bool:
	return bool(frappe.db.exists("DocType", SPACE_DOCTYPE) and frappe.db.exists("DocType", DOCUMENT_DOCTYPE))


def _read_page(page: dict) -> str:
	path = Path(frappe.get_app_path(page["app"], "practitioner_guide", "content", page["file"]))
	return path.read_text(encoding="utf-8")


def get_declared_pages() -> dict[str, str]:
	"""Route -> owning app for every page the installed apps currently declare."""
	declared = {}
	for guide in get_guides():
		for group in guide["groups"]:
			for page in group["pages"]:
				declared[f"{guide['space']['route']}/{group['key']}/{page['slug']}"] = page["app"]
	return declared


def _read_inventory() -> dict[str, str]:
	raw = frappe.db.get_global(INVENTORY_KEY)
	if not raw:
		return {}
	try:
		inventory = json.loads(raw)
	except ValueError:
		return {}
	return inventory if isinstance(inventory, dict) else {}


def _write_inventory(inventory: dict[str, str]) -> None:
	frappe.db.set_global(INVENTORY_KEY, json.dumps(inventory, sort_keys=True))


def _get_managed_root_groups() -> dict[str, str]:
	"""Space route -> root group, for the spaces this suite publishes into."""
	roots = {}
	for space in GUIDE_SPACES.values():
		root = frappe.db.get_value(SPACE_DOCTYPE, {"route": space["route"]}, "root_group")
		if root:
			roots[space["route"]] = root
	return roots


def _get_or_create_space(definition: dict):
	name = frappe.db.get_value(SPACE_DOCTYPE, {"route": definition["route"]}, "name")
	space = frappe.get_doc(SPACE_DOCTYPE, name) if name else frappe.new_doc(SPACE_DOCTYPE)
	space.space_name = definition["space_name"]
	space.route = definition["route"]
	space.is_published = 1
	space.show_in_switcher = 1
	if space.is_new():
		space.insert(ignore_permissions=True)
	else:
		space.save(ignore_permissions=True)
	if not space.root_group:
		space.create_root_group()
		space.save(ignore_permissions=True)
	return space


def _upsert_document(*, route, title, parent, is_group, sort_order, content=None):
	name = frappe.db.get_value(DOCUMENT_DOCTYPE, {"route": route}, "name")
	doc = frappe.get_doc(DOCUMENT_DOCTYPE, name) if name else frappe.new_doc(DOCUMENT_DOCTYPE)
	doc.route = route
	doc.title = title
	doc.parent_wiki_document = parent
	doc.is_group = int(is_group)
	doc.is_published = 1
	doc.sort_order = sort_order
	if content is not None:
		doc.content = content
	if doc.is_new():
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)
	return doc.name


def _delete_documents(names) -> int:
	"""Delete deepest first.

	Wiki Document is a nested set and refuses to drop a group that still has
	children, so ordering by descending ``lft`` is what makes a bulk delete work.
	"""
	if not names:
		return 0
	ordered = frappe.get_all(
		DOCUMENT_DOCTYPE, filters={"name": ("in", list(names))}, pluck="name", order_by="lft desc"
	)
	for name in ordered:
		frappe.delete_doc(DOCUMENT_DOCTYPE, name, force=True, ignore_permissions=True)
	return len(ordered)


def _delete_pages(routes) -> int:
	"""Delete the leaf pages at these routes. Wiki keeps leaf routes unique."""
	if not routes:
		return 0
	names = frappe.get_all(
		DOCUMENT_DOCTYPE, filters={"route": ("in", list(routes)), "is_group": 0}, pluck="name"
	)
	return _delete_documents(names)


def _prune_empty_groups() -> int:
	"""Drop groups inside the managed spaces that have nothing left in them.

	Emptiness is the only signal used. A group a provider still declares is
	recreated by the next publish, and one nobody declares has nothing to show.
	Root groups belong to the space rather than to a provider, so they stay.
	"""
	roots = _get_managed_root_groups()
	removed = 0
	while True:
		empty = []
		for root in roots.values():
			descendants = get_descendants_of(DOCUMENT_DOCTYPE, root, ignore_permissions=True)
			if not descendants:
				continue
			groups = frappe.get_all(
				DOCUMENT_DOCTYPE,
				filters={"name": ("in", descendants), "is_group": 1},
				pluck="name",
				order_by="lft desc",
			)
			empty += [
				name
				for name in groups
				if not frappe.db.exists(DOCUMENT_DOCTYPE, {"parent_wiki_document": name})
			]
		if not empty:
			return removed
		removed += _delete_documents(empty)


def stage_space() -> str:
	"""Idempotently publish every installed app's guide contribution."""
	if not _wiki_installed():
		return "Frappe Wiki is not installed; repository documentation remains available."

	summaries = []
	for guide in get_guides():
		space = _get_or_create_space(guide["space"])
		page_count = 0
		for group_index, group in enumerate(guide["groups"]):
			group_route = f"{guide['space']['route']}/{group['key']}"
			group_name = _upsert_document(
				route=group_route,
				title=group["title"],
				parent=space.root_group,
				is_group=True,
				sort_order=group_index,
			)
			for page_index, page in enumerate(group["pages"]):
				_upsert_document(
					route=f"{group_route}/{page['slug']}",
					title=page["title"],
					parent=group_name,
					is_group=False,
					sort_order=page_index,
					content=_read_page(page),
				)
				page_count += 1
		summaries.append(f"{guide['space']['space_name']}: {page_count} pages")

	declared = get_declared_pages()
	withdrawn = _delete_pages(set(_read_inventory()) - set(declared))
	if withdrawn:
		_prune_empty_groups()
		summaries.append(f"withdrawn: {withdrawn} pages no longer declared")
	_write_inventory(declared)
	return "; ".join(summaries)


def unpublish_app_guide(app: str) -> str:
	"""Withdraw one app's published pages, for that app's ``before_uninstall``.

	Without this the pages stay live and reachable after the app that wrote them
	is gone, because Frappe has no module link to reclaim them by.
	"""
	if not _wiki_installed():
		return "Frappe Wiki is not installed; nothing to withdraw."

	inventory = _read_inventory()
	routes = {route for route, owner in inventory.items() if owner == app}
	if not routes:
		# Published before the inventory existed, or never published at all.
		routes = {route for route, owner in get_declared_pages().items() if owner == app}

	pages = _delete_pages(routes)
	groups = _prune_empty_groups()
	_write_inventory({route: owner for route, owner in inventory.items() if owner != app})
	return f"Withdrew {pages} pages and {groups} empty groups published by {app}."


def _get_foreign_pages(root: str, ours: set[str]) -> list[str]:
	"""Leaf pages under this root that this suite did not publish."""
	descendants = get_descendants_of(DOCUMENT_DOCTYPE, root, ignore_permissions=True)
	if not descendants:
		return []
	return [
		route
		for route in frappe.get_all(
			DOCUMENT_DOCTYPE, filters={"name": ("in", descendants), "is_group": 0}, pluck="route"
		)
		if route not in ours
	]


def unpublish_guides() -> str:
	"""Withdraw everything this suite published and drop the spaces it created.

	Deleting a Wiki Space cascades to its whole tree, which is both the cheap way
	to do this and the reason a space holding pages this suite did not publish is
	emptied of ours and then kept: an uninstall must not take someone else's
	documentation with it.
	"""
	if not _wiki_installed():
		clear_default(key=INVENTORY_KEY, parent="__global")
		return "Frappe Wiki is not installed; nothing to withdraw."

	ours = set(_read_inventory()) or set(get_declared_pages())
	dropped, retained, pages = [], [], 0
	for route, root in _get_managed_root_groups().items():
		if _get_foreign_pages(root, ours):
			pages += _delete_pages({page for page in ours if page.startswith(f"{route}/")})
			retained.append(route)
			continue
		space = frappe.db.get_value(SPACE_DOCTYPE, {"route": route}, "name")
		frappe.delete_doc(SPACE_DOCTYPE, space, force=True, ignore_permissions=True)
		dropped.append(route)

	groups = _prune_empty_groups() if retained else 0
	clear_default(key=INVENTORY_KEY, parent="__global")
	summary = f"Removed spaces: {', '.join(dropped) or 'none'}"
	if retained:
		summary += (
			f"; kept {', '.join(retained)} after withdrawing {pages} pages and {groups} empty groups"
			" (holds pages this suite did not publish)"
		)
	return summary


@frappe.whitelist(methods=["GET"])
def is_wiki_available() -> bool:
	return _wiki_installed()


@frappe.whitelist(methods=["GET"])
def get_guide_status() -> dict:
	"""Describe publication state without changing it, for the Desk page."""
	frappe.only_for("System Manager")
	declared = get_declared_pages()
	contributors = {}
	for app in declared.values():
		contributors[app] = contributors.get(app, 0) + 1

	status = {
		"wiki_installed": _wiki_installed(),
		"declared": len(declared),
		"contributors": [{"app": app, "pages": count} for app, count in sorted(contributors.items())],
		"spaces": [],
	}
	for space in GUIDE_SPACES.values():
		row = None
		published = 0
		if status["wiki_installed"]:
			row = frappe.db.get_value(
				SPACE_DOCTYPE, {"route": space["route"]}, ["name", "is_published"], as_dict=True
			)
			published = frappe.db.count(
				DOCUMENT_DOCTYPE, {"route": ("like", f"{space['route']}/%"), "is_group": 0}
			)
		status["spaces"].append(
			{
				"space_name": space["space_name"],
				"route": space["route"],
				"exists": bool(row),
				"is_published": bool(row and row.is_published),
				"declared": len([route for route in declared if route.startswith(f"{space['route']}/")]),
				"published": published,
			}
		)
	return status


@frappe.whitelist(methods=["POST"])
def publish_practitioner_guide() -> dict:
	"""Queue site-wide guide publication on the long queue."""
	frappe.only_for("System Manager")
	if not _wiki_installed():
		return {
			"title": _("Wiki Not Installed"),
			"indicator": "orange",
			"message": _("Install Frappe Wiki before publishing the on-site guides."),
		}
	job = frappe.enqueue(
		"za_local_core.practitioner_guide.stage.stage_space",
		queue="long",
		job_id=f"za-local-guides::{frappe.local.site}",
		deduplicate=True,
	)
	return {
		"title": _("Documentation Publication Queued"),
		"indicator": "blue",
		"message": _("The practitioner and end-user guides are being refreshed."),
		"job_id": job.id,
	}
