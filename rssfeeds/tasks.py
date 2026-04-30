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
    from frappe.utils import now_datetime
    
    # 1. Find all active alerts where the trigger time has passed
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
            
            # 2. Format the Google Chat Message
            message_text = f"⏰ *ACTION REQUIRED!* ⏰\n\n"
            message_text += f"*Alert Note:* {alert.alert_message}\n"
            message_text += f"*Article:* {article.title}\n\n"
            message_text += f"🔗 <{article.article_url}|Read Original Article>"

            payload = {"text": message_text}
            headers = {"Content-Type": "application/json"}

            # 3. Fire to ALL selected Webhooks
            for row in alert.webhooks:
                webhook_doc = frappe.get_doc("Google Chat Webhook", row.webhook)
                if webhook_doc.is_active and webhook_doc.webhook_url:
                    requests.post(webhook_doc.webhook_url, json=payload, headers=headers, timeout=30)

            # 4. Update the Alert Status or Recalculate Next Date
            if alert.frequency == "Once":
                alert.db_set("status", "Completed")
            else:
                # Recalculate the next valid date based on the one that just fired
                next_dt = alert.calculate_next_trigger(from_datetime=alert.next_trigger_datetime)
                alert.db_set("next_trigger_datetime", next_dt)

            frappe.db.commit()

        except Exception as e:
            frappe.log_error(title=f"Alert Execution Failed: {alert.name}", message=str(e))