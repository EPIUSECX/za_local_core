frappe.ui.form.on("ZA Filing", {
	refresh(frm) {
		if (
			frm.doc.docstatus === 0 &&
			["Draft", "Reviewed"].includes(frm.doc.status) &&
			frm.doc.reviewed_by === frappe.session.user
		) {
			const label = frm.doc.status === "Reviewed" ? __("Re-Mark Reviewed") : __("Mark Reviewed");
			frm.add_custom_button(label, () => {
				frm.call("mark_reviewed").then(() => frm.reload_doc());
			});
		}
	},
});
