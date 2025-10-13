import streamlit as st
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import json
import re
from urllib.parse import urljoin, urlparse
import tldextract
import pyperclip

# --- 1. KONSTANTEN UND KONFIGURATION ---
st.set_page_config(page_title="Universal Forensic Auditor", page_icon="🌐", layout="wide")

TECHNOLOGY_SIGNATURES = {
    # Analytics & Tracking
    "Google Analytics 4": {"signatures": [r"G-[A-Z0-9]{6,}"], "confidence": "high"},
    "Google Analytics (Universal)": {"signatures": [r"UA-\d+-\d+"], "confidence": "high"},
    "Adobe Analytics": {"signatures": [r"s_code\.js", r"AppMeasurement\.js"], "confidence": "high"},
    "Matomo / Piwik": {"signatures": [r"matomo\.js", r"piwik\.js", r"_paq\.push"], "confidence": "high"},
    "Plausible Analytics": {"signatures": [r"plausible\.io/js/plausible\.js"], "confidence": "high"},
    "Mixpanel": {"signatures": [r"mixpanel-"], "confidence": "high"},
    "Amplitude": {"signatures": [r"amplitude\.com"], "confidence": "high"},

    # Advertising & Retargeting
    "Google Ads": {"signatures": [r"AW-\d+", r"google_ad_conversion_id"], "confidence": "high"},
    "Google Marketing Platform (Floodlight)": {"signatures": [r"fls\.doubleclick\.net", r"doubleclick\.net/activityi"], "confidence": "high"},
    "Meta Pixel": {"signatures": [r"fbq\('init'", r"facebook\.com/tr", r"_fbevents"], "confidence": "high"},
    "LinkedIn Insight Tag": {"signatures": [r"linkedin_data_partner_id", r"licdn\.com/insight\.min\.js"], "confidence": "high"},
    "Twitter Ads": {"signatures": [r"twq\('init'", r"static\.ads-twitter\.com"], "confidence": "high"},
    "Pinterest Tag": {"signatures": [r"pintrk\('init'"], "confidence": "high"},
    "TikTok Pixel": {"signatures": [r"tiktok-pc-analytics", r"ttq\('init'"], "confidence": "high"},
    "Microsoft Advertising (Bing)": {"signatures": [r"bat\.bing\.com"], "confidence": "high"},
    "Criteo": {"signatures": [r"criteo_id", r"static\.criteo\.net"], "confidence": "high"},
    "Taboola": {"signatures": [r"trc\.taboola\.com"], "confidence": "high"},
    "Outbrain": {"signatures": [r"outbrain\.com/pixel"], "confidence": "high"},

    # Affiliate Marketing
    "Impact Radius": {"signatures": [r"impact\.com"], "confidence": "high"},
    "Commission Junction (CJ)": {"signatures": [r"cjevent\.com"], "confidence": "high"},
    "Awin": {"signatures": [r"awin1\.com"], "confidence": "high"},
    "ShareASale": {"signatures": [r"shareasale\.com"], "confidence": "high"},

    # Customer Experience, CRO & Personalisierung
    "Hotjar": {"signatures": [r"hj\('event'", r"static\.hotjar\.com", r"window\.hj"], "confidence": "high"},
    "Microsoft Clarity": {"signatures": [r"clarity\.ms"], "confidence": "high"},
    "FullStory": {"signatures": [r"fullstory\.com/fs\.js"], "confidence": "high"},
    "Optimizely": {"signatures": [r"optimizely\.com/js", r"Optimizely\.push"], "confidence": "high"},
    "VWO (Visual Website Optimizer)": {"signatures": [r"dev\.vwo\.com"], "confidence": "high"},
    "Google Optimize": {"signatures": [r"optimize\.js"], "confidence": "high"},
    "AB Tasty": {"signatures": [r"try\.abtasty\.com"], "confidence": "high"},

    # Marketing Automation, CRM & Live Chat
    "HubSpot": {"signatures": [r"js\.hs-scripts\.com", r"_hsq\.push"], "confidence": "high"},
    "Salesforce Pardot": {"signatures": [r"pi\.pardot\.com"], "confidence": "high"},
    "Marketo": {"signatures": [r"munchkin\.js", r"Munchkin\.init"], "confidence": "high"},
    "ActiveCampaign": {"signatures": [r"ac_track\.js"], "confidence": "high"},
    "Intercom": {"signatures": [r"widget\.intercom\.io"], "confidence": "high"},
    "Drift": {"signatures": [r"js\.driftt\.com"], "confidence": "high"},
    "Zendesk Chat": {"signatures": [r"v2\.zopim\.com"], "confidence": "high"},

    # Social Proof & Reviews
    "Trustpilot": {"signatures": [r"widget\.trustpilot\.com"], "confidence": "high"},
    "Reviews.io": {"signatures": [r"widget\.reviews\.io"], "confidence": "high"},

    # Consent Management Platforms (CMP)
    "Cookiebot": {"signatures": [r"consent\.cookiebot\.com", r"Cybot"], "confidence": "high"},
    "Usercentrics": {"signatures": [r"app\.usercentrics\.eu"], "confidence": "high"},
    "OneTrust": {"signatures": [r"cdn\.cookielaw\.org", r"optanon\.blob\.core\.windows\.net"], "confidence": "high"},

    # E-Commerce & andere TMS
    "Shopify": {"signatures": [r"Shopify\.theme", r"cdn\.shopify\.com"], "confidence": "high"},
    "Magento": {"signatures": [r"mage-init"], "confidence": "high"},
    "WooCommerce": {"signatures": [r"/wp-content/plugins/woocommerce"], "confidence": "high"},
    "Segment": {"signatures": [r"cdn\.segment\.com"], "confidence": "high"},
    "Tealium": {"signatures": [r"tags\.tiqcdn\.com"], "confidence": "high"},
    "Adobe Launch": {"signatures": [r"assets\.adobedtm\.com"], "confidence": "high"},

    # Cloud & Content Delivery
    "Amazon Web Services (AWS)": {"signatures": [r"amazonaws\.com"], "confidence": "medium"},
    "Google Cloud Platform (GCP)": {"signatures": [r"storage\.googleapis\.com"], "confidence": "medium"},
    "Cloudflare": {"signatures": [r"cdn-cgi/scripts"], "confidence": "medium"},
    "Microsoft Azure": {"signatures": [r"azureedge\.net"], "confidence": "medium"},
}
TAG_MANAGERS = {
    "Google Tag Manager": r"googletagmanager\.com/gtm\.js",
    "Tealium": r"tags\.tiqcdn\.com",
    "Adobe Launch": r"assets\.adobedtm\.com",
    "Ensighten": r"ensighten\.com",
    "Segment": r"cdn\.segment\.com" # Segment kann auch als Tag Manager agieren
}
# ERSETZEN SIE DIE ALTE BUSINESS_EVENTS-LISTE MIT DIESER
BUSINESS_EVENTS = [
    # --- E-Commerce & Retail ---
    'purchase', 'add_to_cart', 'remove_from_cart', 'begin_checkout',
    'add_payment_info', 'add_shipping_info', 'view_item', 'view_item_list',
    'select_item', 'add_to_wishlist', 'view_cart', 'refund',
    'view_promotion', 'select_promotion', 'product_impression', 'checkout_progress',

    # --- Lead Generation & B2B ---
    'generate_lead', 'form_submission', 'lead', 'sign_up',
    'request_quote', 'schedule_demo', 'contact', 'trial_start', 'download',
    'file_download', 'submit_form', 'get_directions', 'call_now_button',

    # --- SaaS & Subscription ---
    'subscribe', 'unsubscribe', 'subscription_start', 'subscription_cancel',
    'login', 'logout', 'upgrade_plan', 'downgrade_plan', 'feature_use',
    'register', 'tutorial_begin', 'tutorial_complete',

    # --- Allgemeines User Engagement ---
    'search', 'share', 'click', 'view_search_results', 'video_start',
    'video_progress', 'video_complete', 'scroll_depth', 'page_view',
    'element_visibility', ' outbound_link_click', 'internal_link_click',

    # --- Travel & Hospitality ---
    'search_flight', 'search_hotel', 'select_room', 'book_trip', 'view_location',
]
# --- 2. KERNLOGIK-FUNKTIONEN (BACKEND) ---

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
    """
    Sammelt intelligent Text von der Startseite und den wichtigsten verlinkten Unterseiten.
    """
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'}
    total_text = ""
    urls_to_visit = {base_url}
    processed_urls = set()
    
    # Schlüsselwörter für relevante Unterseiten
    keywords = ['about', 'ueber-uns', 'company', 'unternehmen', 'services', 'leistungen', 
                'product', 'produkt', 'solution', 'loesung', 'karriere', 'jobs', 'contact', 'kontakt']

    try:
        # Zuerst die Startseite analysieren und Links sammeln
        response = requests.get(base_url, timeout=15, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            processed_urls.add(base_url)
            
            # Sammle Links von der Startseite
            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin(base_url, href)
                # Füge nur interne, relevante Links hinzu
                if urlparse(full_url).netloc == urlparse(base_url).netloc:
                    if any(keyword in full_url.lower() for keyword in keywords):
                        urls_to_visit.add(full_url)
    except requests.RequestException:
        pass # Ignoriere, wenn die Startseite nicht geladen werden kann

    # Besuche die gesammelten URLs und extrahiere den Text
    for url in list(urls_to_visit)[:10]: # Limitiere auf 10 URLs, um die Laufzeit zu begrenzen
        if url in processed_urls:
            continue
        try:
            response = requests.get(url, timeout=10, headers=headers)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
                    element.decompose()
                text = soup.get_text(separator=' ', strip=True)
                total_text += f"\n\n--- Inhalt von {url} ---\n\n{text}"
                processed_urls.add(url)
        except requests.RequestException:
            continue
            
    return total_text.strip() if total_text else "Es konnte kein relevanter Text von der Webseite extrahiert werden."
    
@st.cache_data(ttl=600)

def generate_dossier(infra_data: dict, website_text: str, company_name: str):
    """
    Erstellt den forensischen Audit mit Beweisführung mithilfe der Gemini API.
    Diese Version nutzt eine saubere und robuste Methode zur Prompt-Erstellung.
    """
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
    except (KeyError, FileNotFoundError):
        st.error("GEMINI_API_KEY nicht in den Streamlit Secrets gefunden.")
        return None

    # Alle dynamischen Daten werden hier sauber in einem Dictionary gebündelt
    evidence = {
        "Unternehmen": company_name,
        "Forensische MarTech-Analyse": infra_data,
        "Webseiten-Inhalt": website_text[:30000]
    }
    evidence_json = json.dumps(evidence, indent=2, ensure_ascii=False)

    prompt_template = """

Du bist ein Partner bei einer Top-Management-Beratung (z.B. McKinsey, BCG) mit Spezialisierung auf digitale Transformation und GMP.
Beweismittel: {}

**Zusätzliche Anweisung zur GMP-Analyse:** Wenn du in den Beweismitteln "Google Marketing Platform (Floodlight)" findest, musst du daraus folgende Schlussfolgerungen ziehen:
* **Campaign Manager 360 (CM360):** Die Nutzung ist **gesichert**.
* **Display & Video 360 (DV360):** Die Nutzung ist **sehr wahrscheinlich**.
* **Search Ads 360 (SA360):** Die Nutzung ist **möglich**.
Integriere diese abgeleiteten Tools in deine Kategorie-Analyse und markiere sie entsprechend.

**Dein Auftrag:** Erstelle einen strategischen Bericht basierend auf den Beweismitteln und den obigen Regeln. Halte dich exakt an die folgende Berichtsstruktur. Verwende in deiner finalen Antwort Emojis zur Visualisierung (z.B. 🟢 für Sicher, 🟡 für Wahrscheinlich, 🔴 für Lücke).

**Berichtsstruktur (Markdown):**

---
### **Teil 1: Firmenprofil & strategische Positionierung**
- **Unternehmen:** """ + company_name + """
- **Kernbotschaft:** [Fasse die Hauptbotschaft zusammen]
- **Tätigkeit & Branche:** [Beschreibe, was die Firma macht]
- **Unternehmensgröße (geschätzt):** [Schätze die Unternehmensgröße]
- **Zielgruppe:** [Leite ab, wer die Kunden sind]

---
### **Teil 2: Technologisches Fundament**
**Anweisung:** Erstelle eine Übersicht ALLER erkannten Technologien.
* **Content Management / Shop-System:** [Nenne die Tools. Wenn keines, schreibe "Unbekannt".]
* **Marketing Automation & CRM:** [Nenne die Tools.]
* **Analytics & User Experience:** [Nenne die Tools.]
* **Advertising & Performance:** [Nenne die Tools.]

---
### **Teil 3: Forensischer Digital-Audit**
**Gesamteinschätzung (Executive Summary):**
[Bewerte die digitale Reife basierend auf ALLEN Beweismitteln.]

---
#### **Detaillierte Kategorie-Analyse**
**Anweisung:** Bewerte JEDE der folgenden Kategorien.
**1. Tag Management & Daten-Grundlage**
* **Status:** [Bewerte hier ALLE gefundenen TMS.]

**2. Data & Analytics**
* **Status & Implikation:** [Bewerte die Situation. Wenn keine Tools gefunden wurden, schreibe: "**Lücke:** Es wird keine Web-Analyse betrieben."]
* **Reifegrad (1-5):**

**3. Advertising & Kundengewinnung**
* **Status & Implikation:** [Bewerte die Situation. Wenn keine Tools gefunden wurden, schreibe: "**Lücke:** Es findet kein Conversion-Tracking statt."]
* **Reifegrad (1-5):**

---
### **Teil 4: Strategische Auswertung**
**Stärken (Was gut läuft und warum):**
* **Stärke:** [Nenne die größte Stärke]
    * **Beobachtung:** [Beschreibe den technischen Fakt.]
    * **Beweis (Code-Snippet):** [Füge den "proof"-Schnipsel ein.]
    * **Bedeutung (Intern):** [Erkläre die strategische Bedeutung.]
   

**Schwächen (Wo das größte Potenzial liegt):**
* **Schwäche:** [Nenne die größte Schwäche]
    * **Beobachtung:** [Beschreibe den technischen Fakt oder die Lücken.]
    * **Beweis:** [Gib den Beweis an.]
    * **Konkretes Geschäftsrisiko:** [Erkläre das Geschäftsproblem.]
    * **Erläuterung für den Kunden:** [Formuliere eine Analogie.]

---
### **Teil 5: Empfohlener Strategischer Fahrplan**
**Quick Wins (Sofortmaßnahmen mit hohem ROI):**
* [Liste hier 1-2 konkrete, schnell umsetzbare Maßnahmen auf.]

**Unser strategischer Vorschlag (Phasenplan):**
* **Phase 1: Fundament schaffen (1-3 Monate):** [Beschreibe den wichtigsten ersten Schritt.]
* **Phase 2: Potenzial entfalten (3-9 Monate):** [Beschreibe den nächsten logischen Schritt.]

Am Ende sollen ausnahmslos ALLE erkannten Tools zu sehen sein. Alles was durch den gtm.js gefunden wurde.
"""

    prompt = prompt_template.format(evidence_json)

    try:
        model = genai.GenerativeModel('gemini-flash-latest')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"Fehler bei der Kommunikation mit der Gemini API: {e}")
        return None

