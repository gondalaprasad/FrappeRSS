import frappe
from frappe.utils import add_to_date, now

def fetch_all_active_feeds():
    """Runs via Frappe Scheduler to fetch all active RSS feeds automatically."""
    active_feeds = frappe.get_all("RSS Feed Source", filters={"status": "Active"})
    
    for feed in active_feeds:
        frappe.enqueue_doc(
            "RSS Feed Source",
            feed.name,
            "fetch_latest_items",
            queue="short"
        )

def sweep_stuck_articles():
    """Finds articles that got stuck due to server restarts and re-queues them."""

    # Check if the pipeline is actually enabled before sweeping!
    settings = frappe.get_single("RSS App Settings")
    if not settings.enable_ai_pipeline:
        return
    
    # 1. Re-queue anything sitting in 'Pending'
    pending_articles = frappe.get_all("RSS Feed Article", filters={"ai_processing_status": "Pending"})
    for doc in pending_articles:
        frappe.enqueue_doc(
            "RSS Feed Article",
            doc.name,
            "generate_ai_summary",
            queue="long",
            timeout=300
        )

    # 2. Rescue 'Summarizing' jobs that crashed mid-way (modified more than 30 mins ago)
    thirty_mins_ago = add_to_date(now(), minutes=-30)
    stuck_summarizing = frappe.get_all(
        "RSS Feed Article", 
        filters={
            "ai_processing_status": "Summarizing", 
            "modified": ("<", thirty_mins_ago)
        }
    )
    
    for doc in stuck_summarizing:
        # Revert them to Pending. The next time the sweeper runs, it will catch them!
        frappe.db.set_value("RSS Feed Article", doc.name, "ai_processing_status", "Pending")

def process_action_alerts():
    """Runs every few minutes to check for due alerts and fire them."""
    import requests
    import frappe
    from frappe.utils import now_datetime, add_to_date, get_datetime

    # 1. Find all active alerts where the trigger time has passed
    # Using now_datetime() ensures we compare the full Date + Time
    due_alerts = frappe.get_all(
        "Article Action Alert",
        filters={
            "status": "Active",
            "next_trigger_datetime": ("<=", now_datetime())
        }
    )

    for alert_record in due_alerts:
        alert = frappe.get_doc("Article Action Alert", alert_record.name)
        
        try:
            # Get the original article for context
            article = frappe.get_doc("RSS Feed Article", alert.article)
            
            # 2. Format the Message
            message_text = f"⏰ *ACTION REQUIRED!* ⏰\n\n"
            message_text += f"*Alert Note:* {alert.alert_message}\n"
            message_text += f"*Article:* {article.title}\n\n"
            message_text += f"🔗 <{article.article_url}|Read Original Article>"

            payload = {"text": message_text}
            headers = {"Content-Type": "application/json"}

            # 3. Fire to Webhooks
            for row in alert.webhooks:
                webhook_doc = frappe.get_doc("Google Chat Webhook", row.webhook)
                if webhook_doc.is_active and webhook_doc.webhook_url:
                    requests.post(webhook_doc.webhook_url, json=payload, headers=headers, timeout=30)

            # 4. Update Status or Recalculate Next Date
            if alert.frequency == "Once":
                alert.db_set("status", "Completed")
            else:
                # IMPORTANT: Pass the current next_trigger_datetime to calculate the subsequent one
                # If the method is inside the DocType class, use alert.calculate_next_trigger()
                # Otherwise, use the logic below to update the field.
                new_next_dt = calculate_next_trigger_logic(alert)
                alert.db_set("next_trigger_datetime", new_next_dt)

            frappe.db.commit()

        except Exception as e:
            frappe.db.rollback()
            frappe.log_error(title=f"Alert Execution Failed: {alert.name}", message=frappe.get_traceback())

def calculate_next_trigger_logic(doc):
    """Helper to calculate next date based on frequency."""
    from frappe.utils import add_to_date, get_datetime, now_datetime
    
    current_scheduled = get_datetime(doc.next_trigger_datetime)
    
    if doc.frequency == "Daily":
        return add_to_date(current_scheduled, days=1)
    
    elif doc.frequency == "Weekdays":
        # Skip Saturday(5) and Sunday(6)
        next_dt = add_to_date(current_scheduled, days=1)
        while get_datetime(next_dt).weekday() >= 5:
            next_dt = add_to_date(next_dt, days=1)
        return next_dt
        
    elif doc.frequency == "Interval":
        # Assuming you have an 'interval_days' field
        days = doc.interval_days or 1
        return add_to_date(current_scheduled, days=days)
        
    return add_to_date(current_scheduled, days=1) # Default fallback