# Copyright (c) 2024, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import os
import zipfile
import tempfile
import shutil
import requests
from frappe.utils import get_url_to_form, strip_html, markdown
from frappe.utils.file_manager import save_file

class RSSFeedArticle(Document):

    def after_insert(self):
        """Triggered automatically right after the article is saved."""
        settings = frappe.get_single("RSS App Settings")
        if settings.enable_ai_pipeline and self.ai_processing_status == "Pending":
            frappe.db.commit() # nosemgrep # Required: enqueue_after_commit=True only enqueues the background job after the transaction is committed; without this commit the job is never dispatched
            frappe.enqueue_doc(
                self.doctype,
                self.name,
                "generate_ai_summary",
                queue="long",
                timeout=1500,
                enqueue_after_commit=True
            )

    # =========================================================================
    # STEP 1: ATTACHMENT & FILE HANDLING
    # =========================================================================


    # def _handle_attachments(self):
    #     """Stable RBI fetcher + smart HTML extraction (no raw_content override issue)."""

    #     import requests
    #     import frappe
    #     from frappe.utils.file_manager import save_file
    #     import tempfile
    #     import os
    #     import shutil
    #     import time
    #     import random
    #     from bs4 import BeautifulSoup

    #     if not self.article_url:
    #         return

    #     temp_dir = tempfile.mkdtemp(prefix="frappe_ingest_")

    #     url = self.article_url.replace("http://", "https://").strip()

    #     headers = {
    #         "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    #         "Referer": "https://www.rbi.org.in/"
    #     }

    #     try:
    #         time.sleep(random.uniform(2, 4))

    #         session = requests.Session()
    #         session.get("https://www.rbi.org.in/", headers=headers, timeout=(5, 10))

    #         res = session.get(url, headers=headers, timeout=(5, 90), allow_redirects=True)
    #         res.raise_for_status()
    #         content = res.content

    #         if not content:
    #             raise Exception("Empty response")

    #         # =========================
    #         # DETECT HTML
    #         # =========================
    #         is_html = b"<html" in content.lower()

    #         filename = (url.split('/')[-1] or "content").split('?')[0]

    #         if is_html:
    #             filename = filename.replace(".aspx", "") + ".html"
    #         else:
    #             if "." not in filename:
    #                 filename += ".bin"

    #         file_path = os.path.join(temp_dir, filename)

    #         with open(file_path, 'wb') as f:
    #             f.write(content)

    #         # =========================
    #         # 🔥 SMART EXTRACTION
    #         # =========================
    #         if is_html:
    #             try:
    #                 soup = BeautifulSoup(content, "html.parser")

    #                 # Try to get only main RBI content
    #                 main = (
    #                     soup.find(id="wrapper")
    #                     or soup.find(id="content")
    #                     or soup.find(class_="content")
    #                     or soup.find("table")  # RBI often uses tables
    #                     or soup.body
    #                 )

    #                 # Remove junk
    #                 for tag in main(["script", "style", "nav", "header", "footer"]):
    #                     tag.decompose()

    #                 # Extract structured text
    #                 lines = []
    #                 for elem in main.find_all(["p", "li", "h1", "h2", "h3", "h4"]):
    #                     text = elem.get_text(strip=True)
    #                     if text and len(text) > 20:  # filter noise
    #                         lines.append(text)

    #                 clean_text = "\n\n".join(lines)

    #                 # ✅ CRITICAL FIX: don't overwrite good RSS content
    #                 if clean_text:
    #                     if not self.raw_content or len(self.raw_content.strip()) < 200:
    #                         self.db_set("raw_content", clean_text[:50000])

    #             except Exception as e:
    #                 frappe.log_error("HTML Parse Failed", str(e))

    #         # =========================
    #         # SAVE FILE
    #         # =========================
    #         with open(file_path, 'rb') as f:
    #             saved_file = save_file(
    #                 fname=filename,
    #                 content=f.read(),
    #                 dt=self.doctype,
    #                 dn=self.name,
    #                 is_private=1
    #             )

    #         # =========================
    #         # UPDATE DOC
    #         # =========================
    #         self.db_set("file_attachment", saved_file.file_url)
    #         frappe.db.commit()
    #         self.reload()

    #         # =========================
    #         # ZIP HANDLING
    #         # =========================
    #         if self.file_attachment and self.file_attachment.lower().endswith(".zip"):
    #             file_doc_name = frappe.db.get_value("File", {"file_url": self.file_attachment}, "name")
    #             if file_doc_name:
    #                 zip_path = frappe.get_doc("File", file_doc_name).get_full_path()
    #                 self._process_zip_contents(zip_path)

    #     except Exception as e:
    #         frappe.log_error(f"Attachment Failed: {self.name}", str(e))

    #     finally:
    #         shutil.rmtree(temp_dir, ignore_errors=True)

    def _handle_attachments(self):
        """Stable RBI fetcher + smart HTML extraction (No HTML file attachments!)."""

        import requests
        import frappe
        from frappe.utils.file_manager import save_file
        import tempfile
        import os
        import shutil
        import time
        import random
        from bs4 import BeautifulSoup

        if not self.article_url:
            return

        temp_dir = tempfile.mkdtemp(prefix="frappe_ingest_")
        url = self.article_url.replace("http://", "https://").strip()

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
            "Referer": "https://www.rbi.org.in/"
        }

        try:
            time.sleep(random.uniform(2, 4))
            session = requests.Session()
            session.get("https://www.rbi.org.in/", headers=headers, timeout=(5, 10))
            
            res = session.get(url, headers=headers, timeout=(5, 90), allow_redirects=True)
            res.raise_for_status()
            content = res.content

            if not content:
                raise Exception("Empty response")

            # =========================
            # DETECT HTML vs REAL FILE
            # =========================
            is_html = b"<html" in content.lower()

            if is_html:
                # ----------------------------------------------------
                # IT IS A WEBPAGE: Scrape text, do NOT attach a file!
                # ----------------------------------------------------
                try:
                    soup = BeautifulSoup(content, "html.parser")

                    # Try to get only main RBI content
                    main = (
                        soup.find(id="wrapper")
                        or soup.find(id="content")
                        or soup.find(class_="content")
                        or soup.find("table")  # RBI often uses tables
                        or soup.body
                    )

                    # Remove junk
                    for tag in main(["script", "style", "nav", "header", "footer"]):
                        tag.decompose()

                    # Extract structured text
                    lines = []
                    for elem in main.find_all(["p", "li", "h1", "h2", "h3", "h4"]):
                        text = elem.get_text(strip=True)
                        if text and len(text) > 20:  # filter noise
                            lines.append(text)

                    clean_text = "\n\n".join(lines)

                    if clean_text:
                        # Save straight to raw_content so AI can read it
                        self.db_set("raw_content", clean_text[:50000])
                        frappe.db.commit()
                        self.reload()
                        
                except Exception as e:
                    frappe.log_error("HTML Parse Failed", str(e))

            else:
                # ----------------------------------------------------
                # IT IS A FILE (.pdf, .zip, etc.): Download and attach
                # ----------------------------------------------------
                filename = os.path.basename((url.split('/')[-1] or "content").split('?')[0])  # strip any directory components
                if not filename or "." not in filename:
                    filename = "attachment.bin"

                file_path = os.path.join(temp_dir, filename)

                # Guard: ensure resolved path stays inside temp_dir
                if not os.path.realpath(file_path).startswith(os.path.realpath(temp_dir)):
                    raise Exception("Unsafe file path detected in URL filename.")

                with open(file_path, 'wb') as f: # nosemgrep # Path sanitized with os.path.basename and validated with realpath against temp_dir above
                    f.write(content)

                # SAVE FILE TO FRAPPE
                with open(file_path, 'rb') as f: # nosemgrep # Path sanitized with os.path.basename and validated with realpath against temp_dir above
                    saved_file = save_file(
                        fname=filename,
                        content=f.read(),
                        dt=self.doctype,
                        dn=self.name,
                        is_private=1
                    )

                # UPDATE DOC
                self.db_set("file_attachment", saved_file.file_url)
                frappe.db.commit() # nosemgrep # Required: this runs inside a background worker outside the request cycle; commit persists the attachment before self.reload() reads it back
                self.reload()

                # ZIP HANDLING
                if self.file_attachment and self.file_attachment.lower().endswith(".zip"):
                    zip_path = frappe.get_doc("File", saved_file.name).get_full_path()
                    self._process_zip_contents(zip_path)

        except Exception as e:
            frappe.log_error(f"Attachment Failed: {self.name}", str(e))

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _process_zip_contents(self, zip_path):
        """Extracts PDFs and identifies the 'Main' circular."""
        extract_dir = tempfile.mkdtemp(prefix="frappe_zip_")
        extracted_pdfs = []
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for member in zip_ref.namelist():
                    filename = os.path.basename(member)
                    if not filename.lower().endswith(".pdf"): continue
                    with zip_ref.open(member) as source:
                        target_path = os.path.join(extract_dir, filename)
                        
                        # Guard: zip entries can contain ../../ traversal sequences
                        if not os.path.realpath(target_path).startswith(os.path.realpath(extract_dir)):
                            frappe.log_error("ZIP Traversal Blocked", f"Skipped unsafe entry: {member}")
                            continue

                        with open(target_path, "wb") as target: # nosemgrep # Path validated with realpath against extract_dir to prevent zip traversal above
                            shutil.copyfileobj(source, target)
                    with open(target_path, 'rb') as f: # nosemgrep # Path validated with realpath against extract_dir to prevent zip traversal above
                        saved_file = save_file(fname=filename, content=f.read(), dt=self.doctype, dn=self.name, is_private=1)
                        extracted_pdfs.append(saved_file)

            if extracted_pdfs:
                primary_pdf = None
                keywords = ["circular", "press", "notification", "main", "report"]
                for pdf in extracted_pdfs:
                    if any(k in pdf.file_name.lower() for k in keywords):
                        primary_pdf = pdf
                        break
                if not primary_pdf: primary_pdf = extracted_pdfs[0]
                self.db_set("file_attachment", primary_pdf.file_url)
            frappe.db.commit() # nosemgrep # Required: background job context; commits extracted zip PDFs and primary file selection so they are visible to the AI pipeline in the next step
        finally:
            shutil.rmtree(extract_dir, ignore_errors=True)

    # =========================================================================
    # STEP 2: TEXT EXTRACTION
    # =========================================================================

    def _extract_text_from_html(self, url):
        """Scrapes text with headers to ensure content found for RBI ones."""
        from bs4 import BeautifulSoup
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            "Referer": "https://www.google.com/"
        }
        try:
            res = requests.get(url, timeout=30, headers=headers)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, 'html.parser')
            for script in soup(["script", "style"]): script.decompose()
            return soup.get_text(separator=' ', strip=True)
        except:
            return ""

    def _extract_text_from_all_attachments(self):
        all_text = ""
        self.reload()
        main_url = self.file_attachment
        files = frappe.get_all("File", filters={"attached_to_doctype": self.doctype, "attached_to_name": self.name}, fields=["name", "file_name", "file_url"])
        
        # Prioritize elected main file
        sorted_files = sorted(files, key=lambda x: x['file_url'] != main_url)
        for f in sorted_files:
            if not f.file_url.lower().endswith((".pdf", ".txt", ".png", ".jpg", ".jpeg")): continue
            f_doc = frappe.get_doc("File", f.name)
            path = f_doc.get_full_path()
            if os.path.exists(path):
                file_text = self._extract_text_from_file(path)
                prefix = "[MAIN DOCUMENT]" if f.file_url == main_url else "[ANNEXURE]"
                all_text += f"\n{prefix} Source: {f.file_name}\n{file_text}\n"
        return all_text

    def _extract_text_from_file(self, file_path):
        text = ""
        try:
            # Guard: path must be inside the Frappe site directory
            site_path = os.path.realpath(frappe.get_site_path())
            if not os.path.realpath(file_path).startswith(site_path):
                frappe.log_error("File Traversal Blocked", f"Rejected path outside site: {file_path}")
                return ""

            if file_path.lower().endswith(".pdf"):
                import fitz
                with fitz.open(file_path) as pdf: # nosemgrep # Path validated with realpath against frappe.get_site_path() above
                    for page in pdf: text += page.get_text() + "\n"
            elif file_path.lower().endswith((".png", ".jpg", ".jpeg")):
                from PIL import Image
                import pytesseract
                text += pytesseract.image_to_string(Image.open(file_path)) + "\n"
            elif file_path.lower().endswith(".txt"):
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f: text = f.read()
        except: pass
        return text

    # =========================================================================
    # STEP 3: AI PIPELINE & NOTIFICATIONS
    # =========================================================================

    @frappe.whitelist()
    def generate_ai_summary(self):
        self.reload() # CRITICAL: Fixes Error 1020
        settings = frappe.get_single("RSS App Settings")
        if not settings.enable_ai_pipeline or self.ai_processing_status in ["Completed", "Summarizing"]: return

        self.db_set("ai_processing_status", "Summarizing")
        frappe.db.commit()   # nosemgrep # Required: background job context; commits "Summarizing" status immediately so concurrent scheduler runs see it and skip, preventing duplicate AI processing

        try:
            self._handle_attachments()
            final_content = self._extract_text_from_all_attachments()
            
            # Scrape HTML if PDF extraction didn't yield text (RBI Case)
            if not final_content.strip() and self.article_url:
                final_content = self._extract_text_from_html(self.article_url)
            
            if not final_content.strip():
                final_content = self.raw_content or ""

            if not final_content.strip():
                self.db_set({"ai_processing_status": "Failed", "ai_summary": "No readable content found."})
                frappe.db.commit()
                return

            self._run_ai_fallback_chain(final_content)
        except Exception as e:
            self._handle_failure(str(e))

    def _run_ai_fallback_chain(self, content):
        import litellm
        profiles = frappe.get_all("AI Provider Profile", filters={"is_enabled": 1}, order_by="priority_sequence asc")
        if not profiles: raise Exception("No active AI Providers.")

        last_error = ""
        for p in profiles:
            profile = frappe.get_doc("AI Provider Profile", p.name)
            
            # Provider Mapping for LiteLLM
            if profile.provider_type == "Zhipu AI (GLM)":
                model_string = f"zhipu/{profile.model_name}"
            elif profile.provider_type == "Dashscope (Qwen)":
                model_string = f"dashscope/{profile.model_name}"
            elif profile.provider_type in ["OpenRouter", "Ollama"]:
                model_string = f"{profile.provider_type.lower()}/{profile.model_name}"
            else:
                model_string = profile.model_name

            try:
                response = litellm.completion(
                    model=model_string,
                    messages=[{"role": "user", "content": f"Summarize in short 1 or 2 paras with key details and/or dates as per content:\n\n{content[:20000]}"}],
                    api_key=profile.get_password("api_key") if profile.api_key else None,
                    api_base=profile.base_url or None,
                    timeout=60
                )
                self.db_set({"ai_summary": markdown(response.choices[0].message.content), "ai_processing_status": "Completed"})
                frappe.db.commit() # nosemgrep # Required: background job context; commits the completed AI summary before reload and webhook notification to prevent data loss if notification fails
                self.reload()
                self.send_google_chat_notification()
                return
            except Exception as e:
                last_error = str(e)
                continue
        raise Exception(f"AI Failed. Last error: {last_error}")

    def _handle_failure(self, error_message):
        frappe.db.rollback()
        self.reload()
        if "[RETRY]" in (self.ai_summary or ""):
            self.db_set({"ai_processing_status": "Failed", "ai_summary": f"<span style='color:red;'>[FINAL FAILURE] {error_message}</span>"})
        else:
            self.db_set({"ai_processing_status": "Pending", "ai_summary": f"[RETRY] Attempt 1 failed: {error_message}"})
            frappe.enqueue_doc(self.doctype, self.name, "generate_ai_summary", queue="long", timeout=1500)
        frappe.db.commit() # nosemgrep # Required: background job context; commits failure/retry status so the retry job sees a clean state when it picks up the document

    def send_google_chat_notification(self):
        """Restored Alert Logic with verified fields from console."""
        try:
            if not self.source: return
            
            source_doc = frappe.get_doc("RSS Feed Source", self.source)
            if not source_doc.webhooks: return 

            # Keywords Logic
            search_text = f"{self.title} {self.ai_summary or ''}".lower()
            def parse_kws(s): return [k.strip().lower() for k in s.split(',') if k.strip()] if s else []
            
            if any(bw in search_text for bw in parse_kws(source_doc.blocked_keywords)): return 
            allowed = parse_kws(source_doc.allowed_keywords)
            if allowed and not any(aw in search_text for aw in allowed): return

            # Notification Content
            frappe_url = get_url_to_form(self.doctype, self.name)
            clean_summary = strip_html(self.ai_summary or "")
            
            # Using verified field names: self.title and source_doc.feed_name
            message_text = f"🚨 *PRIORITY ALERT: {self.title}*\n\n"
            message_text += f"*Source:* {source_doc.feed_name}\n\n"
            message_text += f"*AI Summary:*\n{clean_summary[:1500]}\n\n"
            message_text += f"🔗 <{self.article_url}|Original> | <{frappe_url}|Frappe Article>"

            for row in source_doc.webhooks:
                # Verified field: webhook_url and is_active (not is_enabled)
                webhook = frappe.get_doc("Google Chat Webhook", row.webhook)
                if webhook.is_active and webhook.webhook_url:
                    requests.post(webhook.webhook_url, json={"text": message_text}, timeout=30)
        except Exception as e:
            frappe.log_error(f"Notification Error: {self.name}", str(e))