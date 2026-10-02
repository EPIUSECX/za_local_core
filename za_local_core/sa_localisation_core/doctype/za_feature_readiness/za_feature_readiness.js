frappe.ui.form.on("ZA Feature Readiness", {
	refresh(frm) {
		if (!frm.is_new() && frm.doc.proposed_status && frm.doc.approver === frappe.session.user) {
			frm.add_custom_button(__("Approve Proposed Status"), () =>
				frm.call({ doc: frm.doc, method: "approve_proposed_status", freeze: true }).then(() => frm.reload_doc())
			);
		}
	},
});
