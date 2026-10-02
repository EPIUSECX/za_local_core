from za_local_core.role_grants import grant_core_permissions


def execute():
	"""The SA VAT checklist's own role could not open the source and pack it asks it to confirm."""
	grant_core_permissions()
