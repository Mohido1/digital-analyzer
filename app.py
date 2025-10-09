import streamlit as st
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import json
import re
from urllib.parse import urljoin, urlparse

# --- Konstanten und Konfiguration ---

# TECHNOLOGY_SIGNATURES: Ein Dictionary zur Erkennung von Web-Technologien.
TECHNOLOGY_SIGNATURES = {
    # Analytics & Tracking
    "Google Analytics 4": {"signatures": ["G-"], "confidence": "high"},
    "Google Analytics (Universal)": {"signatures": ["UA-"], "confidence": "high"},
    "Adobe Analytics": {"signatures": ["s_code.js", "AppMeasurement.js"], "confidence": "high"},
    "Matomo": {"signatures": ["matomo.js", "piwik.js"], "confidence": "high"},
    # Advertising & Retargeting
    "Google Ads": {"signatures": ["AW-", "google_ad_conversion_id"], "confidence": "high"},
    "Meta Pixel": {"signatures": ["fbq('init'"], "confidence": "high"},
    "LinkedIn Insight Tag": {"signatures": ["linkedin_data_partner_id"], "confidence": "high"},
    "TikTok Pixel": {"signatures": ["tiktok-pc-analytics"], "confidence": "high"},
    # DSP & Programmatic
    "DoubleClick (Google Marketing Platform)": {"signatures": ["doubleclick.net"], "confidence": "medium"},
    # Customer Experience & Personalisierung
    "Hotjar": {"signatures": ["hj('event'"], "confidence": "high"},
    "Optimizely": {"signatures": ["optimizely.com/js"], "confidence": "high"},
    # Marketing Automation & CRM
    "HubSpot": {"signatures": ["js.hs-scripts.com", "_hsq.push"], "confidence": "high"},
    "Salesforce Pardot": {"signatures": ["pi.pardot.com"], "confidence": "high"},
    # Cloud-Nutzung
    "Amazon Web Services (AWS)": {"signatures": ["amazonaws.com"], "confidence": "medium"},
    "Google Cloud Platform (GCP)": {"signatures": ["storage.googleapis.com"], "confidence": "medium"},
    "Cloudflare": {"signatures": ["cdn-cgi/scripts"], "confidence": "medium"},
}

# Liste der zu suchenden Business-Events
BUSINESS_EVENTS = ['purchase', 'add_to_cart', 'begin_checkout', 'form_submission', 'lead', 'sign_up']

# --- Python-Logik: Backend-Funktionen (unverändert) ---

