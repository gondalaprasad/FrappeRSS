frappe.ui.form.on("RSS Feed Source", {
    refresh(frm) {
        // Only show the button if the record is saved (not new) and is Active
        if (!frm.is_new() && frm.doc.status === "Active") {
            frm.add_custom_button(__("Fetch Now"), function() {
                frappe.call({
                    method: "fetch_latest_items",
                    doc: frm.doc,
                    freeze: true,
                    freeze_message: __("Fetching latest articles from RSS..."),
                    callback: function(r) {
                        if (!r.exc) {
                            // Reload the page to show the updated Last Fetched timestamp
                            frm.reload_doc();
                        }
                    }
                });
            });
        }
    }
});