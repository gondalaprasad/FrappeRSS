import frappe
from frappe.model.document import Document
import feedparser
from frappe.utils import now
import time
import requests
from frappe.utils.file_manager import save_file

class RSSFeedSource(Document):
    
    def after_insert(self):
        """Automatically trigger a fetch when a new feed source is created."""
        if self.status == "Active":
            frappe.enqueue_doc(
                self.doctype,
                self.name,
                "fetch_latest_items",
                queue="short",
                timeout=300
            )

    @frappe.whitelist()
    def fetch_latest_items(self):
        """Fetches the RSS feed, creates Article records, and downloads attachments."""
        if self.status != "Active":
            if frappe.request:
                frappe.msgprint(f"Feed '{self.feed_name}' is inactive. Skipping fetch.")
            return

        try:
            # Disguise the Python script as a normal Google Chrome browser to bypass anti-bot security
            custom_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            feed = feedparser.parse(self.feed_url, agent=custom_agent)
            
            # Check if feed is valid
            if getattr(feed, "bozo", False) and feed.bozo == 1 and not feed.entries:
                frappe.throw(f"Failed to parse the RSS feed at {self.feed_url}")

            new_articles_count = 0

            # Iterate through the fetched entries
            for entry in feed.entries:
                # Use the entry's link as a unique identifier to prevent duplicates
                article_url = entry.get("link")
                
                # Check if we already have this article saved
                if frappe.db.exists("RSS Feed Article", {"article_url": article_url}):
                    continue # Skip if it already exists

                # Format the published date for MariaDB
                published_date = now()
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published_date = time.strftime('%Y-%m-%d %H:%M:%S', entry.published_parsed)

                # 1. Create the basic article record first
                doc = frappe.get_doc({
                    "doctype": "RSS Feed Article",
                    "title": entry.get("title", "Untitled Article")[:140],
                    "source": self.name,
                    "article_url": article_url,
                    "published_date": published_date,
                    "raw_content": entry.get("summary", "") or entry.get("description", ""),
                    "ai_processing_status": "Pending" 
                })
                doc.insert(ignore_permissions=True)
                new_articles_count += 1

                # 2. The Downloader: Look for file enclosures or PDF links
                file_url = None
                enclosures = entry.get("enclosures", [])
                
                if enclosures:
                    file_url = enclosures[0].get("href")
                elif article_url and article_url.lower().endswith(".pdf"):
                    file_url = article_url

                # 3. Download and attach the file if found
                if file_url:
                    try:
                        # Extract a clean file name from the URL
                        file_name = file_url.split("/")[-1].split("?")[0]
                        if not file_name or len(file_name) < 3:
                            file_name = "downloaded_document.pdf"

                        # --- THE NSE TARPIT FIX: Disguise the PDF download request ---
                        headers = {
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,application/pdf,*/*;q=0.8",
                            "Accept-Language": "en-US,en;q=0.5",
                            "Connection": "keep-alive",
                            "Upgrade-Insecure-Requests": "1"
                        }

                        if "nsearchives.nseindia.com" in file_url and "nsearchives.nseindia.com/" not in file_url:
                            file_url = file_url.replace("nsearchives.nseindia.com", "nsearchives.nseindia.com/")

                        # Fetch the actual file bytes (timeout increased to 60s and headers added)
                        response = requests.get(file_url, headers=headers, stream=True, timeout=60)
                        
                        if response.status_code == 200:
                            # Native Frappe function to save the file and link it to the doc
                            save_file(
                                fname=file_name,
                                content=response.content,
                                dt="RSS Feed Article",
                                dn=doc.name,
                                df="file_attachment",
                                is_private=1
                            )
                    except Exception as download_error:
                        # Log file download failures silently so it doesn't crash the rest of the feed fetch
                        frappe.log_error(title=f"File Download Failed: {doc.name}", message=str(download_error))

            # Update the last fetched timestamp
            self.db_set("last_fetched_on", now())
            frappe.db.commit()

            if frappe.request:
                frappe.msgprint(f"Successfully fetched {new_articles_count} new articles from {self.feed_name}.")

        except Exception as e:
            frappe.log_error(title=f"RSS Fetch Error: {self.name}", message=frappe.get_traceback())
            if frappe.request:
                frappe.throw(f"An error occurred while fetching the feed. Check Error Logs.")