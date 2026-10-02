# Tax templates and classification

Map item and transaction treatment explicitly: standard-rated, zero-rated, export zero-rated, exempt, capital, imported capital or imported other goods. Do not infer treatment from an account or item name.

Each invoice line takes its **SA VAT Category** from the item when it is blank. Where one line genuinely differs from
the item's usual treatment, for example a zero-rated food item exported at the export category, change the line
category and record a **VAT Category Reason**. A changed line without a reason is refused, and the reason stays on the
invoice as review evidence.

Template tax-row descriptions name the treatment only (for example *SA Standard Rated Sales 15%*), never the company, so the same
wording prints on every company's invoices.

Review mixed-use, blocked-input, second-hand goods, imported services, bad debts, change-in-use and manual journal transactions with a VAT practitioner. Unresolved transactions remain review items and do not silently enter VAT201 totals.

Test each template by posting a representative document and reconciling the tax row to the VAT control account.
The System Manager bootstrap rebuilds tax rows on templates bearing the app's generated titles; it is not a safe
merge tool for intentionally customised templates. Preserve a backup and use distinct template names for approved
customer-specific treatments.
