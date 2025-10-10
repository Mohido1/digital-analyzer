from Wappalyzer import Wappalyzer, WebPage
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
    "Google Analytics 4": {"signatures": [r"G-[A-Z0-9]+"], "confidence": "high"},
    "Google Analytics (Universal)": {"signatures": [r"UA-\d+-\d+"], "confidence": "high"},
    "Adobe Analytics": {"signatures": ["s_code.js", "AppMeasurement.js"], "confidence": "high"},
    "Matomo / Piwik": {"signatures": ["matomo.js", "piwik.js", "_paq.push"], "confidence": "high"},
    "Plausible Analytics": {"signatures": ["plausible.io/js/plausible.js"], "confidence": "high"},

    # Advertising & Retargeting
    "Google Ads": {"signatures": [r"AW-\d+", r"google_ad_conversion_id"], "confidence": "high"},
    "Google Marketing Platform (Floodlight)": {"signatures": ["fls.doubleclick.net", "doubleclick.net/activity"], "confidence": "high"},
    "Meta Pixel": {"signatures": [r"fbq\('init'"], "confidence": "high"},
    "LinkedIn Insight Tag": {"signatures": [r"linkedin_data_partner_id"], "confidence": "high"},
    "Twitter Ads": {"signatures": [r"twq\('init'", "static.ads-twitter.com"], "confidence": "high"},
    "Pinterest Tag": {"signatures": [r"pintrk\('init'"], "confidence": "high"},
    "TikTok Pixel": {"signatures": ["tiktok-pc-analytics", r"ttq\('init'"], "confidence": "high"},
    "Microsoft Advertising (Bing)": {"signatures": ["bat.bing.com"], "confidence": "high"},
    "Criteo": {"signatures": ["criteo_id", "static.criteo.net"], "confidence": "high"},
    "AdRoll": {"signatures": ["adroll_adv_id"], "confidence": "high"},
    "Taboola": {"signatures": ["trc.taboola.com"], "confidence": "high"},
    "Outbrain": {"signatures": ["outbrain.com/pixel"], "confidence": "high"},

    # DSPs & Programmatic
    "The Trade Desk": {"signatures": ["insight.adsrvr.org"], "confidence": "high"},
    "Xandr (AppNexus)": {"signatures": ["anj.adnxs.com", "ib.adnxs.com"], "confidence": "high"},
    "MediaMath": {"signatures": ["mathads.com"], "confidence": "high"},
    "Adform": {"signatures": ["track.adform.net"], "confidence": "high"},

    # Customer Experience & CRO
    "Hotjar": {"signatures": [r"hj\('event'", "static.hotjar.com"], "confidence": "high"},
    "Microsoft Clarity": {"signatures": ["clarity.ms"], "confidence": "high"},
    "FullStory": {"signatures": ["fullstory.com/fs.js"], "confidence": "high"},
    "Optimizely": {"signatures": ["optimizely.com/js"], "confidence": "high"},
    "Visual Website Optimizer (VWO)": {"signatures": ["dev.vwo.com"], "confidence": "high"},
    "Google Optimize": {"signatures": [r"GTM-[A-Z0-9]+", "optimize.js"], "confidence": "high"}, # Often linked to GTM

    # Marketing Automation & CRM
    "HubSpot": {"signatures": [r"js\.hs-scripts\.com", r"_hsq\.push"], "confidence": "high"},
    "Salesforce Pardot": {"signatures": ["pi.pardot.com"], "confidence": "high"},
    "Marketo": {"signatures": ["munchkin.js", "Munchkin.init"], "confidence": "high"},
    "ActiveCampaign": {"signatures": ["ac_track.js"], "confidence": "high"},
    "Intercom": {"signatures": ["widget.intercom.io"], "confidence": "high"},

    # Consent Management Platforms (CMP)
    "Cookiebot": {"signatures": ["consent.cookiebot.com", "Cybot"], "confidence": "high"},
    "Usercentrics": {"signatures": ["app.usercentrics.eu"], "confidence": "high"},
    "OneTrust": {"signatures": ["cdn.cookielaw.org", "OneTrust.js"], "confidence": "high"},

    # E-Commerce Platforms
    "Shopify": {"signatures": ["Shopify.theme", "cdn.shopify.com"], "confidence": "high"},
    "Magento": {"signatures": ["mage-init", "Magento_Theme"], "confidence": "high"},
    "WooCommerce": {"signatures": ["/wp-content/plugins/woocommerce"], "confidence": "high"},

    # Customer Data Platforms (CDP)
    "Segment": {"signatures": ["cdn.segment.com"], "confidence": "high"},
    # Tealium wird bereits durch den Tag Manager erkannt

    # Cloud & Content Delivery (generische Signale)
    "Amazon Web Services (AWS)": {"signatures": ["amazonaws.com"], "confidence": "medium"},
    "Google Cloud Platform (GCP)": {"signatures": ["storage.googleapis.com"], "confidence": "medium"},
    "Cloudflare": {"signatures": ["cdn-cgi/scripts"], "confidence": "medium"},
    "Microsoft Azure": {"signatures": ["azureedge.net"], "confidence": "medium"},
}
TAG_MANAGERS = {
    "Google Tag Manager": r"googletagmanager\.com/gtm\.js",
    "Tealium": r"tags\.tiqcdn\.com",
    "Adobe Launch": r"assets\.adobedtm\.com",
    "Ensighten": r"ensighten\.com",
    "Segment": r"cdn\.segment\.com" # Segment kann auch als Tag Manager agieren
}
BUSINESS_EVENTS = [
    # --- E-Commerce & Retail ---
    'purchase',
    'add_to_cart',
    'remove_from_cart',
    'begin_checkout',
    'add_payment_info',
    'add_shipping_info',
    'view_item',
    'view_item_list',
    'select_item',
    'add_to_wishlist',
    'view_cart',
    'refund',
    'view_promotion',
    'select_promotion',

    # --- Lead Generation & B2B ---
    'generate_lead', # GA4 Standard
    'form_submission',
    'lead',
    'sign_up',
    'request_quote',
    'schedule_demo',
    'contact',
    'trial_start',
    'download',
    'file_download',
    'submit_form',

    # --- SaaS & Subscription ---
    'subscribe',
    'unsubscribe',
    'subscription_start',
    'subscription_cancel',
    'login',
    'logout',
    'upgrade_plan',
    'downgrade_plan',
    'feature_use',

    # --- Allgemeines User Engagement ---
    'search',
    'share',
    'click',
    'view_search_results',
    'video_start',
    'video_progress',
    'video_complete',
    'scroll_depth',
    'page_view', # Obwohl implizit, explizit suchen kann wertvoll sein

    # --- Travel & Hospitality ---
    'search_flight',
    'search_hotel',
    'select_room',
    'book_trip',
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
def analyze_with_wappalyzer(website_url: str):
    """
    Analysiert die Webseite mit der Wappalyzer-Bibliothek auf eine breite Palette von Technologien.
    """
    try:
        wappalyzer = Wappalyzer.latest()
        webpage = WebPage.new_from_url(website_url, verify=False) # verify=False, um SSL-Fehler zu ignorieren
        technologies = wappalyzer.analyze_with_versions(webpage)
        # Bereinige das Ergebnis für eine bessere Lesbarkeit
        tech_names = list(technologies.keys())
        return tech_names
    except Exception:
        return [] # Gib eine leere Liste zurück, wenn die Analyse fehlschlägt
def generate_dossier(infra_data: dict, website_text: str, company_name: str):
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
    except (KeyError, FileNotFoundError):
        st.error("GEMINI_API_KEY nicht in den Streamlit Secrets gefunden.")
        return None
    
    evidence = {
        "Unternehmen": company_name,
        "Forensische Analyse": infra_data,
        # LIMIT MASSIV ERHÖHT: Wir erlauben jetzt bis zu 200.000 Zeichen
        "Webseiten-Inhalt": website_text[:200000]
    }
    evidence_json = json.dumps(evidence, indent=2, ensure_ascii=False)

    prompt_template = """
[Hier fügen Sie Ihren finalen, detaillierten KI-Prompt ("Vorstands-Analyse") ein]
"""
    
    prompt = prompt_template.format(evidence_json)

    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"Fehler bei der Kommunikation mit der Gemini API: {e}")
        return None

    prompt_template = """
Du bist ein Partner bei einer Top-Management-Beratung (z.B. McKinsey, BCG) mit Spezialisierung auf digitale Transformation.
Du erhältst DREI Arten von Daten: Eine forensische MarTech-Analyse, eine allgemeine Technologie-Analyse von Wappalyzer und den Webseiten-Inhalt.

**Beweismittel:** {}

**Dein Auftrag:** Erstelle einen strategischen Bericht. Kombiniere alle drei Datenquellen.
**WICHTIGE ANWEISUNG FÜR DIE WAPPALYZER-DATEN:** Extrahiere aus der rohen Wappalyzer-Liste NUR die strategisch relevanten Technologien. Ignoriere unwichtige JavaScript-Bibliotheken, Widgets oder Schriftarten. Konzentriere dich auf die folgenden Kategorien, falls vorhanden:
- CMS (z.B. WordPress, Contentful)
- E-Commerce-Plattform (z.B. Shopify, Magento)
- Programmiersprache & Frameworks (z.B. PHP, React, Node.js)
- Web Server (z.B. Nginx, Apache)
- CDN (z.B. Cloudflare)
- Datenbanken

**Berichtsstruktur (Markdown):**

### Teil 1: Firmenprofil & strategische Positionierung
- **Unternehmen:** """ + company_name + """
- **Kernbotschaft:** [Fasse die Hauptbotschaft zusammen]
- **Tätigkeit & Branche:** [Beschreibe, was die Firma macht]
- **Zielgruppe:** [Leite ab, wer die Kunden sind]

---

### Teil 2: Technologisches Fundament
**Anweisung:** Erstelle eine Übersicht der wichtigsten, von dir gefilterten Technologien.

* **Content Management / Shop-System:** [Nenne hier das relevante Tool aus der Wappalyzer-Liste. Wenn keines, schreibe "Unbekannt".]
* **Programmier-Framework:** [Nenne hier das relevante Tool aus der Wappalyzer-Liste. Wenn keines, schreibe "Unbekannt".]
* **Web Server / CDN:** [Nenne hier das relevante Tool aus der Wappalyzer-Liste. Wenn keines, schreibe "Unbekannt".]

---

### Teil 3: Forensischer Digital-Audit
**Gesamteinschätzung (Executive Summary):**
[Bewerte die digitale Reife basierend auf ALLEN Beweismitteln.]

---
#### Strategische Auswertung & Handlungsbedarf
**✅ Operative Stärken:**
* **Stärke:** [Nenne die größte Stärke und begründe sie mit den Beweismitteln.]

**⚠️ Strategische Risiken (Handlungsbedarf):**
* **Risiko:** [Nenne die größte Schwäche und das konkrete Geschäftsrisiko.]

---
#### Empfohlener Strategischer Fahrplan
**🚀 Unser strategischer Vorschlag (Phasenplan):**
* **Phase 1: Fundament schaffen (1-3 Monate):** [Beschreibe den wichtigsten ersten Schritt.]
* **Phase 2: Potenzial entfalten (3-9 Monate):** [Beschreibe den nächsten logischen Schritt.]
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
    swith st.spinner("Führe universelle forensische Analyse durch... (kann bis zu 90s dauern)"):
        infra_data_result = analyze_infrastructure(url)
        wappalyzer_result = analyze_with_wappalyzer(url)

        if infra_data_result:
            st.session_state.infra_data = infra_data_result
            # NEU: Wappalyzer-Ergebnisse zu den Beweismitteln hinzufügen
            st.session_state.infra_data['wappalyzer_technologies'] = wappalyzer_result

            extracted_info = tldextract.extract(url)
            company_name = extracted_info.domain.capitalize()
            website_text = scrape_website_text(url)
            st.session_state.dossier = generate_dossier(st.session_state.infra_data, website_text, company_name)
            st.success("Analyse abgeschlossen!")
        else:
            st.warning("Die Analyse wurde abgebrochen...")

if st.session_state.dossier:
    st.markdown("---")
    st.subheader(f"Analyse-Ergebnisse für: {urlparse(url).netloc}")
    st.markdown(st.session_state.dossier)
    with st.expander("🔍 Detaillierte Beweismittel anzeigen (JSON)"):
        st.json(st.session_state.infra_data)
    if st.button("📋 Bericht in die Zwischenablage kopieren"):
        pyperclip.copy(st.session_state.dossier)
        st.success("Bericht in die Zwischenablage kopiert!")
