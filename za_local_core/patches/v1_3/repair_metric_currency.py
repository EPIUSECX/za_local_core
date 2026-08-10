from za_local_core.install import repair_core_metrics


def execute() -> None:
	"""Restamp metric currency from the site default.

	Kept for sites that recorded this patch as pending. ``after_migrate`` now
	performs the same repair on every migrate, because a one-time patch cannot
	reach a fresh install: ``install_app`` marks all patches complete before
	``after_install`` creates the metrics.
	"""
	repair_core_metrics()
