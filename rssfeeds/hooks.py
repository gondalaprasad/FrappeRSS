app_name = "rssfeeds"
app_title = "RSS Feeds"
app_publisher = "Prasad Gondala"
app_description = "A custom Frappe app to manage and aggregate RSS feeds."
app_email = "gondalaprasad@gmail.com"
app_license = "mit"

# Requirements
# ------------------
# This line fixes the Marketplace 'NPM-style semver' error
required_apps = [
    {"name": "frappe", "version": ">=15.0.0 <16.0.0"}
]

# Installation
# ------------
after_install = "rssfeeds.install.after_install"

# Scheduled Tasks
# ---------------
scheduler_events = {
    "all": [
        "rssfeeds.tasks.fetch_all_active_feeds",
        "rssfeeds.tasks.sweep_stuck_articles",
        "rssfeeds.tasks.process_action_alerts"
    ]
}

# Testing
# -------
# before_tests = "rssfeeds.install.before_tests"

# Desk Notifications
# ------------------
# notification_config = "rssfeeds.notifications.get_notification_config"