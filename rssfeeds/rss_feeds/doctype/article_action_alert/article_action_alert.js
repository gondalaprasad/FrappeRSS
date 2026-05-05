// Copyright (c) 2026, Prasad Gondala and contributors
// For license information, please see license.txt

frappe.ui.form.on('Article Action Alert', {

    // ✅ No frm.trigger('frequency') here anymore.
    // depends_on in JSON handles all field visibility on load automatically.
    // Calling set_value() during refresh marks the form dirty = "Not Saved" forever.
    refresh: function(frm) {
        // intentionally empty - depends_on handles display
    },

    // This only fires when the user manually changes the Frequency dropdown.
    frequency: function(frm) {
        const freq = frm.doc.frequency;

        if (freq === 'Once') {
            // Clear recurring-only fields
            frm.set_value('time_of_day', null);
            frm.set_value('interval_days', null);
            ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']
                .forEach(day => frm.set_value(day, 0));
            // ✅ Do NOT touch next_trigger_datetime — Python sets it from once_datetime on save

        } else {
            // Clear once-only field
            frm.set_value('once_datetime', null);

            if (freq !== 'Interval') {
                frm.set_value('interval_days', null);
            }

            if (freq !== 'Specific Days') {
                ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']
                    .forEach(day => frm.set_value(day, 0));
            }
        }
    }
});