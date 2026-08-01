import frappe
from frappe.tests.classes import IntegrationTestCase


class TestPrivacyGovernance(IntegrationTestCase):
	def setUp(self):
		self.company = frappe.get_all(
			"Company", filters={"country": "South Africa"}, pluck="name", limit=1
		)[0]
		self.case_owner = self._ensure_user("_test.za.privacy.owner@example.com", "Privacy Owner")
		self.reviewer = self._ensure_user("_test.za.privacy.reviewer@example.com", "Privacy Reviewer")

	def test_information_officer_registration_requires_independent_review_and_evidence(self):
		registration = self._information_officer_registration(reviewed_by="Administrator")
		registration.insert()
		with self.assertRaises(frappe.ValidationError):
			registration.submit()

		approved = self._information_officer_registration(reviewed_by=self.reviewer)
		approved.submission_evidence = "/private/files/_test-io-submission.pdf"
		approved.insert()
		approved.submit()

		self.assertEqual(approved.status, "Active")
		self.assertIsNotNone(approved.reviewed_on)

	def test_processing_activity_requires_approved_company_scoped_controls(self):
		retention = self._approved_retention_schedule()
		transfer = self._approved_cross_border_transfer()
		activity = frappe.get_doc(
			{
				"doctype": "ZA Processing Activity",
				"company": self.company,
				"activity_name": "_Test employee payroll processing",
				"business_process": "_Test Payroll",
				"responsible_user": self.case_owner,
				"processing_purpose": "_Test pay employees and meet statutory duties",
				"processing_justification": "Legal Obligation",
				"justification_details": "_Test employment and tax law duties",
				"data_subject_categories": "_Test employees",
				"personal_information_categories": "_Test payroll and tax records",
				"recipients": "_Test SARS and approved payroll operators",
				"cross_border_transfer": 1,
				"cross_border_transfer_record": transfer.name,
				"retention_schedule": retention.name,
				"security_measures": "_Test role access, encryption and audit logs",
				"last_reviewed_on": "2026-07-01",
				"next_review_date": "2027-07-01",
				"risk_assessment": "/private/files/_test-ropa-risk.pdf",
				"reviewed_by": self.reviewer,
			}
		).insert()
		activity.submit()

		self.assertEqual(activity.status, "Approved")
		self.assertEqual(activity.retention_schedule, retention.name)

	def test_data_subject_request_enforces_identity_and_status_transitions(self):
		request = frappe.get_doc(
			{
				"doctype": "ZA Data Subject Request",
				"company": self.company,
				"request_type": "Access to Personal Information",
				"data_subject_reference": "_TEST-DS-001",
				"responsible_user": self.case_owner,
				"request_channel": "Email",
				"received_on": "2026-08-01",
				"due_date": "2026-08-31",
				"request_scope": "_Test payroll records",
				"request_evidence": "/private/files/_test-dsr-request.pdf",
			}
		).insert()

		request.status = "Fulfilled"
		with self.assertRaises(frappe.ValidationError):
			request.save()

		request.reload()
		request.status = "In Progress"
		request.identity_verified_on = "2026-08-02"
		request.identity_verification_evidence = "/private/files/_test-id-check.pdf"
		request.save()
		request.status = "Fulfilled"
		with self.assertRaises(frappe.ValidationError):
			request.save()

		request.reload()
		request.status = "Fulfilled"
		request.completed_on = "2026-08-10"
		request.final_response_evidence = "/private/files/_test-dsr-response.pdf"
		request.reviewed_by = self.reviewer
		request.save()
		request.status = "Closed"
		request.save()

		self.assertEqual(request.status, "Closed")
		self.assertIsNotNone(request.reviewed_on)

	def test_incident_requires_notification_and_remediation_evidence(self):
		incident = frappe.get_doc(
			{
				"doctype": "ZA Personal Information Incident",
				"company": self.company,
				"incident_title": "_Test unauthorised payroll export",
				"severity": "High",
				"responsible_user": self.case_owner,
				"detected_at": "2026-08-01 09:00:00",
				"incident_summary": "_Test controlled incident description",
				"systems_or_locations": "_Test payroll export store",
				"personal_information_categories": "_Test payroll identifiers",
				"affected_data_subjects": 2,
			}
		).insert()
		incident.status = "Triaged"
		incident.save()
		incident.status = "Contained"
		incident.contained_at = "2026-08-01 10:00:00"
		incident.containment_evidence = "/private/files/_test-containment.pdf"
		incident.save()
		incident.status = "Notification Assessment"
		incident.notification_decision = "Regulator and Data Subjects"
		incident.notification_rationale = "_Test notification required after risk assessment"
		incident.notification_assessment_evidence = "/private/files/_test-notification-assessment.pdf"
		incident.save()
		incident.status = "Notifying"
		incident.save()
		incident.status = "Remediating"
		with self.assertRaises(frappe.ValidationError):
			incident.save()

		incident.reload()
		incident.status = "Remediating"
		incident.regulator_notified_on = "2026-08-01 11:00:00"
		incident.regulator_notification_evidence = "/private/files/_test-regulator-notice.pdf"
		incident.data_subjects_notified_on = "2026-08-01 12:00:00"
		incident.data_subject_notification_evidence = "/private/files/_test-subject-notice.pdf"
		incident.save()
		incident.status = "Resolved"
		incident.resolved_at = "2026-08-02 10:00:00"
		incident.remediation_evidence = "/private/files/_test-remediation.pdf"
		incident.reviewed_by = self.reviewer
		incident.save()

		self.assertEqual(incident.status, "Resolved")
		self.assertIsNotNone(incident.reviewed_on)

	def test_cross_border_transfer_rejects_south_african_destination(self):
		transfer = self._cross_border_transfer("South Africa")
		with self.assertRaises(frappe.ValidationError):
			transfer.insert()

	def test_paia_manual_requires_approved_information_officer_registration(self):
		registration = self._information_officer_registration(reviewed_by=self.reviewer)
		registration.submission_evidence = "/private/files/_test-io-submission.pdf"
		registration.insert()
		manual = self._paia_manual(registration.name)
		with self.assertRaises(frappe.ValidationError):
			manual.insert()

		registration.submit()
		manual.insert()
		manual.submit()
		self.assertEqual(manual.status, "Published")

	def test_sensitive_case_permissions_are_owner_scoped(self):
		meta = frappe.get_meta("ZA Data Subject Request")
		user_permission = next(
			permission
			for permission in meta.permissions
			if permission.role == "ZA Compliance User" and permission.permlevel == 0
		)
		reviewer_sensitive_permission = next(
			permission
			for permission in meta.permissions
			if permission.role == "ZA Compliance Reviewer" and permission.permlevel == 1
		)

		self.assertEqual(user_permission.if_owner, 1)
		self.assertEqual(user_permission.delete, 0)
		self.assertEqual(reviewer_sensitive_permission.mask, 1)

	def _information_officer_registration(self, reviewed_by: str):
		return frappe.get_doc(
			{
				"doctype": "ZA Information Officer Registration",
				"company": self.company,
				"officer_name": "_Test Information Officer",
				"designation": "_Test Chief Executive",
				"responsible_user": self.case_owner,
				"submitted_on": "2026-07-01",
				"effective_from": "2026-07-01",
				"reviewed_by": reviewed_by,
			}
		)

	def _approved_retention_schedule(self):
		doc = frappe.get_doc(
			{
				"doctype": "ZA Retention Schedule",
				"company": self.company,
				"record_class": "_Test payroll records",
				"business_owner": "_Test Payroll",
				"responsible_user": self.case_owner,
				"retention_trigger": "_Test termination of employment",
				"retention_period_value": 5,
				"retention_period_unit": "Years",
				"legal_requirement": 1,
				"legal_basis": "_Test statutory recordkeeping requirement",
				"disposal_method": "Secure Destruction",
				"disposal_instructions": "_Test verified secure destruction",
				"legal_hold_process": "_Test suspend disposal on authorised legal hold",
				"effective_from": "2026-07-01",
				"legal_basis_evidence": "/private/files/_test-retention-basis.pdf",
				"reviewed_by": self.reviewer,
			}
		).insert()
		doc.submit()
		return doc

	def _approved_cross_border_transfer(self):
		doc = self._cross_border_transfer("Germany").insert()
		doc.submit()
		return doc

	def _cross_border_transfer(self, destination_country: str):
		return frappe.get_doc(
			{
				"doctype": "ZA Cross Border Transfer",
				"company": self.company,
				"transfer_name": "_Test cloud hosting transfer",
				"responsible_user": self.case_owner,
				"recipient_name": "_Test Foreign Operator",
				"destination_country": destination_country,
				"transfer_purpose": "_Test encrypted payroll hosting",
				"personal_information_categories": "_Test payroll records",
				"data_subject_categories": "_Test employees",
				"transfer_ground": "Adequate Protection or Binding Agreement",
				"safeguards": "_Test binding agreement and technical controls",
				"assessment_date": "2026-07-01",
				"next_review_date": "2027-07-01",
				"effective_from": "2026-07-01",
				"transfer_assessment": "/private/files/_test-transfer-assessment.pdf",
				"reviewed_by": self.reviewer,
			}
		)

	def _paia_manual(self, registration: str):
		return frappe.get_doc(
			{
				"doctype": "ZA PAIA Manual",
				"company": self.company,
				"manual_title": "_Test PAIA Manual",
				"manual_version": "_Test v1",
				"responsible_user": self.case_owner,
				"information_officer_registration": registration,
				"published_on": "2026-07-01",
				"effective_from": "2026-07-01",
				"physical_availability": "_Test registered office",
				"languages": "_Test English",
				"last_reviewed_on": "2026-07-01",
				"next_review_due": "2027-07-01",
				"review_scope": "_Test annual content and publication review",
				"manual_file": "/private/files/_test-paia-manual.pdf",
				"publication_evidence": "/private/files/_test-paia-publication.pdf",
				"reviewed_by": self.reviewer,
			}
		)

	@staticmethod
	def _ensure_user(email: str, full_name: str) -> str:
		if frappe.db.exists("User", email):
			return email
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": full_name,
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)
		return email
