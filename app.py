import streamlit as st
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import json
import re
from urllib.parse import urljoin, urlparse
import tldextract
import pyperclip

# --- 1. Konstanten und Konfiguration ---

st.set_page_config(page_title="Digital Maturity Analyzer", page_icon="🚀", layout="wide")

TECHNOLOGY_SIGNATURES = {
    # Analytics & Tracking
    "Google Analytics 4": {"signatures": [r"G-[A-Z0-9]+"], "confidence": "high"},
    "Google Analytics (Universal)": {"signatures": [r"UA-\d+-\d+"], "confidence": "high"},
    # Advertising & Retargeting
    "Google Ads": {"signatures": [r"AW-\d+", r"google_ad_conversion_id"], "confidence": "high"},
    "Meta Pixel": {"signatures": [r"fbq\('init'"], "confidence": "high"},
    "LinkedIn Insight Tag": {"signatures": [r"linkedin_data_partner_id"], "confidence": "high"},
    # Customer Experience & CRO
    "Hotjar": {"signatures": [r"hj\('event'"], "confidence": "high"},
    # Marketing Automation & CRM
    "HubSpot": {"signatures": [r"js\.hs-scripts\.com", r"_hsq\.push"], "confidence": "high"},
    # Cloud & Content Delivery
    "Cloudflare": {"signatures": [r"cdn-cgi/scripts"], "confidence": "medium"},
}

TAG_MANAGERS = {
    "Google Tag Manager": r"googletagmanager\.com/gtm\.js",
    "Tealium": r"tags\.tiqcdn\.com",
    "Adobe Launch": r"assets\.adobedtm\.com"
}

BUSINESS_EVENTS = ['purchase', 'add_to_cart', 'begin_checkout', 'form_submission', 'lead', 'sign_up']

# --- 2. Kernlogik-Funktionen ---

@st.cache_data(ttl=600)
def analyze_infrastructure(website_url: str):
    results = {"tag_management_system": "Keines", "gtm_id": None, "hardcoded_tools": [], "gtm_tools": [], "gtm_events": []}
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'}
    try:
        response = requests.get(website_url, timeout=15, headers=headers)
        response.raise_for_status()
        html_content = response.text
    except requests.RequestException as e:
        st.error(f"Fehler beim Laden der Webseite: {e}")
        return None

    for name, signature in TAG_MANAGERS.items():
        if re.search(signature, html_content, re.IGNORECASE):
            results["tag_management_system"] = name
            break
    
    for tech_name, data in TECHNOLOGY_SIGNATURES.items():
        for signature in data["signatures"]:
            match = re.search(signature, html_content, re.IGNORECASE)
            if match and not any(d['name'] == tech_name for d in results['hardcoded_tools']):
                results['hardcoded_tools'].append({"name": tech_name, "confidence": data["confidence"], "proof": match.group(0).strip()})
                break 

    if results["tag_management_system"] == "Google Tag Manager":
        gtm_match = re.search(r'(GTM-[A-Z0-9]+)', html_content, re.IGNORECASE)
        if gtm_match:
            results["gtm_id"] = gtm_match.group(1)
            gtm_url = f"https://www.googletagmanager.com/gtm.js?id={results['gtm_id']}"
            try:
                gtm_response = requests.get(gtm_url, timeout=10, headers=headers)
                if gtm_response.status_code == 200:
                    gtm_content = gtm_response.text
                    for tech_name, data in TECHNOLOGY_SIGNATURES.items():
                        for signature in data["signatures"]:
                            match = re.search(signature, gtm_content, re.IGNORECASE)
                            if match and not any(d['name'] == tech_name for d in results['gtm_tools']):
                                results["gtm_tools"].append({"name": tech_name, "confidence": data["confidence"], "proof": match.group(0).strip()})
                                break
                    for event in BUSINESS_EVENTS:
                        pattern = re.compile(f"['\"]event['\"]:\\s*['\"]{event}['\"]", re.IGNORECASE)
                        match = pattern.search(gtm_content)
                        if match and not any(d['name'] == event for d in results['gtm_events']):
                            results["gtm_events"].append({"name": event, "proof": match.group(0).strip()})
            except requests.RequestException: pass
    return results

@st.cache_data(ttl=600)
def scrape_website_text(base_url: str):
    subpage_paths = ['/', '/ueber-uns', '/about', '/services', '/leistungen', '/karriere', '/jobs']
    total_text = ""
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'}
    for path in subpage_paths:
        try:
            url_to_scrape = urljoin(base_url.rstrip('/') + '/', path.lstrip('/'))
            response = requests.get(url_to_scrape, timeout=10, headers=headers)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
                    element.decompose()
                total_text += soup.get_text(separator=' ', strip=True) + " "
        except requests.RequestException: continue
    return total_text.strip() if total_text else "Es konnte kein relevanter Text von der Webseite extrahiert werden."

def generate_dossier(infra_data: dict, website_text: str, company_name: str):
    prompt = f"""
    Du bist ein Senior Enterprise MarTech Architect. Deine Aufgabe ist es, einen tiefgehenden, forensischen Audit für unser Sales-Team zu erstellen.
    Beweismittel: {json.dumps(infra_data, indent=2, ensure_ascii=False)}
    Webseiten-Inhalt: {website_text[:10000]}

    Dein Auftrag: Erstelle einen forensischen Bericht. Halte dich exakt an die folgende Berichtsstruktur.

    **Berichtsstruktur (Markdown):**

    ### Teil 1: Firmenprofil
    - **Unternehmen:** {company_name}
    - **Kernbotschaft:** [Fasse die Hauptbotschaft oder den Slogan der Webseite in einem Satz zusammen]
    - **Tätigkeit & Branche:** [Beschreibe detailliert, was die Firma macht und in welcher Branche sie tätig ist]
    - **Zielgruppe:** [Leite aus der Sprache und den Angeboten ab, wer die typischen Kunden sind]

    ---

    ### Teil 2: Forensischer Digital-Audit
    **Gesamteinschätzung (Executive Summary):**
    [Bewerte die digitale Reife von 1-10 und formuliere eine prägnante Management-Zusammenfassung basierend auf den Beweisen. Unterscheide klar zwischen Tools im GTM und hartcodierten Tools.]

    ---
    
    #### Kategorie-Analyse
    **Anweisung:** Bewerte JEDE der folgenden Kategorien. Liste gefundene Tools oder schreibe explizit "🔴 Lücke: ...".
    1. **Tag Management & Daten-Grundlage**
    2. **Data & Analytics**
    3. **Advertising & Performance Marketing**
    4. **Marketing Automation & CRM**
    5. **Customer Experience & Personalisierung (CRO)**

    ---

    #### Strategische Auswertung für das Kundengespräch
    **✅ Stärken (Was gut läuft und warum):**
    * **Stärke 1:** [Nenne die größte Stärke]
        * **Beobachtung:** [Der technische Fakt.]
        * **Bedeutung (Intern):** [Die
