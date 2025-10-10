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
        st.error("GEMINI_API_KEY nicht in den Streamlit Secrets gefunden.")
        return None
    
    evidence = {
        "Unternehmen": company_name,
        "Forensische Analyse": infra_data,
        "Webseiten-Inhalt": website_text[:15000]
    }
    evidence_json = json.dumps(evidence, indent=2, ensure_ascii=False)

    prompt_template = """
Du bist ein Partner bei einer Top-Management-Beratung (z.B. McKinsey, BCG) mit Spezialisierung auf digitale Transformation. Deine Aufgabe ist es, ein strategisches Dossier zu erstellen.

Beweismittel: {}

Dein Auftrag: Erstelle einen strategischen Bericht. Sei präzise, direkt und begründe jeden Punkt. Halte dich exakt an die folgende Berichtsstruktur.

**Berichtsstruktur (Markdown):**

### Teil 1: Firmenprofil
- **Unternehmen:** """ + company_name + """
- **Kernbotschaft:** [Fasse die Hauptbotschaft der Webseite in einem Satz zusammen]
- **Tätigkeit & Branche:** [Beschreibe in 2-3 Sätzen, was die Firma macht]
- **Zielgruppe:** [Leite ab, wer die typischen Kunden sind]

---

### Teil 2: Forensischer Digital-Audit
**Gesamteinschätzung (Executive Summary):**
[Bewerte die digitale Reife von 1-10 und formuliere eine prägnante Management-Zusammenfassung basierend auf den Beweisen. Unterscheide klar zwischen Tools im GTM und hartcodierten Tools.]

---

#### **Kategorie-Analyse**

**Anweisung:** Bewerte **JEDE** der folgenden 7 Kategorien. Liste für jede Kategorie die gefundenen Tools oder schreibe explizit "**🔴 Lücke:** [Beschreibung der Lücke]", wenn nichts gefunden wurde. Gib für jede Kategorie einen Reifegrad von 1-5 an.

**1. Tag Management & Daten-Grundlage**
* **Status:** [Bewerte hier das gefundene TMS. z.B. 🟢 Google Tag Manager (Best Practice) oder 🟡 Tealium iQ (Enterprise-Alternative) oder 🔴 Keines (Kritische Lücke)]

**2. Data & Analytics**
* **Gefundene Tools:** [Liste hier Tools aus dieser Kategorie mit Konfidenz-Emoji 🟢/🟡]
* **Status:** [Wenn keine Tools gefunden wurden, schreibe: "**🔴 Lücke:** Es wird keine Web-Analyse betrieben, um das Nutzerverhalten zu verstehen."]
* **Reifegrad (1-5):**

**3. Advertising & Performance Marketing**
* **Gefundene Tools:** [...]
* **Status:** [Wenn keine Tools gefunden wurden, schreibe: "**🔴 Lücke:** Es findet kein Retargeting oder Conversion-Tracking für Werbekampagnen statt."]
* **Reifegrad (1-5):**

**4. DSP & Programmatic Advertising**
* **Gefundene Tools:** [...]
* **Status:** [Wenn keine Tools gefunden wurden, schreibe: "**🔴 Lücke:** Das Unternehmen nutzt keine programmatischen Werbeplattformen für eine skalierte Reichweite."]
* **Reifegrad (1-5):**

**5. Marketing Automation & CRM**
* **Gefundene Tools:** [...]
* **Status:** [Wenn keine Tools gefunden wurden, schreibe: "**🔴 Lücke:** Prozesse zur Lead-Generierung und -Pflege sind nicht automatisiert."]
* **Reifegrad (1-5):**

**6. Customer Experience & Personalisierung (CRO)**
* **Gefundene Tools:** [...]
* **Status:** [Wenn keine Tools gefunden wurden, schreibe: "**🔴 Lücke:** Die Webseite wird nicht aktiv optimiert (z.B. durch A/B-Tests oder Heatmaps)."]
* **Reifegrad (1-5):**

**7. Cloud-Nutzung & Infrastruktur**
* **Gefundene Tools:** [...]
* **Status:** [Wenn keine Tools gefunden wurden, schreibe: "Keine direkten Signale für eine spezifische Public-Cloud-Nutzung im Frontend erkannt."]
* **Reifegrad (1-5):**

---

#### **Strategische Auswertung für das Kundengespräch**

**✅ Stärken (Was gut läuft und warum):**

* **Stärke 1:** [Nenne die größte Stärke]
    * **Beobachtung:** [Beschreibe den technischen Fakt.]
    * **Bedeutung (Intern):** [Erkläre die strategische Bedeutung.]
    * **Erläuterung für den Kunden:** [Formuliere eine einfache Analogie.]

**⚠️ Schwächen (Wo das größte Potenzial liegt):**

* **Schwäche 1:** [Nenne die größte Schwäche]
    * **Beobachtung:** [Beschreibe den technischen Fakt oder die Lücke.]
    * **Konkretes Geschäftsrisiko:** [Erkläre das daraus resultierende Geschäftsproblem.]
    * **Erläuterung für den Kunden:** [Formuliere eine einfache Analogie.]

**🚀 Top-Empfehlung (Unser konkreter Vorschlag):**

* **Problem:** [Fasse die größte Schwäche in einem Satz als klares Geschäftsproblem zusammen.]
* **Lösung:** [Beschreibe die konkrete Google-Lösung (z.B. aus dem GMP oder Google Cloud Portfolio).]
* **Ihr Mehrwert:** [Liste 2-3 klare Vorteile für den Kunden auf (z.B. "Präzisere Erfolgsmessung", "Effizienteres Marketing", "Zukunftssicherheit").]
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
