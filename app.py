import streamlit as st
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import json
import re
from urllib.parse import urljoin, urlparse

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
    "Cloudflare": {"signatures": [r"cdn-cgi/scripts"], "confidence": "medium"},
}

TAG_MANAGERS = {
    "Google Tag Manager": r"googletagmanager\.com/gtm\.js",
    "Tealium": r"tags\.tiqcdn\.com",
    "Adobe Launch": r"assets\.adobedtm\.com"
}

BUSINESS_EVENTS = ['purchase', 'add_to_cart', 'begin_checkout', 'form_submission', 'lead', 'sign_up']

# --- 2. Kernlogik-Funktionen ---

@st.cache_data(ttl=600) # Ergebnisse für 10 Minuten zwischenspeichern
def analyze_infrastructure(website_url: str) -> dict:
    results = {
        "tag_management_system": "Keines", "gtm_id": None,
        "hardcoded_tools": [], "gtm_tools": [], "gtm_events": []
    }
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'}
    
    try:
        response = requests.get(website_url, timeout=15, headers=headers)
        response.raise_for_status()
        html_content = response.text
    except requests.RequestException as e:
        st.error(f"Fehler beim Laden der Webseite: {e}")
        return None # Wichtig: Gib None zurück, um den Fehler zu signalisieren

    # Teil A: Allgemeine HTML-Analyse
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

    # Teil B: GTM-Tiefen-Analyse (KORRIGIERTE LOGIK)
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
def scrape_website_text(base_url: str) -> str:
    subpage_paths = ['/', '/ueber-uns', '/about', '/services', '/leistungen']
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

def generate_dossier(infra_data: dict, website_text: str) -> str:
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
    except (KeyError, FileNotFoundError):
        st.error("GEMINI_API_KEY nicht in den Streamlit Secrets gefunden. Bitte fügen Sie ihn hinzu.")
        return None
    
    evidence = { "Forensische Analyse": infra_data, "Webseiten-Inhalt": website_text[:40000] }
    prompt = f"""[Hier fügen Sie Ihren finalen, detaillierten "Vorstands-Analyse"-Prompt ein]""" # Platzhalter für Kürze
    
    try:
        model = genai.GenerativeModel('gemini-flash-latest')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"Fehler bei der Kommunikation mit der Gemini API: {e}")
        return None

# --- 3. Streamlit Benutzeroberfläche ---

st.title("🚀 Strategie-Dossier Pro")
st.markdown("Geben Sie eine URL ein, um eine tiefgehende, forensische Analyse der digitalen Infrastruktur zu erstellen.")

url = st.text_input("Geben Sie die vollständige URL der Webseite ein", "https://www.google.com")

if 'dossier' not in st.session_state:
    st.session_state.dossier = None
if 'infra_data' not in st.session_state:
    st.session_state.infra_data = None

if st.button("Analyse starten", type="primary"):
    # Alte Ergebnisse zurücksetzen
    st.session_state.dossier = None
    st.session_state.infra_data = None
    
    if not url or not (url.startswith('http://') or url.startswith('https://')):
        st.error("Bitte geben Sie eine gültige, vollständige URL ein (z.B. https://www.beispiel.de).")
    else:
        with st.spinner("Führe forensische Infrastruktur-Analyse durch..."):
            infra_data_result = analyze_infrastructure(url)
        
        # KORRIGIERTE LOGIK: Prüfen, ob die erste Analyse erfolgreich war
        if infra_data_result is not None:
            st.session_state.infra_data = infra_data_result
            with st.spinner("Extrahiere Webseiten-Inhalte und erstelle KI-Analyse..."):
                website_text = scrape_website_text(url)
                st.session_state.dossier = generate_dossier(st.session_state.infra_data, website_text)
            st.success("Analyse abgeschlossen!")
        else:
            # Fehlermeldung wurde bereits in analyze_infrastructure angezeigt
            st.warning("Die Analyse wurde aufgrund eines Fehlers beim Laden der Webseite abgebrochen.")

# Ergebnis-Anzeige (unverändert)
if st.session_state.dossier:
    st.markdown("---")
    # ... (Rest der UI bleibt exakt gleich wie in Ihrem Code)
