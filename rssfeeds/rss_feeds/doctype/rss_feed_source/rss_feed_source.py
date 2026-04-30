import frappe
from frappe.model.document import Document
import feedparser
from frappe.utils import now
import time
import cloudscraper
from frappe.utils.file_manager import save_file

def download_attachment_safely(file_url, max_retries=3):
    """Safely downloads a file by mimicking a browser and bypassing Cloudflare."""
    scraper = cloudscraper.create_scraper() # Initializes the Cloudflare bypasser
    
    for attempt in range(max_retries):
        try:
            # allow_redirects=True is crucial for financial sites that bounce links around
            response = scraper.get(file_url, allow_redirects=True, timeout=30)
            
            # If successful, return the raw bytes
            if response.status_code == 200:
                return response.content
                
        except Exception as e:
            if attempt == max_retries - 1:
                # If we failed 3 times, log it and give up gracefully
                frappe.log_error(title=f"File Download Failed: {file_url}", message=str(e))
                return None
            
            # Wait 3 seconds before trying again to let the target server breathe
            time.sleep(3)
            
    return None

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
            # Create the Cloudflare bypass scraper
            scraper = cloudscraper.create_scraper()
            
            # Fetch the raw XML content securely
            response = scraper.get(self.feed_url, timeout=20)
            
            # Throw an explicit error if the firewall still blocks us
            if response.status_code == 403:
                frappe.throw(f"Firewall is aggressively blocking access to {self.feed_url}")
            response.raise_for_status() 
            
            # Pass the raw content to feedparser
            feed = feedparser.parse(response.content)
            
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

                        # --- THE NSE TARPIT FIX ---
                        if "nsearchives.nseindia.com" in file_url and "nsearchives.nseindia.com/" not in file_url:
                            file_url = file_url.replace("nsearchives.nseindia.com", "nsearchives.nseindia.com/")

                        # Fetch the actual file bytes using our new robust 3-try function
                        file_content = download_attachment_safely(file_url)
                        
                        if file_content:
                            # Native Frappe function to save the file and link it to the doc
                            save_file(
                                fname=file_name,
                                content=file_content,
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

    # @frappe.whitelist()
    def process_stuck_articles(self):
        """Finds any articles for this source that are stuck in 'Pending' and re-queues them."""
        stuck_articles = frappe.get_all("RSS Feed Article", 
            filters={
                "ai_processing_status": "Pending", 
                "source": self.name
            },
            limit=50
        )
        
        for a in stuck_articles:
            frappe.enqueue_doc(
                "RSS Feed Article",
                a.name,
                "generate_ai_summary",
                queue="long",
                timeout=1500
            )
        
        return len(stuck_articles)
    
def requeue_all_stuck():
    """Global task to find ALL stuck articles across all sources and re-queue them."""
    sources = frappe.get_all("RSS Feed Source", filters={"status": "Active"})
    for s in sources:
        doc = frappe.get_doc("RSS Feed Source", s.name)
        doc.process_stuck_articles()