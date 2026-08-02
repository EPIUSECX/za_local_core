"""Publish federated localisation documentation into optional Frappe Wiki spaces."""

from pathlib import Path

import frappe
from frappe import _

from za_local_core.practitioner_guide.registry import get_guides


def _wiki_installed() -> bool:
	return bool(frappe.db.exists("DocType", "Wiki Space") and frappe.db.exists("DocType", "Wiki Document"))


def _read_page(page: dict) -> str:
	path = Path(frappe.get_app_path(page["app"], "practitioner_guide", "content", page["file"]))
	return path.read_text(encoding="utf-8")


def _get_or_create_space(definition: dict):
	name = frappe.db.get_value("Wiki Space", {"route": definition["route"]}, "name")
	space = frappe.get_doc("Wiki Space", name) if name else frappe.new_doc("Wiki Space")
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
	name = frappe.db.get_value("Wiki Document", {"route": route}, "name")
	doc = frappe.get_doc("Wiki Document", name) if name else frappe.new_doc("Wiki Document")
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
	return "; ".join(summaries)


@frappe.whitelist(methods=["GET"])
def is_wiki_available() -> bool:
	return _wiki_installed()


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
