import frappe

def after_install():
    """This runs automatically when 'bench install-app rssfeeds' is executed."""
    print("🚀 Configuring FrappeRSS Enterprise Settings...")
    
    # Increase System-wide Max File Size to 100MB
    system_settings = frappe.get_doc("System Settings")
    system_settings.max_file_size = 104857600  # 100MB in bytes
    system_settings.flags.ignore_mandatory = True
    system_settings.save(ignore_permissions=True)
    
    # Commit the database changes
    frappe.db.commit() # nosemgrep # Required: after_install() runs outside any request-response cycle during bench install; commit is necessary to persist System Settings changes before the installation process completes
    print("✅ Max File Size increased to 100MB.")
    print("🎉 FrappeRSS Installation Complete!")