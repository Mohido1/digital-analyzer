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
    # Customer Experience & Personalisierung
    "Hotjar": {"signatures": ["hj('event'"], "confidence": "high"},
    "Optimizely": {"signatures": ["optimizely.com/js"], "confidence": "high"},
    # Marketing Automation & CRM
    "HubSpot": {"signatures": ["js.hs-scripts.com", "_hsq.push"], "confidence": "high"},
    "Salesforce Pardot": {"signatures": ["pi.pardot.com"], "confidence": "high"},
    # Consent Management Platforms (CMP)
    "Cookiebot": {"signatures": ["consent.cookiebot.com"], "confidence": "high"},
    "Usercentrics": {"signatures": ["app.usercentrics.eu"], "confidence": "high"},
}

# Liste der zu suchenden Business-Events
BUSINESS_EVENTS = ['purchase', 'add_to_cart', 'begin_checkout', 'form_submission', 'lead', 'sign_up']

# --- Python-Logik: Backend-Funktionen ---

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
    gtm_url = f"https://www.googletagmanager.com/gtm.js?id={domain}"
    
    try:
        response = requests.get(gtm_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        
        # Schritt 1: GTM-Check
        if response.status_code == 200 and 'GTM-' in response.text:
            results["has_gtm"] = True
            gtm_content = response.text
            
            # Schritt 2: Tool-Analyse
            for tech_name, data in TECHNOLOGY_SIGNATURES.items():
                for signature in data["signatures"]:
                    if signature in gtm_content:
                        results["detected_tools"].append({"name": tech_name, "confidence": data["confidence"]})
                        break
            
            # Schritt 3: Event-Analyse
            for event in BUSINESS_EVENTS:
                if f"'{event}'" in gtm_content or f'"{event}"' in gtm_content:
                    results["tracked_events"].append(event)
        
    except requests.exceptions.RequestException:
        # Fehler wird ignoriert, da das Fehlen von GTM ein Analyseergebnis ist.
        pass
        
    return results

def scrape_website_text(base_url: str) -> str:
    """
    Sammelt den Text von der Startseite und relevanten Unterseiten einer Webseite.
    """
    subpage_paths = [
        '/', '/ueber-uns', '/about', '/about-us', '/company', '/unternehmen',
        '/services', '/leistungen', '/produkte', '/products',
        '/karriere', '/jobs', '/career', '/kontakt', '/contact'
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
                for element in soup(["script", "style", "nav", "footer", "header"]):
                    element.decompose()
                text = soup.get_text(separator=' ', strip=True)
                total_text += f"\n\n--- Inhalt von {url_to_scrape} ---\n\n{text}"
                processed_urls.add(url_to_scrape)
        except requests.exceptions.RequestException:
            continue
            
    if not total_text:
        st.error(f"Fehler: Konnte keinen Text von der Webseite {base_url} extrahieren.")
    return total_text.strip()

def generate_report(infra_data: dict, website_text: str) -> str:
    """
    Generiert den forensischen Analysebericht mit der Google Gemini API.
    """
    # Beweismittel für den Prompt vorbereiten
    gtm_status = "GTM gefunden" if infra_data["has_gtm"] else "Kein GTM gefunden"
    
    # Der finale, forensische KI-Befehl
    prompt = f"""
Du bist ein Senior Digital Forensics Analyst. Deine Aufgabe ist es, einen tiefgehenden Audit für unser Sales-Team zu erstellen, der auch für Laien verständlich ist. Du erhältst folgende Beweismittel:

Beweismittel 1 - GTM-Status: {gtm_status}
Beweismittel 2 - Erkannte Technologien: {json.dumps(infra_data["detected_tools"])}
Beweismittel 3 - Verfolgte Kern-Events: {json.dumps(infra_data["tracked_events"])}
Beweismittel 4 - Webseiten-Inhalt: ```{website_text[:25000]}```

Dein Auftrag: Erstelle einen forensischen Bericht. Gehe in deiner Analyse explizit auf die Kombination der gefundenen Technologien UND Events ein. Wenn kein GTM gefunden wurde, muss dies die zentrale Schwäche sein.

**Berichtsstruktur (Markdown):**

# Forensischer Digital-Audit

---

## Teil 1: Firmenprofil
- **Unternehmen:** [Leite den Firmennamen aus dem Inhalt ab]
- **Kernbotschaft:** [Fasse die Hauptbotschaft oder den Slogan der Webseite in einem Satz zusammen]
- **Tätigkeit & Branche:** [Beschreibe in 2-3 Sätzen detailliert, was die Firma macht und in welcher Branche sie tätig ist]
- **Zielgruppe:** [Leite aus der Sprache und den Angeboten ab, wer die typischen Kunden sind]

---

## Teil 2: Forensischer Digital-Audit
**Gesamteinschätzung:**
[Bewerte die digitale Reife von 1-10 und gib eine Zusammenfassung, die den GTM-Status und die Event-Analyse berücksichtigt.]

### Kategorie-Analyse
Für jede der folgenden Kategorien: Liste zuerst die gefundenen Tools mit Konfidenz-Emoji (🟢/🟡). Liste danach explizit auf, welche wichtigen Tools aus dieser Kategorie NICHT gefunden wurden (🔴 Lücke).

**1. Tag Management & Daten-Grundlage**
- **Status:** [{ "🟢 Google Tag Manager aktiv" if infra_data["has_gtm"] else "🔴 Kein Tag Management System gefunden"}]

**2. Data & Analytics**
- **Gefundene Tools:** [Liste die gefundenen Analytics Tools. Wenn leer: "Keine"]
- **Potenzielle Lücken:** [z.B. 🔴 Adobe Analytics, 🔴 Matomo]

**3. Advertising & Performance Marketing**
- **Gefundene Tools:** [Liste die gefundenen Advertising Tools. Wenn leer: "Keine"]
- **Potenzielle Lücken:** [z.B. 🔴 LinkedIn Insight Tag, 🔴 TikTok Pixel]

**4. Marketing Automation & CRM**
- **Gefundene Tools:** [Liste die gefundenen CRM/Automation Tools. Wenn leer: "Keine"]
- **Potenzielle Lücken:** [z.B. 🔴 HubSpot, 🔴 Salesforce Pardot]

**5. Customer Experience & Personalisierung**
- **Gefundene Tools:** [Liste die gefundenen CX Tools. Wenn leer: "Keine"]
- **Potenzielle Lücken:** [z.B. 🔴 Hotjar, 🔴 Optimizely]

---

## Teil 3: Strategische Auswertung für das Kundengespräch

**✅ Stärken (Was gut läuft und warum):**
- **Stärke 1:** [Nenne die größte Stärke, basierend auf den Beweisen.]
- **Beweis:** [Nenne hier die konkreten Beweismittel. Z.B.: "Wir haben die Implementierung des Meta Pixels (🟢) in Kombination mit einem 'purchase'-Event nachgewiesen."]
- **Bedeutung (Intern):** [Erkläre die strategische Bedeutung.]
- **Erläuterung für den Kunden:** [Formuliere eine einfache Analogie.]

**⚠️ Schwächen (Wo das größte Potenzial liegt):**
- **Schwäche 1:** [Nenne die größte Schwäche, basierend auf den identifizierten Lücken und fehlenden Events.]
- **Beweis:** [Nenne die Beweismittel. Z.B.: "Es wurde kein Google Tag Manager gefunden. Alle Skripte werden unstrukturiert geladen."]
- **Bedeutung (Intern):** [Erkläre das Problem. Z.B.: "Komplett unflexibel, langsam, fehleranfällig. Keine Möglichkeit, schnell auf neue Marketing-Anforderungen zu reagieren."]
- **Erläuterung für den Kunden:** [Formuliere eine einfache Analogie. Z.B.: "Stellen Sie sich vor, die Elektrik in Ihrem Haus wäre ohne Sicherungskasten verlegt. Jedes Mal, wenn Sie eine neue Lampe anschließen wollen, müssen Sie die Wände aufreißen. Ein Tag Manager ist dieser fehlende, zentrale Sicherungskasten für Ihr digitales Marketing."]

**🚀 Top-Empfehlung (Unser konkreter Vorschlag):**
[Formuliere eine klare, umsetzbare Handlungsempfehlung, die direkt auf der größten Schwäche aufbaut und eine Lösung anbietet.]
"""
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-flash-latest')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"Fehler bei der Kommunikation mit der Gemini API: {e}")
        return None

# --- Streamlit Benutzeroberfläche ---

st.set_page_config(page_title="Digital Forensics Auditor", page_icon="🔬")

st.title("🔬 Digital Forensics Auditor")
st.markdown("Führen Sie einen tiefgehenden Audit der digitalen Infrastruktur einer Webseite durch.")

# Session State Initialisierung
if 'report' not in st.session_state:
    st.session_state.report = ""
if 'infra' not in st.session_state:
    st.session_state.infra = {}
if 'text' not in st.session_state:
    st.session_state.text = ""

# Eingabefeld
url = st.text_input("Geben Sie die vollständige URL der Webseite ein (z.B. `https://www.beispiel.de`)")

if st.button("Forensischen Audit starten", type="primary"):
    if not url:
        st.warning("Bitte geben Sie eine URL ein.")
    else:
        if not re.match(r'http(s)?://', url):
            url = 'https://' + url
        
        with st.spinner("Führe forensische Analyse durch... Untersuche GTM, Events und Webinhalte..."):
            st.session_state.infra = analyze_infrastructure(url)
            st.session_state.text = scrape_website_text(url)
            
            if st.session_state.text:
                st.session_state.report = generate_report(st.session_state.infra, st.session_state.text)
            else:
                st.session_state.report = ""

# --- Anzeige der Ergebnisse ---

if st.session_state.report:
    st.markdown("---")
    st.subheader("Forensischer Analysebericht")
    st.markdown(st.session_state.report)

    st.markdown("---")
    st.download_button(
        label="📥 Bericht als Markdown herunterladen",
        data=st.session_state.report,
        file_name=f"forensischer_audit_{urlparse(url).netloc}.md",
        mime="text/markdown",
    )

    if st.checkbox("🔍 Beweismittel anzeigen (Rohdaten)"):
        st.subheader("Infrastruktur-Analyse")
        st.json(st.session_state.infra)

        st.subheader("Extrahierter Webseiten-Text")
        st.text_area("Gesammelter Text", st.session_state.text, height=300)

with st.expander("❓ Funktionsweise & Methodik"):
    st.markdown("""
    **1. GTM-Verifizierung:** Die App prüft zunächst, ob ein Google Tag Manager (`GTM-XXXX`) auf der Seite aktiv ist. Dies ist die Grundlage für jede moderne, flexible Datenstrategie.
    **2. Tool-Analyse:** Falls GTM vorhanden ist, wird der Code auf Signaturen bekannter Marketing-, Analytics- und CRM-Tools durchsucht.
    **3. Event-Analyse:** Parallel dazu wird der GTM-Code auf die Konfiguration von wichtigen Geschäfts-Events (`purchase`, `lead` etc.) untersucht. Dies zeigt, ob das Unternehmen nicht nur Tools installiert hat, sondern auch aktiv Daten misst.
    **4. Inhaltsanalyse:** Der Text von relevanten Unterseiten wird extrahiert, um die Geschäftsziele und die Zielgruppe des Unternehmens zu verstehen.
    **5. KI-Synthese:** Alle gesammelten "Beweismittel" werden an die Gemini KI gesendet, die sie zu einem strategischen, leicht verständlichen Bericht für Vertriebsgespräche zusammenfügt.
    """)
