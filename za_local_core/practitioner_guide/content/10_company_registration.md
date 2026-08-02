# Company and South African registration details

Set Country to South Africa and confirm the legal name, trading name, registration number, income-tax number and the registrations that apply: PAYE, UIF, SDL, VAT and COIDA. Use the domain-owned fields shown by each installed app.

Maintain physical and postal addresses, filing contacts and company currency. Registration numbers are sensitive configuration: restrict changes, review them independently and verify them against authority correspondence before producing tax documents, certificates or returns.

Migration may create a disabled **Draft** Company Compliance Profile from populated legacy Company fields. That is
an inventory aid, not approval. A preparer must confirm the effective period and registration indicators, a
different authorised user must mark it Reviewed, and a manager who is neither preparer nor reviewer must submit it
with private approval evidence and a matching SHA-256 checksum. Domain calculations should resolve only the one
submitted, enabled **Approved** profile applicable on their transaction date.

Role boundary: a `ZA Compliance User` may prepare the profile. Mark Reviewed requires the recorded signed-in user
to have `ZA Compliance Reviewer`, `ZA Compliance Manager` or `System Manager` and not be the creator. Submission
requires the recorded signed-in approver to have `ZA Compliance Manager` or `System Manager` and be neither the
creator nor reviewer. Role assignment is an organisational control and does not certify the registration details.
