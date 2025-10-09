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
    # Advertising & Retargeting
    "Google Ads": {"signatures": ["AW-", "google_ad_conversion_id"], "confidence": "high"},
    "Meta Pixel": {"signatures": ["fbq('init'"], "confidence": "high"},
    "LinkedIn Insight Tag": {"signatures": ["linkedin_data_partner_id"], "confidence": "high"},
    # Customer Experience & CRO
    "Hotjar": {"signatures": ["hj('event'"], "confidence": "high"},
    "Optimizely": {"signatures": ["optimizely.com/js"], "confidence": "high"},
    # Marketing Automation & CRM
    "HubSpot": {"signatures": ["js.hs-scripts.com", "_hsq.push"], "confidence": "high"},
    # Consent Management Platforms (CMP)
    "Cookiebot": {"signatures": ["consent.cookiebot.com"], "confidence": "high"},
    "Usercentrics": {"signatures": ["app.usercentrics.eu"], "confidence": "high"},
    # E-Commerce Platforms
    "Shopify": {"signatures": ["Shopify.theme", "cdn.shopify.com"], "confidence": "high"},
    # Cloud & Content Delivery (Generic Signals)
    "Amazon Web Services (AWS)": {"signatures": ["amazonaws.com"], "confidence": "medium"},
    "Google Cloud Platform (GCP)": {"signatures": ["storage.googleapis.com"], "confidence": "medium"},
    "Cloudflare": {"signatures": ["cdn-cgi/scripts"], "confidence": "medium"},
    "Microsoft Azure": {"signatures": ["azureedge.net"], "confidence": "medium"}
}

# --- Python-Logik: Backend-Funktionen ---

