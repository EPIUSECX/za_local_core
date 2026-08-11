"""Core setup that has to follow a Company rather than the app install.

A site is normally installed before it has any company: the setup wizard creates
the first one afterwards. Seeding that only runs at install or migrate therefore
misses the company the customer actually uses.
"""

from __future__ import annotations

from za_local_core.localisation import is_south_african_company


def seed_readiness_for_new_company(doc, method=None) -> None:
	"""Record conservative capability readiness for a new South African company.

	Without this the SA Overview card counts zero capabilities awaiting sign-off,
	which reads as "everything is production ready" when nothing has been assessed
	at all.
	"""
	if not is_south_african_company(doc.name):
		return

	from za_local_core.install import seed_core_readiness
	from za_local_core.sa_vat.install import seed_vat_readiness

	seed_core_readiness(doc.name)
	seed_vat_readiness(doc.name)
