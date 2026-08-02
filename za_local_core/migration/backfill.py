"""Idempotent core governance backfills for fresh and upgraded sites."""

import json
from pathlib import Path

import frappe
from frappe.utils import getdate


def run() -> dict[str, int]:
	"""Seed controlled drafts without fabricating approval or overwriting user records."""
	return {
		"sources_created": seed_statutory_source_catalog(),
		"profiles_created": backfill_company_profiles(),
		"profiles_safened": safeguard_unapproved_profiles(),
	}


def seed_statutory_source_catalog() -> int:
	if not _doctype_ready("ZA Statutory Source", "catalog_key"):
		return 0
	created = 0
	for entry in _source_catalog():
		if frappe.db.exists("ZA Statutory Source", {"catalog_key": entry["catalog_key"]}):
			continue
		notes = entry["notes"]
		if reference_url := entry.get("reference_file_url"):
			notes = f"{notes}\nReference file: {reference_url}"
		doc = frappe.get_doc(
			{
				"doctype": "ZA Statutory Source",
				"catalog_key": entry["catalog_key"],
				"authority": entry["authority"],
				"title": entry["title"],
				"document_type": entry["document_type"],
				"version": entry["version"],
				"publication_date": entry["publication_date"],
				"effective_from": entry["effective_from"],
				"effective_to": entry.get("effective_to"),
				"source_url": entry["source_url"],
				"sha256_checksum": entry.get("reference_sha256"),
				"notes": notes,
				"status": "Draft",
			}
		)
		doc.insert(ignore_permissions=True)
		created += 1
	return created


def backfill_company_profiles() -> int:
	if not _doctype_ready("ZA Company Compliance Profile", "profile_key"):
		return 0
	company_meta = frappe.get_meta("Company")
	legacy_fields = {
		"vat_registered": "za_vat_number",
		"paye_registered": "za_paye_reference_number",
		"uif_registered": "za_uif_reference_number",
		"sdl_registered": "za_sdl_reference_number",
		"coida_registered": "za_coida_registration_number",
	}
	optional_values = {
		"seta": "za_seta",
		"bargaining_council": "za_bargaining_council",
	}
	query_fields = ["name", "creation"]
	query_fields.extend(field for field in legacy_fields.values() if company_meta.has_field(field))
	query_fields.extend(field for field in optional_values.values() if company_meta.has_field(field))
	created = 0
	for company in frappe.get_all(
		"Company", filters={"country": "South Africa"}, fields=query_fields, order_by="name"
	):
		if frappe.db.exists("ZA Company Compliance Profile", {"company": company.name}):
			continue
		effective_from = str(getdate(company.creation))
		profile = {
			"doctype": "ZA Company Compliance Profile",
			"profile_key": f"{company.name}|{effective_from}",
			"company": company.name,
			"effective_from": effective_from,
			"enabled": 0,
			"status": "Draft",
			"notes": (
				"Created by the za_local_core migration. Registration indicators were inferred only "
				"from populated legacy Company fields. Review against evidence before enabling."
			),
		}
		for target, source in legacy_fields.items():
			profile[target] = int(bool(company.get(source))) if company_meta.has_field(source) else 0
		for target, source in optional_values.items():
			profile[target] = company.get(source) if company_meta.has_field(source) else None
		frappe.get_doc(profile).insert(ignore_permissions=True)
		created += 1
	return created


def safeguard_unapproved_profiles() -> int:
	if not _doctype_ready("ZA Company Compliance Profile", "profile_key"):
		return 0
	updated = 0
	for row in frappe.get_all(
		"ZA Company Compliance Profile",
		filters={"docstatus": 0},
		fields=["name", "company", "effective_from", "profile_key", "enabled", "status"],
	):
		values = {}
		if not row.profile_key:
			values["profile_key"] = f"{row.company}|{getdate(row.effective_from)}"
		if row.enabled or row.status not in {None, "", "Draft", "Reviewed"}:
			values.update({"enabled": 0, "status": "Draft"})
		if values:
			frappe.db.set_value("ZA Company Compliance Profile", row.name, values, update_modified=False)
			updated += 1
	return updated


def _source_catalog() -> list[dict]:
	path = Path(frappe.get_app_path("za_local_core", "data", "statutory_source_catalog.json"))
	return json.loads(path.read_text(encoding="utf-8"))


def _doctype_ready(doctype: str, fieldname: str) -> bool:
	return frappe.db.exists("DocType", doctype) and frappe.get_meta(doctype).has_field(fieldname)
