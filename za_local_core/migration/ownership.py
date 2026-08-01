"""Classify every legacy source artifact by its target application."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Ownership:
	owner: str
	reason: str


@dataclass(frozen=True)
class Artifact:
	path: str
	sha256: str
	owner: str
	reason: str


_PREFIX_RULES = (
	("za_local/accounts/", Ownership("za_local_finance", "South African accounting setup")),
	("za_local/sa_vat/", Ownership("za_local_finance", "VAT domain")),
	("za_local/custom/", Ownership("za_local_finance", "Finance master and transaction extensions")),
	("za_local/sa_payroll/", Ownership("za_local_payroll", "Payroll domain")),
	("za_local/sa_labour/", Ownership("za_local_workplace", "Labour and skills domain")),
	("za_local/sa_coida/", Ownership("za_local_workplace", "COIDA and injury domain")),
	("za_local/sa_localisation/", Ownership("za_local_core", "Shared localisation module")),
	("za_local/api/", Ownership("za_local_core", "Shared application APIs")),
)

_EXACT_RULES = {
	"za_local/overrides/vat_invoices.py": Ownership("za_local_finance", "VAT transaction extension"),
	"za_local/utils/vat_utils.py": Ownership("za_local_finance", "VAT services"),
	"za_local/public/js/vat_tax_calculation.js": Ownership("za_local_finance", "VAT client behaviour"),
	"za_local/overrides/salary_slip.py": Ownership("za_local_payroll", "Salary Slip calculation"),
	"za_local/overrides/payroll_entry.py": Ownership("za_local_payroll", "Payroll Entry workflow"),
	"za_local/overrides/additional_salary.py": Ownership("za_local_payroll", "Additional Salary extension"),
	"za_local/overrides/salary_structure_assignment.py": Ownership(
		"za_local_payroll", "Salary Structure Assignment extension"
	),
	"za_local/overrides/journal_entry.py": Ownership("za_local_payroll", "Payroll journal controls"),
	"za_local/utils/payroll_utils.py": Ownership("za_local_payroll", "Payroll services"),
	"za_local/utils/tax_utils.py": Ownership("za_local_payroll", "PAYE services"),
	"za_local/utils/statutory_rates.py": Ownership("za_local_payroll", "Legacy payroll rate resolver"),
	"za_local/utils/eti_utils.py": Ownership("za_local_payroll", "ETI services"),
	"za_local/utils/emp501_utils.py": Ownership("za_local_payroll", "EMP501 services"),
	"za_local/utils/lump_sum_tax_utils.py": Ownership("za_local_payroll", "Lump-sum tax services"),
	"za_local/utils/fringe_benefit_utils.py": Ownership("za_local_payroll", "Fringe-benefit services"),
	"za_local/utils/travel_allowance_utils.py": Ownership("za_local_payroll", "Travel allowance tax services"),
	"za_local/utils/sars_xml_generator.py": Ownership("za_local_payroll", "Payroll statutory export"),
	"za_local/utils/integrations/eft_generator.py": Ownership("za_local_payroll", "Payroll payment export"),
	"za_local/overrides/leave_application.py": Ownership("za_local_workplace", "BCEA leave rules"),
	"za_local/overrides/employee_separation.py": Ownership("za_local_workplace", "Termination entitlement"),
	"za_local/utils/coida_utils.py": Ownership("za_local_workplace", "COIDA services"),
	"za_local/utils/termination_utils.py": Ownership("za_local_workplace", "Termination entitlement services"),
	"za_local/utils/file_utils.py": Ownership("za_local_core", "Shared safe resource access"),
	"za_local/utils/setup_utils.py": Ownership("za_local_core", "Shared setup services"),
	"za_local/utils/hooks_utils.py": Ownership("za_local_core", "Compatibility hook composition"),
	"za_local/utils/hrms_detection.py": Ownership("za_local_core", "Installed-app detection"),
	"za_local/public/js/za_local_feedback.js": Ownership("za_local_core", "Shared Desk feedback"),
	"za_local/practitioner_guide/manifest.py": Ownership("za_local_core", "Guide registry"),
	"za_local/practitioner_guide/stage.py": Ownership("za_local_core", "Guide publication service"),
}


def classify_path(path: str) -> Ownership:
	"""Return the target owner for one tracked legacy path."""
	if exact := _EXACT_RULES.get(path):
		return exact

	for prefix, ownership in _PREFIX_RULES:
		if path.startswith(prefix):
			return ownership

	if path.startswith("za_local/tests/"):
		return _classify_test(path)

	if path.startswith("za_local/practitioner_guide/content/") or path.startswith("docs/"):
		return _classify_documentation(path)

	if path.startswith("za_local/sa_setup/"):
		return Ownership("migration_split", "Split by fixture/record ownership before compatibility retirement")

	if path.startswith(("za_local/public/", "za_local/templates/", "za_local/config/")):
		return Ownership("migration_split", "Split by domain before compatibility retirement")

	return Ownership("za_local_compatibility", "Temporary compatibility or repository-level artifact")


def build_manifest(legacy_repo: Path) -> dict:
	"""Build a deterministic manifest for all tracked files in the legacy repository."""
	paths = _tracked_paths(legacy_repo)
	artifacts = []
	for relative_path in paths:
		ownership = classify_path(relative_path)
		artifacts.append(
			Artifact(
				path=relative_path,
				sha256=_sha256(legacy_repo / relative_path),
				owner=ownership.owner,
				reason=ownership.reason,
			)
		)

	owner_counts: dict[str, int] = {}
	for artifact in artifacts:
		owner_counts[artifact.owner] = owner_counts.get(artifact.owner, 0) + 1

	return {
		"schema_version": 1,
		"legacy_app": "za_local",
		"artifact_count": len(artifacts),
		"owner_counts": dict(sorted(owner_counts.items())),
		"artifacts": [asdict(artifact) for artifact in artifacts],
	}


def write_manifest(legacy_repo: Path, output_path: Path) -> None:
	"""Write the ownership manifest with stable ordering and formatting."""
	manifest = build_manifest(legacy_repo.resolve())
	output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def _tracked_paths(repo: Path) -> list[str]:
	result = subprocess.run(
		["git", "-C", str(repo), "ls-files", "-z"],
		check=True,
		capture_output=True,
	)
	return sorted(path for path in result.stdout.decode().split("\0") if path)


def _sha256(path: Path) -> str:
	hash_value = hashlib.sha256()
	with path.open("rb") as source:
		for block in iter(lambda: source.read(1024 * 1024), b""):
			hash_value.update(block)
	return hash_value.hexdigest()


def _classify_test(path: str) -> Ownership:
	name = Path(path).name
	if any(token in name for token in ("vat",)):
		return Ownership("za_local_finance", "Finance regression test")
	if any(token in name for token in ("payroll", "tax", "irp5", "sars", "fringe")):
		return Ownership("za_local_payroll", "Payroll regression test")
	if any(token in name for token in ("coida", "labour")):
		return Ownership("za_local_workplace", "Workplace regression test")
	return Ownership("za_local_core", "Cross-domain or shared regression test")


def _classify_documentation(path: str) -> Ownership:
	lower_path = path.lower()
	if "vat" in lower_path or "finance" in lower_path:
		return Ownership("za_local_finance", "Finance practitioner content")
	if any(token in lower_path for token in ("payroll", "paye", "irp5", "eti", "sars")):
		return Ownership("za_local_payroll", "Payroll practitioner content")
	if any(token in lower_path for token in ("coida", "labour", "employment", "skills")):
		return Ownership("za_local_workplace", "Workplace practitioner content")
	return Ownership("za_local_core", "Shared practitioner content")
