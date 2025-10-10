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

# --- 2. Kernlogik-Funktionen (mit Caching für Performance) ---

@st.cache_data(ttl=3600) # Cache für 1 Stunde
def analyze_infrastructure(website_url: str) -> dict:
    """
    Führt eine universelle, zweistufige forensische Analyse durch.
    """
    results = {
        "tag_management_system": "Keines",
        "gtm_id": None,
        "hardcoded_tools": [],
        "gtm_tools": [],
        "gtm_events": []
    }
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    try:
        response = requests.get(website_url, timeout=15, headers=headers)
        response.raise_for_status()
        html_content = response.text
    except requests.RequestException:
        st.error(f"Fehler: Die Webseite unter {website_url} konnte nicht geladen werden. Bitte prüfen Sie die URL.")
        return None

    # Schritt A: TMS-Identifikation
    for name, signature in TAG_MANAGERS.items():
        if re.search(signature, html_content, re.IGNORECASE):
            results["tag_management_system"] = name
            break

    # Schritt B: Allgemeiner HTML-Scan nach hartcodierten Tools
    for tech_name, data in TECHNOLOGY_SIGNATURES.items():
        for signature in data["signatures"]:
            match = re.search(f".*{signature}.*", html_content, re.IGNORECASE)
            if match and not any(d['name'] == tech_name for d in results['hardcoded_tools']):
                results['hardcoded_tools'].append({
                    "name": tech_name, "confidence": data["confidence"], "proof": match.group(0).strip()
                })

    # Schritt C: GTM-Tiefen-Analyse
    if results["tag_management_system"] == "Google Tag Manager":
        gtm_match = re.search(r'(GTM-[A-Z0-9]+)', html_content)
        if gtm_match:
            results["gtm_id"] = gtm_match.group(1)
            gtm_url = f"https://www.googletagmanager.com/gtm.js?id={results['gtm_id']}"
            try:
                gtm_response = requests.get(gtm_url, timeout=10, headers=headers)
                if gtm_response.status_code == 200:
                    gtm_content = gtm_response.text
                    lines = gtm_content.splitlines()
                    for tech_name, data in TECHNOLOGY_SIGNATURES.items():
                        for signature in data["signatures"]:
                            for line in lines:
                                if re.search(signature, line, re.IGNORECASE) and not any(d['name'] == tech_name for d in results['gtm_tools']):
                                    results["gtm_tools"].append({"name": tech_name, "confidence": data["confidence"], "proof": line.strip()})
                                    break
                            else: continue
                            break
                    for event in BUSINESS_EVENTS:
                        pattern = re.compile(f"['\"]event['\"]:\\s*['\"]{event}['\"]", re.IGNORECASE)
                        for line in lines:
                            if pattern.search(line) and not any(d['name'] == event for d in results['gtm_events']):
                                results["gtm_events"].append({"name": event, "proof": line.strip()})
                                break
            except requests.RequestException:
                pass
    return results

@st.cache_data(ttl=3600) # Cache für 1 Stunde
def scrape_website_text(base_url: str) -> str:
    """
    Sammelt den Text von der Startseite und wichtigen Unterseiten.
    """
    subpage_paths = ['/', '/ueber-uns', '/about', '/about-us', '/services', '/leistungen', '/karriere', '/jobs']
    total_text = ""
    processed_urls = set()
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    for path in subpage_paths:
        url_to_scrape = urljoin(base_url, path)
        if url_to_scrape in processed_urls: continue
        try:
            response = requests.get(url_to_scrape, timeout=10, headers=headers)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
                    element.decompose()
                text = soup.get_text(separator=' ', strip=True)
                total_text += f"\n\n--- Inhalt von {url_to_scrape} ---\n\n{text}"
                processed_urls.add(url_to_scrape)
        except requests.RequestException:
            continue
    return total_text.strip() if total_text else "Es konnte kein relevanter Text von der Webseite extrahiert werden."