def analyze_infrastructure(url: str) -> dict:
    """
    Führt eine forensische Analyse der Webseite durch.
    Prüft auf GTM, analysiert Technologien und verfolgte Events.
    """
    results = {
        "has_gtm": False,
        "detected_tools": [],
        "tracked_events": []
    }
    domain = urlparse(url).netloc
    # Wir versuchen es mit und ohne 'www', da die Konfiguration variieren kann
    gtm_urls = [f"https://www.googletagmanager.com/gtm.js?id={domain}",
                f"https://www.googletagmanager.com/gtm.js?id={domain.replace('www.','')}"
               ]

    gtm_content = None
    
    for gtm_url in gtm_urls:
        try:
            response = requests.get(gtm_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            if response.status_code == 200 and 'GTM-' in response.text:
                results["has_gtm"] = True
                gtm_content = response.text
                break
        except requests.exceptions.RequestException:
            continue
    
    if gtm_content:
        # Tool-Analyse
        for tech_name, data in TECHNOLOGY_SIGNATURES.items():
            for signature in data["signatures"]:
                if signature in gtm_content:
                    results["detected_tools"].append({"name": tech_name, "confidence": data["confidence"]})
                    break
        # Event-Analyse
        for event in BUSINESS_EVENTS:
            if f"'{event}'" in gtm_content or f'"{event}"' in gtm_content:
                results["tracked_events"].append(event)
    
    return results

def scrape_website_text(base_url: str) -> str:
    """
    Sammelt den Text von der Startseite und relevanten Unterseiten einer Webseite.
    """
    subpage_paths = [
        '/', '/ueber-uns', '/about', '/about-us', '/company', '/unternehmen',
        '/services', '/leistungen', '/produkte', '/products',
        '/karriere', 'jobs', '/contact', '/kontakt'
    ]
    total_text = ""
    processed_urls = set()
    headers = {'User-Agent': 'Mozilla/5.0'}

    for path in subpage_paths:
        url_to_scrape = urljoin(base_url, path)
        if url_to_scrape in processed_urls:
            continue
        try:
            response = requests.get(url_to_scrape, timeout=10, headers=headers)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
                    element.decompose()
                text = soup.get_text(separator=' ', strip=True)
                total_text += f"\n\n--- Inhalt von {url_to_scrape} ---\n\n{text}"
                processed_urls.add(url_to_scrape)
        except requests.exceptions.RequestException:
            continue
    
    if not total_text:
        st.error(f"Fehler: Konnte keinen Text von der Webseite {base_url} extrahieren.")
    return total_text.strip()

def generate_dossier(infra_data: dict, website_text: str) -> str:
    """
    Erstellt das strategische Dossier mit der Google Gemini API.
    """
    # Alle Beweismittel in einem strukturierten Format zusammenfassen
    evidence = {
        "GTM-Status": "Google Tag Manager gefunden" if infra_data["has_gtm"] else "Kein Tag Management System gefunden",
        "Erkannte Technologien": infra_data["detected_tools"],
        "Verfolgte Kern-Events": infra_data["tracked_events"],
        "Webseiten-Inhalt": website_text[:30000]
    }
    
    # Der finale Prompt für die strategische Vorstands-Analyse
    prompt = f"""
Du bist ein Partner bei einer Top-Management-Beratung (z.B. McKinsey, BCG) mit Spezialisierung auf digitale Transformation und datengetriebene Geschäftsmodelle. Deine Aufgabe ist es, ein strategisches Dossier für eine Vorstandssitzung zu erstellen.

Beweismittel: {json.dumps(evidence, indent=2)}

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
[Bewerte die digitale Reife von 1-10 und formuliere eine prägnante Management-Zusammenfassung (3-4 Sätze) über die allgemeine Situation.]

### Audit der Kernkompetenzen
**Anweisung:** Bewerte JEDE der folgenden Kategorien.

**1. Daten-Grundlage & Tag Management**
- **Status:** [{ "🟢 Google Tag Manager" if evidence["GTM-Status"] == "Google Tag Manager gefunden" else "🔴 Kritische Lücke: Kein TMS"}]

**2. Data & Analytics**
- **Gefundene Tools:** [Liste gefundene Tools. Wenn leer: "Keine"]
- **Status & Implikation:** [Wenn keine Tools gefunden wurden, schreibe: "🔴 Lücke: Dem Unternehmen fehlt die grundlegendste Fähigkeit, das Nutzerverhalten zu analysieren. Entscheidungen werden 'blind' getroffen."]
- **Reifegrad (1-5):** [Bewerte von 1-5]

**3. Advertising & Kundengewinnung**
- **Gefundene Tools:** [Liste gefundene Tools, z.B. 🟢 Meta Pixel, 🟡 Google Ads (ohne Events)]
- **Status & Implikation:** [Wenn keine Tools/Events gefunden wurden, schreibe: "🔴 Lücke: Es gibt keine technische Grundlage, um den Erfolg von Werbeausgaben zu messen (ROAS). Investitionen sind nicht messbar."]
- **Reifegrad (1-5):** [Bewerte von 1-5]

**4. DSP & Programmatic**
- **Gefundene Tools:** [Liste gefundene Tools]
- **Status & Implikation:** [Wenn keine Tools gefunden wurden, schreibe: "⚪️ Unentwickelt: Keine Hinweise auf programmatische Werbung. Potenzial zur Skalierung der Reichweite bleibt ungenutzt."]
- **Reifegrad (1-5):** [Bewerte von 1-5]

**5. Marketing Automation & CRM**
- **Gefundene Tools:** [Liste gefundene Tools]
- **Status & Implikation:** [Wenn keine Tools gefunden wurden, schreibe: "🔴 Lücke: Prozesse zur Lead-Pflege und Kundenbindung sind nicht automatisiert und skalierbar."]
- **Reifegrad (1-5):** [Bewerte von 1-5]

**6. Customer Experience & Personalisierung**
- **Gefundene Tools:** [Liste gefundene Tools]
- **Status & Implikation:** [Wenn keine Tools gefunden wurden, schreibe: "🔴 Lücke: Die Webseite bietet allen Nutzern die gleiche, statische Erfahrung. Individualisierung findet nicht statt."]
- **Reifegrad (1-5):** [Bewerte von 1-5]

**7. Cloud-Nutzung**
- **Gefundene Tools:** [Liste gefundene Tools]
- **Status & Implikation:** [Wenn keine Tools gefunden wurden, schreibe: "⚪️ Unklar: Keine spezifischen Cloud-Services identifiziert. Eine skalierbare, moderne IT-Infrastruktur ist nicht nachweisbar."]
- **Reifegrad (1-5):** [Bewerte von 1-5]

---

## Teil 3: Strategische Auswertung & Handlungsbedarf
**✅ Operative Stärken:**
- **Stärke:** [Nenne die größte Stärke]
- **Beobachtung:** [Der technische Fakt.]
- **Strategische Implikation:** [Erkläre in 2-3 Sätzen die positive Auswirkung auf das Geschäft. Z.B.: "Durch den Einsatz von HubSpot besteht bereits eine zentrale Plattform für die Lead-Verwaltung, was eine skalierbare Vertriebs-Pipeline ermöglicht."]

**⚠️ Strategische Risiken (Handlungsbedarf):**
- **Risiko:** [Nenne die größte Schwäche]
- **Beobachtung:** [Der technische Fakt oder die Lücke.]
- **Konkretes Geschäftsrisiko:** [Erkläre in 2-3 Sätzen die negativen Auswirkungen auf das Geschäft. Z.B.: "Ohne serverseitiges Tracking wird der Datenverlust durch Ad-Blocker und Browser-Updates weiter zunehmen. Dies führt zu einer stetig sinkenden Effizienz der Werbeausgaben und dem Risiko, Marktanteile an Wettbewerber zu verlieren, die ihre Kunden besser verstehen."]

## Teil 4: Empfohlener Strategischer Fahrplan
**💡 Quick Wins (Sofortmaßnahmen mit hohem ROI):**
- [Liste hier 1-2 konkrete, schnell umsetzbare Maßnahmen auf, die einen sofortigen Mehrwert bringen. Z.B.: "Einrichtung eines Basis-Trackings mit GA4, um die wichtigsten 3-5 Nutzeraktionen auf der Webseite zu messen."]

**🚀 Unser strategischer Vorschlag (Phasenplan):**
- **Phase 1: Fundament schaffen (1-3 Monate):** [Beschreibe den wichtigsten ersten Schritt, um die größte Lücke zu schließen. Z.B.: "Implementierung eines serverseitigen Google Tag Managers auf der Google Cloud zur Schaffung einer zukunftssicheren First-Party-Datenbasis."]
- **Phase 2: Potenzial entfalten (3-9 Monate):** [Beschreibe den nächsten logischen Schritt, der auf Phase 1 aufbaut. Z.B.: "Anreicherung der gesammelten Daten in BigQuery und Aufbau von Dashboards zur Berechnung des echten Marketing-ROI."]
- **Langfristige Vision:** [Beschreibe das Endziel in einem Satz. Z.B.: "Etablierung eines prädiktiven Analyse-Modells zur Vorhersage des Customer Lifetime Value und zur Automatisierung der Budget-Allokation."]
"""
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"Fehler bei der Kommunikation mit der Gemini API: {e}")
        return None

