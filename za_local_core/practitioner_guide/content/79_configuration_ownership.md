# Configuration ownership

Custom fields and setup records are owned by one app:

- `za_local_core`: shared legal identity, source governance, filing evidence, readiness and privacy, and VAT
  registrations, classifications, tax templates and finance print controls;
- `za_local_payroll`: Employee, Salary Component, Salary Structure, Salary Slip and statutory payroll setup, and
  BCEA/EE/skills/SETA, injury, claim and COIDA setup.

Do not recreate an app-owned field through Customize Form. Report missing fields as a migration/install defect and run the owning app’s setup and tests.