def generate_dossier(infra_data: dict, website_text: str) -> str:
    """
    Erstellt das strategische Dossier mit der Google Gemini API.
    """
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
    except (KeyError, FileNotFoundError):
        st.error("GEMINI_API_KEY nicht in den Streamlit Secrets gefunden. Bitte fügen Sie ihn hinzu.")
        return None

    evidence = {
        "Forensische Analyse": infra_data,
        "Webseiten-Inhalt": website_text[:40000]
    }
    
    # Der finale "Vorstands-Analyse"-Prompt
    prompt = f"""
Du bist ein Partner bei einer Top-Management-Beratung (z.B. McKinsey, BCG) mit Spezialisierung auf digitale Transformation und datengetriebene Geschäftsmodelle. Deine Aufgabe ist es, ein strategisches Dossier für eine Vorstandssitzung zu erstellen.

Beweismittel: {json.dumps(evidence, indent=2, ensure_ascii=False)}

Dein Auftrag: Erstelle ein strategisches Dossier. Sei präzise, direkt und begründe jeden Punkt mit klaren Geschäftsrisiken oder -chancen.

**Berichtsstruktur (Markdown):**

# Strategisches Dossier: Digitale Positionierung

---

## Teil 1: Firmenprofil & strategische Positionierung
- **Unternehmen:** [Leite den Firmennamen aus dem Inhalt ab]
- **Kernbotschaft:** [Fasse die Hauptbotschaft oder den Slogan der Webseite in einem Satz zusammen]
- **Tätigkeit & Branche:** [Beschreibe in 2-3 Sätzen detailliert, was die Firma macht und in welcher Branche sie tätig ist]
- **Zielgruppe:** [Leite aus der Sprache und den Angeboten ab, wer die typischen Kunden sind]

---

## Teil 2: Forensischer Digital-Audit
**Gesamteinschätzung (Executive Summary):**
[Bewerte die digitale Reife von 1-10 und formuliere eine prägnante Management-Zusammenfassung (3-4 Sätze) über die allgemeine Situation. Berücksichtige dabei die Nutzung eines TMS versus hartcodierter Skripte.]

### Audit der Kernkompetenzen
**Anweisung:** Bewerte JEDE der folgenden Kategorien.

**1. Daten-Grundlage & Tag Management**
- **Status:** [{evidence['Forensische Analyse']['tag_management_system']}]

**2. Data & Analytics**
- **Gefundene Tools:** [Liste gefundene Tools. Wenn leer: "Keine"]
- **Status & Implikation:** [Wenn keine Tools gefunden wurden, schreibe: "🔴 Lücke: Dem Unternehmen fehlt die grundlegendste Fähigkeit, das Nutzerverhalten zu analysieren. Entscheidungen werden 'blind' getroffen."]
- **Reifegrad (1-5):** [Bewerte von 1-5]

**3. Advertising & Kundengewinnung**
- **Gefundene Tools:** [Liste gefundene Tools]
- **Status & Implikation:** [Wenn keine Tools/Events gefunden wurden, schreibe: "🔴 Lücke: Es gibt keine technische Grundlage, um den Erfolg von Werbeausgaben zu messen (ROAS). Investitionen sind nicht messbar."]
- **Reifegrad (1-5):** [Bewerte von 1-5]

**4. Marketing Automation & CRM**
- **Gefundene Tools:** [Liste gefundene Tools]
- **Status & Implikation:** [Wenn keine Tools gefunden wurden, schreibe: "🔴 Lücke: Prozesse zur Lead-Pflege und Kundenbindung sind nicht automatisiert und skalierbar."]
- **Reifegrad (1-5):** [Bewerte von 1-5]

---

## Teil 3: Strategische Auswertung & Handlungsbedarf
**✅ Operative Stärken:**
- **Stärke:** [Nenne die größte Stärke]
- **Beobachtung:** [Der technische Fakt.]
- **Strategische Implikation:** [Erkläre in 2-3 Sätzen die positive Auswirkung auf das Geschäft.]

**⚠️ Strategische Risiken (Handlungsbedarf):**
- **Risiko:** [Nenne die größte Schwäche. Bewerte hartcodierte Skripte als hohes Risiko.]
- **Beobachtung:** [Der technische Fakt oder die Lücke.]
- **Konkretes Geschäftsrisiko:** [Erkläre in 2-3 Sätzen die negativen Auswirkungen auf das Geschäft.]

## Teil 4: Empfohlener Strategischer Fahrplan
**💡 Quick Wins (Sofortmaßnahmen mit hohem ROI):**
- [Liste hier 1-2 konkrete, schnell umsetzbare Maßnahmen auf.]

**🚀 Unser strategischer Vorschlag (Phasenplan):**
- **Phase 1: Fundament schaffen (1-3 Monate):** [Beschreibe den wichtigsten ersten Schritt, um die größte Lücke zu schließen.]
- **Phase 2: Potenzial entfalten (3-9 Monate):** [Beschreibe den nächsten logischen Schritt.]
- **Langfristige Vision:** [Beschreibe das Endziel in einem Satz.]
"""
    
    try:
        model = genai.GenerativeModel('gemini-flash-latest')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"Fehler bei der Kommunikation mit der Gemini API: {e}")
        return None

# --- 3. Streamlit Benutzeroberfläche ---

st.title("🚀 Strategie-Dossier Pro")
st.markdown("Geben Sie eine URL ein, um eine tiefgehende, forensische Analyse der digitalen Infrastruktur zu erstellen – optimiert für das Management.")

url = st.text_input("Geben Sie die vollständige URL der Webseite ein", "https://www.google.com")

if 'dossier' not in st.session_state:
    st.session_state.dossier = None
if 'infra_data' not in st.session_state:
    st.session_state.infra_data = None

if st.button("Analyse starten", type="primary"):
    if not url or not re.match(r'http(s)?://', url):
        st.error("Bitte geben Sie eine gültige, vollständige URL ein (z.B. https://www.beispiel.de).")
    else:
        with st.spinner("Führe forensische Analyse durch... Dieser Vorgang kann bis zu 60 Sekunden dauern..."):
            st.session_state.infra_data = analyze_infrastructure(url)
            if st.session_state.infra_data:
                website_text = scrape_website_text(url)
