import frappe


def execute():
	"""VAT-9: the bootstrap VAT templates printed "<rate> - <company>" on every invoice tax line.

	Only template rows whose description is exactly the template's own title, as the
	bootstrap wrote it, are changed; descriptions an administrator edited are left alone.
	"""
	for template_doctype, row_doctype in (
		("Sales Taxes and Charges Template", "Sales Taxes and Charges"),
		("Purchase Taxes and Charges Template", "Purchase Taxes and Charges"),
	):
		for template in frappe.get_all(template_doctype, fields=["name", "title", "company"]):
			suffix = f" - {template.company}"
			if not template.title or not template.title.endswith(suffix):
				continue
			frappe.db.set_value(
				row_doctype,
				{"parenttype": template_doctype, "parent": template.name, "description": template.title},
				"description",
				template.title[: -len(suffix)],
				update_modified=False,
			)
