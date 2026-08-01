"""Collect and validate guide contributions without importing downstream apps."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

import frappe

GUIDE_SPACES = {
	"practitioner": {"space_name": "SA Practitioner Guide", "route": "sa-guide"},
	"user": {"space_name": "SA End-User Guide", "route": "sa-user-guide"},
}
PROVIDER_HOOK = "za_local_practitioner_guide_provider"


def get_guides() -> list[dict]:
	"""Return merged guide definitions from installed localisation apps."""
	groups_by_guide = {guide: OrderedDict() for guide in GUIDE_SPACES}
	seen_routes = set()
	for app in frappe.get_installed_apps():
		for provider_path in frappe.get_hooks(PROVIDER_HOOK, app_name=app) or []:
			provider = frappe.get_attr(provider_path)
			for guide_key, groups in provider().items():
				if guide_key not in GUIDE_SPACES:
					raise ValueError(f"Unknown guide key {guide_key!r} from {provider_path}")
				for group in groups:
					group_key = group["key"]
					merged = groups_by_guide[guide_key].setdefault(
						group_key,
						{
							"key": group_key,
							"title": group["title"],
							"order": group.get("order", 100),
							"pages": [],
						},
					)
					for page in group.get("pages") or []:
						page = {**page, "app": app}
						route = f"{GUIDE_SPACES[guide_key]['route']}/{group_key}/{page['slug']}"
						if route in seen_routes:
							raise ValueError(f"Duplicate guide route: {route}")
						seen_routes.add(route)
						_validate_content_file(page)
						merged["pages"].append(page)

	guides = []
	for guide_key, space in GUIDE_SPACES.items():
		groups = sorted(groups_by_guide[guide_key].values(), key=lambda group: (group["order"], group["key"]))
		guides.append({"key": guide_key, "space": space, "groups": groups})
	return guides


def _validate_content_file(page: dict) -> None:
	path = frappe.get_app_path(page["app"], "practitioner_guide", "content", page["file"])
	if not Path(path).is_file():
		raise FileNotFoundError(f"Guide content file not found: {page['app']}:{page['file']}")
