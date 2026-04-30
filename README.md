# 📡 FrappeRSS — Enterprise Regulatory Intelligence

<div align="center">

[![GitHub stars](https://img.shields.io/github/stars/gondalaprasad/FrappeRSS?style=social)](https://github.com/gondalaprasad/FrappeRSS/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/gondalaprasad/FrappeRSS?style=social)](https://github.com/gondalaprasad/FrappeRSS/network/members)
[![GitHub watchers](https://img.shields.io/github/watchers/gondalaprasad/FrappeRSS?style=social)](https://github.com/gondalaprasad/FrappeRSS/watchers)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Frappe Framework](https://img.shields.io/badge/Frappe-v15+-blue.svg)](https://frappeframework.com/)
[![Python](https://img.shields.io/badge/Python-3.10+-green.svg)](https://www.python.org/)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-gondalaprasad-0A66C2?logo=linkedin&logoColor=white)](https://www.linkedin.com/in/gondalaprasad/)

</div>

---

**FrappeRSS** is an automated, AI-powered threat and news pipeline built directly on the Frappe framework. It is designed to automatically fetch government circulars, download massive regulatory PDFs, perform OCR on scanned documents, summarize them using advanced AI (LiteLLM), and securely route priority alerts via Google Chat Webhooks.

---

## 📈 Repository Activity

<div align="center">

[![Star History Chart](https://api.star-history.com/svg?repos=gondalaprasad/FrappeRSS&type=Date)](https://star-history.com/#gondalaprasad/FrappeRSS&Date)

</div>

---

## ✨ Core Functionality & Features

| Feature | Description |
|---|---|
| 📥 **Automated RSS Fetching** | Background schedulers pull the latest circulars and news items at your preferred intervals. |
| 🛡️ **Bot-Bypass PDF Processor** | Safely downloads massive regulatory PDFs (up to 100MB) bypassing standard government anti-scraping firewalls using custom user-agent headers. |
| 🧠 **AI Executive Summarization** | Passes downloaded document text and OCR data through LiteLLM to generate instant, highly accurate executive summaries. |
| 🚦 **Smart Webhook Gatekeeper** | Keyword-based Allow/Block lists prevent alert spam in Google Chat. Routine updates are logged silently; critical keywords trigger instant alarms. |
| 📖 **Inline PDF Viewer** | A customized UI embedded directly within Frappe Docs to read circulars without ever leaving the system. |
| 🔐 **Role-Based Access Control** | Ships with native `RSS Admin` and `RSS User` standard roles out-of-the-box for surgical permissions. |

---

## 🛠️ Server Prerequisites (Bare-Metal OS)

Because this application performs heavy image extraction and OCR on PDFs, the underlying Ubuntu/Debian server **must have Tesseract OCR installed** before deploying the Frappe app.

Run this on your physical server:

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng libmupdf-dev
```

---

## 🚀 Step-by-Step Installation

Once the OS prerequisites are met, install the app onto your Frappe Bench using the standard workflow:

**Step 1: Download the app to your bench**

```bash
bench get-app https://github.com/gondalaprasad/FrappeRSS.git
```

**Step 2: Install the app on your production site**

```bash
bench --site your_production_site.com install-app rssfeeds
```

> **Note:** The custom `install.py` script will automatically execute during this step to dynamically increase your Frappe system's Max File Size limit to **100MB**.

---

## 💻 Main Commands & Configuration

To ensure optimal performance for heavy background AI processing, we highly recommend adjusting your Frappe configuration:

**Increase Background Workers:**

```bash
bench set-config background_workers 5
bench restart
```

**Manual Background Job Trigger (For Debugging):**

If you need to manually force the RSS fetcher to run without waiting for the scheduler:

```bash
bench execute rssfeeds.rss_feeds.doctype.rss_feed_source.rss_feed_source.fetch_all_feeds
```

---

## 📤 Push to GitHub

After making changes to your documentation:

```bash
git add README.md
git commit -m "Docs: Upgraded README with advanced documentation and star graphs"
git push origin main
```

---

<div align="center">

Built with ❤️ for the **Frappe Community**

[![LinkedIn](https://img.shields.io/badge/Connect%20on%20LinkedIn-gondalaprasad-0A66C2?logo=linkedin&logoColor=white)](https://www.linkedin.com/in/gondalaprasad/)

</div>