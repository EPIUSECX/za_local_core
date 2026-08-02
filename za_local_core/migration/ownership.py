"""Classify every legacy source artifact by its target application."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

ALLOWED_OWNERS = frozenset(
	{
		"za_local_compatibility",
		"za_local_core",
		"za_local_finance",
		"za_local_payroll",
		"za_local_workplace",
	}
)
MANIFEST_SCHEMA_VERSION = 2
TARGET_APPS = ("za_local_core", "za_local_finance", "za_local_payroll", "za_local_workplace")


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
	"za_local/utils/travel_allowance_utils.py": Ownership(
		"za_local_payroll", "Travel allowance tax services"
	),
	"za_local/utils/sars_xml_generator.py": Ownership("za_local_payroll", "Payroll statutory export"),
	"za_local/utils/integrations/eft_generator.py": Ownership("za_local_payroll", "Payroll payment export"),
	"za_local/overrides/leave_application.py": Ownership("za_local_workplace", "BCEA leave rules"),
	"za_local/overrides/employee_separation.py": Ownership("za_local_workplace", "Termination entitlement"),
	"za_local/utils/coida_utils.py": Ownership("za_local_workplace", "COIDA services"),
	"za_local/utils/termination_utils.py": Ownership(
		"za_local_workplace", "Termination entitlement services"
	),
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
		return _classify_setup(path)

	if path.startswith("za_local/public/"):
		return _classify_public_asset(path)

	if path.startswith("za_local/templates/"):
		return _classify_template(path)

	if path.startswith("za_local/config/"):
		return _classify_config(path)

	if path.startswith(("za_local/desktop_icon/", "za_local/workspace_sidebar/")):
		return _classify_public_asset(path)

	if path.startswith("za_local/legacy_standard_docs/"):
		return Ownership("za_local_finance", "Retired finance print-format source")

	if path.startswith("za_local/data/"):
		return Ownership("za_local_workplace", "Workplace reference data")

	if path.startswith("za_local/patches/"):
		if any(token in path.lower() for token in ("emp201", "statutory_tax")):
			return Ownership("za_local_payroll", "Payroll migration patch")
		return Ownership("za_local_core", "Shared migration package")

	if path.startswith("za_local/utils/integrations/"):
		return Ownership("za_local_payroll", "Payroll statutory and payment integration")

	if path == "za_local/utils/csv_importer.py":
		return Ownership("za_local_workplace", "Workplace reference-data importer")

	if path in {
		"za_local/hooks.py",
		"za_local/__init__.py",
		"za_local/modules.txt",
		"za_local/overrides/__init__.py",
		"za_local/patches.txt",
		"za_local/practitioner_guide/README.md",
		"za_local/practitioner_guide/__init__.py",
		"za_local/tasks.py",
		"za_local/test_data_loading.py",
		"za_local/utils/__init__.py",
		"za_local/utils/create_test_data.py",
	}:
		return Ownership("za_local_core", "Legacy composition artifact owned by the core migration programme")

	return Ownership("za_local_compatibility", "Temporary compatibility or repository-level artifact")


def build_manifest(legacy_repo: Path) -> dict:
	"""Build a deterministic manifest for all tracked files in the legacy repository."""
	paths = _tracked_paths(legacy_repo)
	missing_paths = [relative_path for relative_path in paths if not (legacy_repo / relative_path).is_file()]
	if missing_paths:
		formatted_paths = "\n".join(f"- {path}" for path in missing_paths)
		raise FileNotFoundError(
			"The legacy worktree is missing files that are still tracked by Git. "
			"Restore the files or stage their deletion before rebuilding the ownership manifest:\n"
			f"{formatted_paths}"
		)

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
		"schema_version": MANIFEST_SCHEMA_VERSION,
		"classification_version": "2026.08",
		"legacy_app": "za_local",
		"target_apps": list(TARGET_APPS),
		"artifact_count": len(artifacts),
		"owner_counts": dict(sorted(owner_counts.items())),
		"artifacts": [asdict(artifact) for artifact in artifacts],
	}


def write_manifest(legacy_repo: Path, output_path: Path) -> None:
	"""Write the ownership manifest with stable ordering and formatting."""
	manifest = build_manifest(legacy_repo.resolve())
	validate_manifest(manifest)
	output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def verify_checked_manifest() -> dict:
	"""Validate the packaged ownership declaration before install/migrate completes."""
	path = Path(__file__).resolve().parents[2] / "ownership_manifest.json"
	manifest = json.loads(path.read_text(encoding="utf-8"))
	validate_manifest(manifest)
	return manifest


def validate_manifest(manifest: dict) -> None:
	"""Validate ownership identity, counts and artifact integrity without extra dependencies."""
	required_keys = {
		"artifact_count",
		"artifacts",
		"classification_version",
		"legacy_app",
		"owner_counts",
		"schema_version",
		"target_apps",
	}
	if set(manifest) != required_keys:
		raise ValueError("ownership manifest has missing or unexpected top-level keys")
	if manifest["schema_version"] != MANIFEST_SCHEMA_VERSION:
		raise ValueError(f"ownership manifest schema_version must be {MANIFEST_SCHEMA_VERSION}")
	if manifest["legacy_app"] != "za_local" or tuple(manifest["target_apps"]) != TARGET_APPS:
		raise ValueError("ownership manifest application identities are invalid")
	artifacts = manifest["artifacts"]
	if not isinstance(artifacts, list) or manifest["artifact_count"] != len(artifacts):
		raise ValueError("ownership manifest artifact_count is inconsistent")
	paths = set()
	owner_counts = {owner: 0 for owner in manifest["owner_counts"]}
	for artifact in artifacts:
		if set(artifact) != {"owner", "path", "reason", "sha256"}:
			raise ValueError("ownership manifest artifact shape is invalid")
		if artifact["owner"] not in ALLOWED_OWNERS:
			raise ValueError(f"unsupported ownership target: {artifact['owner']}")
		if not artifact["path"] or artifact["path"] in paths:
			raise ValueError(f"duplicate or empty ownership path: {artifact['path']}")
		if len(artifact["sha256"]) != 64 or any(
			character not in "0123456789abcdef" for character in artifact["sha256"]
		):
			raise ValueError(f"invalid SHA-256 for ownership path: {artifact['path']}")
		if not artifact["reason"]:
			raise ValueError(f"missing ownership reason: {artifact['path']}")
		paths.add(artifact["path"])
		owner_counts[artifact["owner"]] = owner_counts.get(artifact["owner"], 0) + 1
	if dict(sorted(owner_counts.items())) != manifest["owner_counts"]:
		raise ValueError("ownership manifest owner_counts are inconsistent")


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


def _classify_config(path: str) -> Ownership:
	name = Path(path).stem
	if name == "sa_vat":
		return Ownership("za_local_finance", "Finance navigation configuration")
	if name == "sa_payroll":
		return Ownership("za_local_payroll", "Payroll navigation configuration")
	if name in {"sa_coida", "sa_labour"}:
		return Ownership("za_local_workplace", "Workplace navigation configuration")
	return Ownership("za_local_core", "Shared navigation configuration")


def _classify_public_asset(path: str) -> Ownership:
	lower_path = path.lower()
	if any(token in lower_path for token in ("vat", "commercial", "payment_entry")):
		return Ownership("za_local_finance", "Finance public asset")
	if any(
		token in lower_path
		for token in (
			"payroll",
			"salary",
			"irp5",
			"it3",
			"benefit_claim",
			"/employee.js",
		)
	):
		return Ownership("za_local_payroll", "Payroll public asset")
	if any(token in lower_path for token in ("coida", "labour", "workplace", "oid_claim")):
		return Ownership("za_local_workplace", "Workplace public asset")
	return Ownership("za_local_core", "Shared localisation public asset")


def _classify_template(path: str) -> Ownership:
	lower_path = path.lower()
	if any(token in lower_path for token in ("irp5", "salary_slip")):
		return Ownership("za_local_payroll", "Payroll print template")
	if any(token in lower_path for token in ("commercial", "payment_entry")):
		return Ownership("za_local_finance", "Finance print template")
	return Ownership("za_local_core", "Shared template package")


def _classify_setup(path: str) -> Ownership:
	lower_path = path.lower()
	payroll_tokens = (
		"earnings_components",
		"eti_slab",
		"holiday_list",
		"payroll_period",
		"salary_component",
		"statutory_rate",
		"tax_rebate",
		"tax_slab",
		"emp201",
		"emp501",
		"irp5",
		"sa_payroll",
		"statutory_submission",
	)
	finance_tokens = (
		"vat",
		"sales_tax",
		"purchase_tax",
		"item_tax",
	)
	workplace_tokens = (
		"coida",
		"labour",
		"workplace",
		"oid_claim",
		"seta",
		"bargaining_council",
		"business_trip",
		"employment_equity",
		"annual_training",
		"sectoral_minimum_wage",
	)
	if any(token in lower_path for token in finance_tokens):
		return Ownership("za_local_finance", "Finance setup artifact")
	if any(token in lower_path for token in payroll_tokens):
		return Ownership("za_local_payroll", "Payroll setup artifact")
	if any(token in lower_path for token in workplace_tokens) or lower_path.endswith("/leave_types.py"):
		return Ownership("za_local_workplace", "Workplace setup artifact")
	return Ownership("za_local_core", "Shared setup and migration orchestration")