# --- 3. STREAMLIT BENUTZEROBERFLÄCHE (FRONTEND) ---
st.title("🚀 Digital Maturity & Strategy Analyzer")
url = st.text_input("Geben Sie die vollständige URL der Webseite ein", help="z.B. https://www.beispiel.de")

if 'dossier' not in st.session_state:
    st.session_state.dossier = None
if 'infra_data' not in st.session_state:
    st.session_state.infra_data = None

if st.button("Analyse starten", type="primary"):
    st.session_state.dossier = None
    st.session_state.infra_data = None
    if not url or not (url.startswith('http://') or url.startswith('https://')):
        st.error("Bitte geben Sie eine gültige, vollständige URL ein (z.B. https://www.beispiel.de).")
    else:
        infra_data_result = None
        with st.spinner("Führe forensische Infrastruktur-Analyse durch..."):
            infra_data_result = analyze_infrastructure(url)
        
        if infra_data_result:
            st.session_state.infra_data = infra_data_result
            with st.spinner("Extrahiere Webseiten-Inhalte und erstelle KI-Analyse..."):
                extracted_info = tldextract.extract(url)
                company_name = extracted_info.domain.capitalize()
                website_text = scrape_website_text(url)
                st.session_state.dossier = generate_dossier(st.session_state.infra_data, website_text, company_name)
            st.success("Analyse abgeschlossen!")
        else:
            st.warning("Die Analyse wurde abgebrochen, da die Webseite nicht geladen werden konnte oder ein Fehler auftrat.")

if st.session_state.dossier:
    st.markdown("---")
    st.subheader(f"Analyse-Ergebnisse für: {urlparse(url).netloc}")
    st.markdown(st.session_state.dossier)
    with st.expander("🔍 Detaillierte Beweismittel anzeigen (JSON)"):
        st.json(st.session_state.infra_data)
    if st.button("📋 Bericht in die Zwischenablage kopieren"):
        pyperclip.copy(st.session_state.dossier)
        st.success("Bericht in die Zwischenablage kopiert!")
