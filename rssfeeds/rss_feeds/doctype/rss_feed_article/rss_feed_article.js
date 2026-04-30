frappe.ui.form.on('RSS Feed Article', {
    refresh: function(frm) {
        
        // ==========================================
        // 1. SET ALERT BUTTON LOGIC
        // ==========================================
        // Add the custom button to the top right of the form
        frm.add_custom_button('⏰ Set Alert', () => {
            // Pop open a new 'Article Action Alert' document
            // and automatically fill in the Linked Article field!
            frappe.new_doc('Article Action Alert', {
                article: frm.doc.name
            });
        });
        // Make the button blue (primary) so it stands out
        frm.change_custom_button_type('⏰ Set Alert', null, 'primary');


        // ==========================================
        // 2. FAVORITES BUTTON LOGIC
        // ==========================================
        // Determine what the button should say based on current status
        let fav_label = frm.doc.is_favorite ? '❌ Remove Favorite' : '⭐ Add to Favorites';
        
        frm.add_custom_button(fav_label, function() {
            // Toggle the checkbox (If 1, make it 0. If 0, make it 1)
            let new_status = frm.doc.is_favorite ? 0 : 1;
            
            // Set the hidden checkbox value and immediately save the document
            frm.set_value('is_favorite', new_status);
            frm.save('Save', () => {
                // Show a nice popup alert when saved
                frappe.show_alert({
                    message: new_status ? '⭐ Added to Favorites!' : 'Removed from Favorites.',
                    indicator: new_status ? 'green' : 'orange'
                });
            });
        });
        
        // Make the button visually stand out with Frappe's native UI colors
        if (frm.doc.is_favorite) {
            frm.change_custom_button_type('❌ Remove Favorite', null, 'warning'); // Yellow/Orange
        } else {
            frm.change_custom_button_type('⭐ Add to Favorites', null, 'default'); // Standard grey
        }


        // ==========================================
        // 3. INLINE PDF VIEWER LOGIC
        // ==========================================
        // Check if the PDF Viewer HTML field exists on the form
        if (frm.fields_dict.pdf_viewer) {
            
            // Check if the article actually has any downloaded attachments
            if (frm.attachments && frm.attachments.get_attachments().length > 0) {
                
                // Find the first attachment that is a PDF
                let pdf_file = frm.attachments.get_attachments().find(f => f.file_url.endsWith('.pdf'));

                if (pdf_file) {
                    let pdf_url = pdf_file.file_url;
                    
                    // Build the custom UI: A right-aligned button (near the PDF) + The PDF iframe
                    let html_content = `
                        <div style="margin-bottom: 10px; text-align: right;">
                            <a href="${pdf_url}" target="_blank" class="btn btn-primary btn-sm" style="background-color: #1736b0; color: white; border: none; padding: 5px 10px; border-radius: 4px; text-decoration: none;">
                                Open PDF in New Tab ↗
                            </a>
                        </div>
                        <iframe src="${pdf_url}" width="100%" height="800px" style="border: 1px solid #d1d8dd; border-radius: 8px; box-shadow: 0px 4px 12px rgba(0,0,0,0.05);"></iframe>
                    `;
                    
                    // Inject the UI into the HTML field
                    frm.get_field('pdf_viewer').$wrapper.html(html_content);
                } else {
                    // It has attachments, but no PDFs (maybe images or zips)
                    frm.get_field('pdf_viewer').$wrapper.html('<p class="text-muted" style="text-align: center; padding: 20px;">No PDF attached to this article.</p>');
                }
            } else {
                // No attachments downloaded at all
                frm.get_field('pdf_viewer').$wrapper.html('<p class="text-muted" style="text-align: center; padding: 20px;">No documents available to view.</p>');
            }
        }

    }
});