from za_local_core.role_grants import grant_core_permissions


def execute():
	"""EE-PERM-1: ZA Compliance Reviewer could not read the Company it reviews for."""
	grant_core_permissions()
