# Tax invoices and credit notes

The print profile uses ZAR base/company-currency consideration and the invoice posting date to resolve the approved thresholds. For the approved current period, no tax invoice is required at or below R50, an abridged invoice applies above R50 through R5,000, and a full invoice is required above R5,000. These values are never runtime constants: the exact source, rate pack, checksums and effective dates are returned with the profile.

Confirm supplier identity, VAT number, date, serial number, recipient particulars where required, description, quantity, consideration and VAT. A zero-rated supply is conservatively routed to the full format because an abridged invoice is not appropriate for that supply.

Foreign-currency and unusual transactions are treated conservatively. If a ZAR base amount is unavailable the full format is selected; a foreign-currency amount is never compared directly with a rand threshold. Preview the PDF before deployment and obtain company-specific VAT practitioner approval. A print format is evidence/presentation—it does not correct an incorrectly posted tax transaction.

These print controls are **Preview** until the customer's VAT practitioner approves the Company setup and
representative rendered documents. They do not certify the underlying supply, zero-rating evidence or input-tax
entitlement.
