import frappe
from frappe.desk.doctype.number_card.number_card import get_result

CARDS = (
	"PAYE Payable (EMP201)",
	"UIF Payable (EMP201)",
	"SDL Payable (EMP201)",
	"ETI Utilised (EMP201)",
	"ETI Carried Forward (EMP201)",
	"Salary Slips in Draft",
)


def run():
	meta = frappe.get_meta("EMP201 Submission")
	for fieldname in ("eti_utilized_current_month", "eti_to_be_carried_forward"):
		field = meta.get_field(fieldname)
		print(f"field {fieldname!r}: exists={bool(field)} type={field.fieldtype if field else None}")

	rows = frappe.get_all(
		"EMP201 Submission",
		filters={"docstatus": 1},
		fields=["name", "eti_utilized_current_month", "eti_to_be_carried_forward"],
	)
	print(f"submitted rows: {len(rows)}")
	for row in rows:
		print("   ", dict(row))

	print()
	for label in CARDS:
		if not frappe.db.exists("Number Card", label):
			print(f"{label}: NOT ON SITE")
			continue
		card = frappe.get_doc("Number Card", label)
		value = get_result(card.as_dict(), card.filters_json)
		print(f"{label}: value={value!r} type={type(value).__name__} filters={card.filters_json}")
