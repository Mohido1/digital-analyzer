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
st.set_page_config(page_title="Strategie-Dossier Pro", page_icon="🚀", layout="wide")

TECHNOLOGY_SIGNATURES = {
    "Google Analytics 4": {"signatures": [r"G-[A-Z0-9]+"], "confidence": "high"},
    "Google Analytics (Universal)": {"signatures": [r"UA-\d+-\d+"], "confidence": "high"},
    "Google Ads": {"signatures": [r"AW-\d+", r"google_ad_conversion_id"], "confidence": "high"},
    "Meta Pixel": {"signatures": [r"fbq\('init'"], "confidence": "high"},
    "LinkedIn Insight Tag": {"signatures": [r"linkedin_data_partner_id"], "confidence": "high"},
    "Hotjar": {"signatures": [r"hj\('event'"], "confidence": "high"},
    "HubSpot": {"signatures": [r"js\.hs-scripts\.com", r"_hsq\.push"], "confidence": "high"},
    "Tealium": {"signatures": [r"tags\.tiqcdn\.com"], "confidence": "high"},
    "Adobe Launch": {"signatures": [r"assets\.adobedtm\.com"], "confidence": "high"},
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
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
    except (KeyError, FileNotFoundError):
        st.error("GEMINI_API_KEY nicht in den Streamlit Secrets gefunden. Bitte fügen Sie ihn hinzu.")
        return None
    
    evidence = {
        "Forensische Analyse": infra_data,
        "Webseiten-Inhalt": website_text[:10000]
    }
    evidence_json = json.dumps(evidence, indent=2, ensure_ascii=False)

    prompt_template = """
Du bist ein Partner bei einer Top-Management-Beratung (z.B. McKinsey, BCG) mit Spezialisierung auf digitale Transformation. Deine Aufgabe ist es, ein strategisches Dossier zu erstellen.
Beweismittel: {}
Dein Auftrag: Erstelle einen strategischen Bericht. Sei präzise, direkt und begründe jeden Punkt.
**Berichtsstruktur (Markdown):**
### Teil 1: Firmenprofil
- **Unternehmen:** """ + company_name + """
- **Kernbotschaft:** [Fasse die Hauptbotschaft der Webseite in einem Satz zusammen]
- **Tätigkeit & Branche:** [Beschreibe in 2-3 Sätzen, was die Firma macht]
- **Zielgruppe:** [Leite ab, wer die typischen Kunden sind]
---
### Teil 2: Forensischer Digital-Audit
**Gesamteinschätzung (Executive Summary):**
[Bewerte die digitale Reife von 1-10 und formuliere eine Management-Zusammenfassung.]
---
#### Strategische Auswertung & Handlungsbedarf
**✅ Operative Stärken:**
* **Stärke:** [Nenne die größte Stärke]
    * **Beobachtung:** [Der technische Fakt.]
    * **Strategische Implikation:** [Erkläre die positive Auswirkung auf das Geschäft.]
**⚠️ Strategische Risiken (Handlungsbedarf):**
* **Risiko:** [Nenne die größte Schwäche]
    * **Beobachtung:** [Der technische Fakt oder die Lücke.]
    * **Konkretes Geschäftsrisiko:** [Erkläre die negativen Auswirkungen auf das Geschäft.]
---
#### Empfohlener Strategischer Fahrplan
**🚀 Unser strategischer Vorschlag (Phasenplan):**
* **Phase 1: Fundament schaffen (1-3 Monate):** [Beschreibe den wichtigsten ersten Schritt.]
* **Phase 2: Potenzial entfalten (3-9 Monate):** [Beschreibe den nächsten logischen Schritt.]
"""
    
    prompt = prompt_template.format(evidence_json)

    try:
        # KORRIGIERTE ZEILE
        model = genai.GenerativeModel('gemini-flash-latest')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"Fehler bei der Kommunikation mit der Gemini API: {e}")
        return None

# --- 3. Streamlit Benutzeroberfläche ---
st.title("🚀 Digital Maturity & Strategy Analyzer")
url = st.text_input("Geben Sie die vollständige URL der Webseite ein", help="z.B. https://www.beispiel.de")

if 'dossier' not in st.session_state: st.session_state.dossier = None
if 'infra_data' not in st.session_state: st.session_state.infra_data = None

if st.button("Analyse starten", type="primary"):
    st.session_state
