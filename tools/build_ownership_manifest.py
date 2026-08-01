#!/usr/bin/env python3
"""Generate the checked-in ownership manifest for the legacy app."""

import sys
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE_REPO))

from za_local_core.migration.ownership import write_manifest


def main() -> None:
	legacy_repo = CORE_REPO.parent / "za_local"
	write_manifest(legacy_repo, CORE_REPO / "ownership_manifest.json")


if __name__ == "__main__":
	main()
