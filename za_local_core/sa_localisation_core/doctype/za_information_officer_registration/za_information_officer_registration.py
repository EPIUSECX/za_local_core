from za_local_core.sa_localisation_core.doctype._privacy import ReviewedPrivacyDocument


class ZAInformationOfficerRegistration(ReviewedPrivacyDocument):
	approved_status = "Active"
	date_pairs = (("effective_from", "effective_to"), ("submitted_on", "registered_on"))
	required_evidence_fields = ("submission_evidence", "registration_evidence")
