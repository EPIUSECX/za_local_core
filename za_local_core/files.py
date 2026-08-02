"""Safe access to packaged resources owned by an installed app."""

from pathlib import Path

import frappe
from frappe import _


def resolve_packaged_path(app_name: str, *parts: str) -> Path:
	"""Resolve a packaged path and reject traversal outside the named app."""
	if not isinstance(app_name, str) or not app_name or "/" in app_name or "\\" in app_name:
		raise TypeError("app_name must be a simple non-empty string")
	app_root = Path(frappe.get_app_path(app_name)).resolve()
	path = app_root.joinpath(*(str(part) for part in parts)).resolve()
	_validate_child(path, app_root)
	return path


def ensure_packaged_path(app_name: str, path: str | Path) -> Path:
	"""Confirm an existing path belongs to the named installed app."""
	app_root = Path(frappe.get_app_path(app_name)).resolve()
	resolved_path = Path(path).resolve()
	_validate_child(resolved_path, app_root)
	return resolved_path


def read_packaged_json(app_name: str, path_or_first_part: str | Path, *parts: str):
	"""Read packaged JSON after validating the target path."""
	path = _resolve_argument(app_name, path_or_first_part, parts)
	return frappe.get_file_json(str(path))


def read_packaged_text(app_name: str, path_or_first_part: str | Path, *parts: str) -> str:
	"""Read packaged text after validating the target path."""
	path = _resolve_argument(app_name, path_or_first_part, parts)
	return frappe.read_file(str(path), raise_not_found=True)


def _resolve_argument(app_name: str, first: str | Path, parts: tuple[str, ...]) -> Path:
	if parts:
		return resolve_packaged_path(app_name, str(first), *parts)
	path = Path(first)
	return (
		ensure_packaged_path(app_name, path)
		if path.is_absolute()
		else resolve_packaged_path(app_name, str(path))
	)


def _validate_child(path: Path, app_root: Path) -> None:
	try:
		path.relative_to(app_root)
	except ValueError:
		frappe.throw(_("Invalid packaged file path: {0}").format(path.name))