def analyze_technologies(url: str) -> list[dict]:
    """
    Analysiert die gtm.js-Datei einer Webseite, um verwendete Technologien zu identifizieren.
    """
    found_technologies = []
    # Extrahiert den Domainnamen für die gtm.js URL
    domain = urlparse(url).netloc
    gtm_url = f"https://www.googletagmanager.com/gtm.js?id={domain}"
    
    try:
        response = requests.get(gtm_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code == 200:
            content = response.text
            for tech_name, data in TECHNOLOGY_SIGNATURES.items():
                for signature in data["signatures"]:
                    if signature in content:
                        found_technologies.append({"name": tech_name, "confidence": data["confidence"]})
                        break
    except requests.exceptions.RequestException as e:
        st.warning(f"Technologie-Analyse (gtm.js) konnte nicht durchgeführt werden: {e}. Bericht wird ohne diese Daten erstellt.")
    return found_technologies

def scrape_website_text(base_url: str) -> str:
    """
    Sammelt den Text von der Startseite und relevanten Unterseiten einer Webseite.
    Ignoriert Seiten, die nicht gefunden werden (404-Fehler).
    """
    # Liste gängiger Unterseiten-Pfade für eine umfassende Analyse
    subpage_paths = [
        '/',  # Startseite explizit als erstes
        '/ueber-uns', '/about', '/about-us', '/company', '/unternehmen',
        '/services', '/leistungen', '/produkte', '/products',
        '/karriere', '/jobs', '/career'
    ]
    
    total_text = ""
    processed_urls = set()
    
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'}

    for path in subpage_paths:
        # Konstruiert die vollständige URL für jede Unterseite
        url_to_scrape = urljoin(base_url, path)
        
        if url_to_scrape in processed_urls:
            continue
            
        try:
            response = requests.get(url_to_scrape, timeout=10, headers=headers)
            # Fährt nur fort, wenn die Seite erfolgreich geladen wurde (Status 200)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                for script_or_style in soup(["script", "style", "nav", "footer"]):
                    script_or_style.decompose()

                text = soup.get_text(separator=' ', strip=True)
                total_text += f"\n\n--- Inhalt von {url_to_scrape} ---\n\n{text}"
                processed_urls.add(url_to_scrape)

        except requests.exceptions.RequestException:
            # Ignoriert Fehler (z.B. 404, Timeout) und macht mit der nächsten Seite weiter
            continue
            
    if not total_text:
        st.error(f"Fehler: Konnte keinen Text von der Webseite {base_url} extrahieren. Bitte prüfen Sie die URL und versuchen Sie es erneut.")

    return total_text.strip()

def generate_report(technologies: list, website_text: str) -> str:
    """
    Generiert den vollständigen Analysebericht mit der Google Gemini API.
    """
    # Der aktualisierte, umfassende Prompt für die KI
    prompt = f"""
Du bist ein Senior Business Analyst und Digital-Stratege bei einem führenden Google Partner. Du erhältst zwei Arten von Daten über ein Unternehmen:
1. Eine Liste von erkannten Technologien auf seiner Webseite.
2. Den gesammelten Textinhalt von der Startseite und wichtigen Unterseiten (wie 'Über uns', 'Leistungen', 'Karriere').

Erkannte Technologien: {json.dumps(technologies, indent=2)}
Webseiten-Inhalt: ```{website_text[:25000]}```

Deine Aufgabe: Erstelle einen vollständigen, tiefgehenden Analysebericht. Formatiere alles professionell in Markdown.

# Digital Maturity & Strategy Audit

---

## Teil 1: Firmenprofil (basierend auf dem Webseiten-Inhalt)
- **Unternehmen:** [Leite den Firmennamen aus dem Inhalt ab]
- **Kernbotschaft:** [Fasse die Hauptbotschaft oder den Slogan der Webseite in einem Satz zusammen]
- **Tätigkeit & Branche:** [Beschreibe in 2-3 Sätzen detailliert, was die Firma macht und in welcher Branche sie tätig ist, basierend auf dem gesamten Text]
- **Zielgruppe:** [Leite aus der Sprache und den Angeboten ab, wer die typischen Kunden sind (z.B. B2B, B2C, kleine Unternehmen, Konzerne)]

---

## Teil 2: Digital Maturity Audit (basierend auf den erkannten Technologien)
**Gesamteinschätzung:**
- **Digital Maturity Score (1-10):** [Bewerte die digitale Reife auf einer Skala von 1 bis 10 und begründe kurz.]
- **Zusammenfassung:** [Gib eine prägnante Zusammenfassung der digitalen Aufstellung des Unternehmens.]

### Kategorie-Analyse
Präsentiere in diesem Abschnitt die gefundenen Tools. Wenn keine Tools in einer Kategorie gefunden wurden, identifiziere dies als Lücke.

- **Data & Analytics**
  - **Gefundene Tools:** [Liste hier die Tools aus den Kategorien 'Analytics & Tracking' und 'Consent Management Platforms'. Verwende 🟢 für 'high' und 🟡 für 'medium' Konfidenz. Bei keinen Tools: "🔴 Lücke: Keine spezialisierten Analytics- oder CMP-Tools erkannt."]
  - **Reifegrad (1-5):** [Bewerte die Reife in diesem Bereich von 1-5 und begründe.]

- **Advertising & Performance Marketing**
  - **Gefundene Tools:** [Liste hier die Tools aus der Kategorie 'Advertising & Retargeting'. Verwende 🟢 für 'high' und 🟡 für 'medium' Konfidenz. Bei keinen Tools: "🔴 Lücke: Keine Performance-Marketing-Pixel oder -Tags implementiert."]
  - **Reifegrad (1-5):** [Bewerte die Reife in diesem Bereich von 1-5 und begründe.]

- **Customer Experience & Personalisierung**
  - **Gefundene Tools:** [Liste hier die Tools aus den Kategorien 'Customer Experience & CRO', 'Marketing Automation & CRM'. Verwende 🟢 für 'high' und 🟡 für 'medium' Konfidenz. Bei keinen Tools: "🔴 Lücke: Keine Tools zur Optimierung der Nutzererfahrung oder zur Marketing-Automatisierung gefunden."]
  - **Reifegrad (1-5):** [Bewerte die Reife in diesem Bereich von 1-5 und begründe.]

### Strategische Auswertung für das Kundengespräch
- **Stärken:**
  - [Punkt 1: Was macht das Unternehmen technologisch bereits gut?]
  - [Punkt 2: Gibt es weitere positive Aspekte?]

- **Schwächen & Potenziale:**
  - [Punkt 1: Wo liegen die größten technologischen Lücken oder ungenutzten Potenziale?]
  - [Punkt 2: Gibt es weitere Schwachstellen?]

- **Top-Empfehlung (als Google Partner):**
  - **Beobachtung:** [Beschreibe eine konkrete, faktenbasierte Beobachtung.]
  - **Bedeutung:** [Erkläre, warum diese Beobachtung für das Geschäft des Kunden relevant ist.]
  - **Empfehlung:** [Gib eine klare, umsetzbare Handlungsempfehlung, die idealerweise auf Google-Technologien (z.B. Google Analytics 4, Google Ads) aufbaut.]
"""
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-flash-latest')
        response = model.generate_content(prompt)
        return response.text
    except (KeyError, FileNotFoundError):
        st.error("GEMINI_API_KEY nicht in den Streamlit Secrets gefunden.")
        return None
    except Exception as e:
        st.error(f"Fehler bei der Kommunikation mit der Gemini API: {e}")
        return None


# --- Streamlit Benutzeroberfläche ---

st.set_page_config(page_title="Firmen-Tiefenanalyse", page_icon="📈")

st.title("📈 Firmen-Tiefenanalyse Pro")
st.markdown("Geben Sie eine URL ein, um eine tiefgehende Analyse des Firmenprofils und der digitalen Reife zu erhalten.")

# Session State Initialisierung
if 'report' not in st.session_state:
    st.session_state.report = ""
if 'tech' not in st.session_state:
    st.session_state.tech = []
if 'text' not in st.session_state:
    st.session_state.text = ""

# Eingabefeld
url = st.text_input(
    "Geben Sie die vollständige URL der Webseite ein (z.B. `https://www.beispiel.de`)", 
    key="url_input"
)

if st.button("Analyse starten", type="primary"):
    if not url:
        st.warning("Bitte geben Sie eine URL ein.")
    else:
        # Standardisiert die URL
        if not re.match(r'http(s)?://', url):
            url = 'https://' + url
        
        with st.spinner("Führe Tiefenanalyse durch... Lese mehrere Unterseiten und kontaktiere die KI..."):
            # Beide Analysefunktionen aufrufen
            st.session_state.tech = analyze_technologies(url)
            st.session_state.text = scrape_website_text(url)
            
            # Bericht nur generieren, wenn Text extrahiert werden konnte
            if st.session_state.text:
                st.session_state.report = generate_report(st.session_state.tech, st.session_state.text)
            else:
                st.session_state.report = ""

# --- Anzeige der Ergebnisse ---

if st.session_state.report:
    st.markdown("---")
    st.subheader("Analysebericht")
    st.markdown(st.session_state.report)

    st.markdown("---")
    st.download_button(
        label="📥 Bericht als Markdown herunterladen",
        data=st.session_state.report,
        file_name=f"analyse_{urlparse(url).netloc}.md",
        mime="text/markdown",
    )

    if st.checkbox("🔍 Rohdaten der Analyse anzeigen"):
        st.subheader("Erkannte Technologien")
        if st.session_state.tech:
            st.json(st.session_state.tech)
        else:
            st.info("Keine spezifischen Technologien über die gtm.js-Analyse gefunden.")

        st.subheader("Extrahierter Webseiten-Text (von allen Unterseiten)")
        st.text_area("Gesammelter Text", st.session_state.text, height=300)

with st.expander("❓ Anleitung & Info"):
    st.markdown("""
    **Was ist neu in dieser Version?**
    1.  **Multi-Seiten-Analyse:** Die App beschränkt sich nicht mehr auf die Startseite. Sie versucht aktiv, wichtige Unterseiten wie "Über uns", "Leistungen" und "Karriere" zu finden und deren Inhalte zu aggregieren.
    2.  **Tiefgreifendes Firmenprofil:** Durch die Analyse mehrerer Seiten kann die KI ein wesentlich genaueres Bild von der Tätigkeit, Branche und Zielgruppe des Unternehmens zeichnen.
    3.  **Download-Funktion:** Sie können den generierten Bericht direkt als Markdown-Datei herunterladen.
    """)