# --- Streamlit Benutzeroberfläche (unverändert) ---

st.set_page_config(page_title="Strategie-Dossier Generator", page_icon="📈")

st.title("📈 Strategie-Dossier Generator")
st.markdown("Erstellt eine tiefgehende, strategische Analyse der digitalen Aufstellung eines Unternehmens für das Management.")

# Session State Initialisierung
if 'dossier' not in st.session_state:
    st.session_state.dossier = ""
if 'infra' not in st.session_state:
    st.session_state.infra = {}
if 'text' not in st.session_state:
    st.session_state.text = ""

# Eingabefeld
url = st.text_input("Geben Sie die vollständige URL der Webseite ein (z.B. `https://www.beispiel.de`)")

if st.button("Strategisches Dossier erstellen", type="primary"):
    if not url:
        st.warning("Bitte geben Sie eine URL ein.")
    else:
        if not re.match(r'http(s)?://', url):
            url = 'https://' + url
        
        with st.spinner("Erstelle Dossier... Führe Tiefenanalyse durch und bewerte strategische Implikationen..."):
            st.session_state.infra = analyze_infrastructure(url)
            st.session_state.text = scrape_website_text(url)
            
            if st.session_state.text:
                st.session_state.dossier = generate_dossier(st.session_state.infra, st.session_state.text)
            else:
                st.session_state.dossier = ""

# --- Anzeige der Ergebnisse ---

if st.session_state.dossier:
    st.markdown("---")
    st.subheader("Strategisches Dossier")
    st.markdown(st.session_state.dossier)

    st.markdown("---")
    st.download_button(
        label="📥 Dossier als Markdown herunterladen",
        data=st.session_state.dossier,
        file_name=f"strategie_dossier_{urlparse(url).netloc}.md",
        mime="text/markdown",
    )

    if st.checkbox("🔍 Beweismittel anzeigen (technische Rohdaten)"):
        st.subheader("Infrastruktur-Analyse")
        st.json(st.session_state.infra)

        st.subheader("Extrahierter Webseiten-Text")
        st.text_area("Gesammelter Text", st.session_state.text, height=300)

with st.expander("❓ Methodik & Anwendungsfall"):
    st.markdown("""
    **Anwendungsfall:** Dieses Tool dient der schnellen Erstellung einer fundierten, externen Analyse der digitalen Aufstellung eines Unternehmens (z.B. eines potenziellen Kunden, Partners oder Wettbewerbers). Das Ergebnis ist ein strategisches Dossier, das als Grundlage für Management-Diskussionen dient.

    **Methodik:**
    1.  **Forensische Analyse:** Die App untersucht die technische Infrastruktur der Webseite auf Schlüsseltechnologien (z.B. Analytics, CRM, Ad-Tech) und deren Konfiguration (Tag Management, Event-Tracking).
    2.  **Inhalts-Analyse:** Parallel dazu wird der Inhalt der Webseite ausgelesen, um die strategische Ausrichtung (Branche, Zielgruppe, Wertversprechen) des Unternehmens zu verstehen.
    3.  **Strategische Synthese durch KI:** Die gesammelten "Beweismittel" werden von einem Gemini-Sprachmodell analysiert, das darauf trainiert ist, wie ein Top-Management-Berater zu agieren. Es übersetzt die technischen Fakten in strategische Implikationen, bewertet Geschäftsrisiken und leitet einen konkreten Handlungsplan ab.
    """)
