#!/usr/bin/env python3
"""Generate the checked-in ownership manifest for the legacy app."""

import argparse
import sys
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE_REPO))

from za_local_core.migration.ownership import write_manifest


def main() -> None:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument(
		"--legacy-repo",
		type=Path,
		default=CORE_REPO.parent / "za_local",
		help="Path to the legacy za_local Git checkout",
	)
	parser.add_argument(
		"--output",
		type=Path,
		default=CORE_REPO / "ownership_manifest.json",
		help="Manifest output path",
	)
	arguments = parser.parse_args()
	write_manifest(arguments.legacy_repo, arguments.output)


if __name__ == "__main__":
	main()
