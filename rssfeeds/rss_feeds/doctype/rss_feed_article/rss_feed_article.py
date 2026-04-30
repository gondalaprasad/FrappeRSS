import frappe
from frappe.model.document import Document
import litellm
import os
import tempfile
import zipfile
from frappe.utils.file_manager import save_file
import pytesseract
from frappe.utils import markdown, get_url_to_form, strip_html

class RSSFeedArticle(Document):
    
    def after_insert(self):
        """Triggered automatically right after the article is saved to the database."""
        settings = frappe.get_single("RSS App Settings")
        
        if settings.enable_ai_pipeline and self.ai_processing_status == "Pending":
            frappe.db.commit() 
            frappe.enqueue_doc(
                self.doctype, 
                self.name, 
                "generate_ai_summary", 
                queue="long", 
                timeout=1500
            )

    @frappe.whitelist()
    def generate_ai_summary(self):
        """Attempts to summarize the raw content or attached files using the Fallback Chain."""

        # --- THE DOUBLE LOCK: Check if pipeline was disabled after this was queued ---
        settings = frappe.get_single("RSS App Settings")
        if not settings.enable_ai_pipeline:
            if frappe.request:
                frappe.msgprint("AI Pipeline is currently disabled in settings.")
            return
        
        # --- HELPER FUNCTION: Only reads PDFs and Images ---
        def extract_text_from_path(file_path):
            text = ""
            ext = file_path.lower()
            try:
                # 1. PDF Handling
                if ext.endswith(".pdf"):
                    import fitz
                    try:
                        with fitz.open(file_path) as pdf:
                            for page in pdf:
                                text += page.get_text() + "\n"
                    except Exception as pdf_err:
                        frappe.log_error("PDF Read Error", str(pdf_err))
                        text += "\n[Error: Could not read PDF text natively. The file may be corrupted or protected.]\n"
                            
                # 2. Image Handling (OCR)
                elif ext.endswith((".png", ".jpg", ".jpeg")):
                    from PIL import Image
                    text += pytesseract.image_to_string(Image.open(file_path)) + "\n"
            except Exception as e:
                frappe.log_error(title=f"Extraction Error for {os.path.basename(file_path)}", message=str(e))
                
            return text

        # --- MAIN EXTRACTION LOGIC ---
        extracted_file_text = ""
        
        if self.file_attachment:
            try:
                file_doc_name = frappe.db.get_value("File", {"file_url": self.file_attachment}, "name")
                if file_doc_name:
                    doc_file = frappe.get_doc("File", file_doc_name)
                    main_file_path = doc_file.get_full_path()
                    
                    if main_file_path.lower().endswith(".zip"):
                        with tempfile.TemporaryDirectory() as tmpdirname:
                            with zipfile.ZipFile(main_file_path, 'r') as zip_ref:
                                zip_ref.extractall(tmpdirname)
                                
                            # Walk through the extracted temporary folder
                            for root, dirs, files in os.walk(tmpdirname):
                                for file_name in files:
                                    extracted_path = os.path.join(root, file_name)
                                    
                                    # 1. Read the file bytes and attach it to the Frappe sidebar
                                    try:
                                        with open(extracted_path, 'rb') as f:
                                            file_content = f.read()
                                            
                                        # Notice we DO NOT use 'df' here, so it goes to the generic attachments sidebar
                                        save_file(
                                            fname=file_name,
                                            content=file_content,
                                            dt=self.doctype,
                                            dn=self.name,
                                            is_private=1
                                        )
                                    except Exception as attach_err:
                                        frappe.log_error(title="Zip File Attach Error", message=str(attach_err))

                                    # 2. Extract text ONLY if it is an AI-readable format
                                    if file_name.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg')):
                                        extracted_file_text += f"\n--- Start of {file_name} ---\n"
                                        extracted_file_text += extract_text_from_path(extracted_path)
                                        extracted_file_text += f"\n--- End of {file_name} ---\n"
                    else:
                        # It's a normal standalone file
                        extracted_file_text = extract_text_from_path(main_file_path)
                        
            except Exception as e:
                frappe.log_error(title=f"Master File Extraction Failed: {self.name}", message=str(e))

        # Combine the text. Prioritize the extracted file text if it exists.
        final_content_to_summarize = extracted_file_text if extracted_file_text.strip() else self.raw_content

        if not final_content_to_summarize:
            frappe.msgprint("No content or file available to summarize.")
            return

        # --- AI FALLBACK LOOP ---
        profiles = frappe.get_all("AI Provider Profile", filters={"is_enabled": 1}, order_by="priority_sequence asc")
        if not profiles:
            frappe.throw("No active AI Provider Profiles found. Please configure one.")

        self.db_set("ai_processing_status", "Summarizing")
        frappe.db.commit()

        for p in profiles:
            profile = frappe.get_doc("AI Provider Profile", p.name)
            
            model_string = profile.model_name
            if profile.provider_type == "OpenRouter":
                model_string = f"openrouter/{profile.model_name}"
            elif profile.provider_type == "Ollama":
                model_string = f"ollama/{profile.model_name}"

            try:
                api_key = profile.get_password("api_key") if profile.api_key else None
                
                prompt = f"Please analyze and summarize the following document/data in 4 to 5 detailed bullet points. Focus on the core facts, trends, and findings.\n\n{final_content_to_summarize[:25000]}" 

                response = litellm.completion(
                    model=model_string,
                    messages=[{"role": "user", "content": prompt}],
                    api_key=api_key,
                    api_base=profile.base_url or None
                )

                # Get the raw markdown summary from AI
                raw_summary = response.choices[0].message.content
                
                # Convert Markdown to HTML for the Text Editor field
                html_summary = markdown(raw_summary)
                
                # Save the HTML formatted summary
                self.db_set("ai_summary", html_summary)
                self.db_set("ai_processing_status", "Completed")
                frappe.db.commit()

                # INJECT THIS LINE RIGHT HERE:
                self.send_google_chat_notification()

                if frappe.request: 
                    frappe.msgprint(f"Successfully summarized using {profile.provider_name}!")
                return 

            except Exception as e:
                frappe.log_error(title=f"AI Fallback: {profile.provider_name} Failed", message=str(e))
                continue
        
        self.db_set("ai_processing_status", "Check Manually")
        frappe.db.commit()
        if frappe.request:
            frappe.throw("All AI Providers failed to summarize the article. Check Error Logs.")

    def send_google_chat_notification(self):
        """Sends a formatted message to ALL mapped Google Chat webhooks IF it passes keyword filters."""
        try:
            import requests

            if not self.source:
                return
            
            source_doc = frappe.get_doc("RSS Feed Source", self.source)
            
            # Check if there are any webhooks added
            if not source_doc.get("webhooks"):
                return 

            # ==========================================
            # --- INTELLIGENCE FILTER: KEYWORD CHECK ---
            # ==========================================
            
            # 1. Combine all available text into a massive lowercase search string
            search_text = f"{self.title} {self.ai_summary or ''} {self.raw_content or ''}".lower()
            
            # Helper function to cleanly split comma-separated keywords
            def parse_keywords(kw_string):
                if not kw_string: return []
                return [k.strip().lower() for k in kw_string.split(',') if k.strip()]

            allowed_kws = parse_keywords(source_doc.get("allowed_keywords"))
            blocked_kws = parse_keywords(source_doc.get("blocked_keywords"))

            # 2. The Blocked Check (Absolute Override)
            for bw in blocked_kws:
                if bw in search_text:
                    frappe.log_error(title="Alert Halted: Blocked Keyword", message=f"Article: {self.name}\nBlocked Word Found: '{bw}'")
                    return 

            # 3. The Allowed Check (Must contain at least one, IF the list isn't empty)
            if allowed_kws:
                has_allowed = any(aw in search_text for aw in allowed_kws)
                if not has_allowed:
                    return 
                    
            # ==========================================
            # --- END FILTER (PROCEED TO SEND) ---------
            # ==========================================

            # Generate the internal Frappe Desk link for the article
            frappe_article_url = get_url_to_form("RSS Feed Article", self.name)
            
            # Strip the HTML tags out of the summary so it looks clean in Google Chat
            clean_summary = strip_html(self.ai_summary or "")

            message_text = f"🚨 *PRIORITY ALERT: {self.title}*\n\n"
            message_text += f"*Source:* {source_doc.feed_name}\n\n"
            message_text += f"*AI Summary:*\n{clean_summary}\n\n"
            message_text += f"🔗 <{frappe_article_url}|View Original PDF & AI Summary in Frappe>"

            payload = {"text": message_text}
            headers = {"Content-Type": "application/json"}

            # Fire a message to every webhook in the table!
            for row in source_doc.webhooks:
                webhook_doc = frappe.get_doc("Google Chat Webhook", row.webhook)
                
                if webhook_doc.is_active and webhook_doc.webhook_url:
                    response = requests.post(webhook_doc.webhook_url, json=payload, headers=headers, timeout=30)
                    
                    if response.status_code not in [200, 201]:
                        frappe.log_error(title=f"Google Chat Webhook Failed: {webhook_doc.webhook_name}", message=response.text)

        except Exception as e:
            frappe.log_error(title=f"Webhook Execution Error: {self.name}", message=str(e))