frappe.ui.form.on("ZA Company Compliance Profile", {
	refresh(frm) {
		if (!frm.is_new() && frm.doc.docstatus === 0 && frm.doc.status !== "Reviewed") {
			frm.add_custom_button(__("Mark Reviewed"), () => frm.call("mark_reviewed").then(() => frm.reload_doc()));
		}
	},
});
