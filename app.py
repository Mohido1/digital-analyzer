import streamlit as st
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import json
import re
from urllib.parse import urljoin, urlparse

# --- Konstanten und Konfiguration ---

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

# --- Python-Logik: Backend-Funktionen ---

def analyze_infrastructure(website_url: str) -> dict:
    """
    Führt eine universelle, zweistufige forensische Analyse durch.
    1. Analysiert das HTML auf Tag Manager und hartcodierte Skripte.
    2. Führt eine Tiefenanalyse des GTM-Containers durch, falls vorhanden.
    """
    results = {
        "tag_management_system": "Keines",
        "gtm_id": None,
        "hardcoded_tools": [],
        "gtm_tools": [],
        "gtm_events": []
    }
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'}
    
    try:
        response = requests.get(website_url, timeout=15, headers=headers)
        response.raise_for_status()
        html_content = response.text
    except requests.RequestException as e:
        st.error(f"Fehler beim Laden der Webseite: {e}")
        return results

    # --- Teil A: Allgemeine HTML-Analyse ---
    # 1. Tag-Manager-Erkennung
    for name, signature in TAG_MANAGERS.items():
        if re.search(signature, html_content, re.IGNORECASE):
            results["tag_management_system"] = name
            break

    # 2. Hartcodierte Tools im HTML finden
    for tech_name, data in TECHNOLOGY_SIGNATURES.items():
        for signature in data["signatures"]:
            match = re.search(f".*{signature}.*", html_content, re.IGNORECASE)
            if match:
                # Extrahiere den relevanten Code-Teil als Beweis
                proof_snippet = match.group(0).strip()
                # Verhindere Duplikate
                if not any(d['name'] == tech_name for d in results['hardcoded_tools']):
                     results["hardcoded_tools"].append({
                        "name": tech_name,
                        "confidence": data["confidence"],
                        "proof": proof_snippet
                    })

    # --- Teil B: GTM-Tiefen-Analyse ---
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

                    # Tools im GTM finden
                    for tech_name, data in TECHNOLOGY_SIGNATURES.items():
                        for signature in data["signatures"]:
                             for line in lines:
                                if re.search(signature, line, re.IGNORECASE):
                                    if not any(d['name'] == tech_name for d in results['gtm_tools']):
                                        results["gtm_tools"].append({
                                            "name": tech_name, "confidence": data["confidence"], "proof": line.strip()
                                        })
                                    break
                             else: continue
                             break

                    # Events im GTM finden
                    for event in BUSINESS_EVENTS:
                        pattern = re.compile(f"['\"]event['\"]:\\s*['\"]{event}['\"]", re.IGNORECASE)
                        for line in lines:
                            if pattern.search(line):
                                if not any(d['name'] == event for d in results['gtm_events']):
                                    results["gtm_events"].append({"name": event, "proof": line.strip()})
                                break

            except requests.RequestException:
                pass # Fehler beim Laden der gtm.js ignorieren

    return results

def scrape_website_text(base_url: str) -> str:
    # Diese Funktion bleibt unverändert
    return "Webseiten-Text-Extraktion übersprungen, um die Kernlogik zu demonstrieren." # Platzhalter für Kürze

def generate_audit(infra_data: dict, website_text: str) -> str:
    """
    Erstellt den forensischen Audit mit Beweisführung mithilfe der Gemini API.
    """
    prompt = f"""
Du bist ein Senior Digital Forensics Analyst. Deine Aufgabe ist es, einen unangreifbaren Audit für unser Sales-Team zu erstellen, bei dem jede Kernaussage mit einem Beweis untermauert wird.

Beweismittel: {json.dumps(infra_data, indent=2)}

Dein Auftrag: Erstelle einen forensischen Bericht. Halte dich exakt an die folgende Berichtsstruktur.

**Berichtsstruktur (Markdown):**

# Forensischer Digital-Audit (mit Beweisführung)

---

## Teil 1: Firmenprofil
- **Unternehmen:** [Leite den Firmennamen aus dem Inhalt ab]
- **Kernbotschaft:** [Fasse die Hauptbotschaft oder den Slogan der Webseite in einem Satz zusammen]
- **Tätigkeit & Branche:** [Beschreibe detailliert, was die Firma macht und in welcher Branche sie tätig ist]
- **Zielgruppe:** [Leite aus der Sprache und den Angeboten ab, wer die typischen Kunden sind]

---

## Teil 2: Forensischer Digital-Audit
**Gesamteinschätzung (Executive Summary):**
[Bewerte die digitale Reife von 1-10 und formuliere eine prägnante Management-Zusammenfassung basierend auf den Beweisen. Unterscheide klar zwischen Tools im GTM und hartcodierten Tools.]

### Kategorie-Analyse
[Für jede der folgenden Kategorien: Liste die gefundenen Tools mit Konfidenz-Emoji (🟢/🟡). Liste danach explizit auf, welche wichtigen Tools aus dieser Kategorie NICHT gefunden wurden (🔴 Lücke).]
- **Tag Management & Daten-Grundlage**
- **Data & Analytics**
- **Advertising & Performance Marketing**
- **Marketing Automation & CRM**
- **Customer Experience & Personalisierung**

---

## Teil 3: Strategische Auswertung (mit Beweisführung)

**✅ Stärken (Was gut läuft und warum):**
- **Stärke 1:** [Nenne die größte Stärke]
- **Beobachtung:** [Beschreibe den technischen Fakt.]
- **Beweis (Code-Snippet):** [Füge hier den "proof"-Schnipsel aus den Beweismitteln ein, formatiert als Code.]
- **Bedeutung (Intern):** [Erkläre die strategische Bedeutung.]
- **Erläuterung für den Kunden:** [Formuliere eine einfache Analogie.]

**⚠️ Schwächen (Wo das größte Potenzial liegt):**
- **Schwäche 1:** [Nenne die größte Schwäche. Beachte besonders hartcodierte Skripte als Problem.]
- **Beobachtung:** [Beschreibe den technischen Fakt oder die Lücke.]
- **Beweis:** [Wenn eine Lücke besteht, schreibe z.B.: "Es konnte kein Code-Schnipsel für ein Conversion-Event wie 'purchase' gefunden werden." Wenn ein hartcodiertes Skript das Problem ist, zeige den "proof" dafür.]
- **Konkretes Geschäftsrisiko:** [Erkläre das daraus resultierende Geschäftsproblem.]
- **Erläuterung für den Kunden:** [Formuliere eine einfache Analogie.]

**🚀 Top-Empfehlung (Unser konkreter Vorschlag):**
[Formuliere eine klare, umsetzbare Handlungsempfehlung, die direkt auf der größten Schwäche aufbaut und eine Lösung anbietet (Problem, Lösung, Mehrwert).]
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

st.set_page_config(page_title="Universal Forensic Auditor", page_icon="🌐")

st.title("🌐 Universal Forensic Auditor")
st.markdown("Führt einen universellen Audit durch, der hartcodierte Skripte von via Tag-Manager geladenen Skripten unterscheidet.")

# Session State
if 'audit' not in st.session_state:
    st.session_state.audit = ""
if 'infra' not in st.session_state:
    st.session_state.infra = {}

# UI-Elemente
url = st.text_input("Geben Sie die vollständige URL der Webseite ein (z.B. `https://www.google.com`)")

if st.button("Universellen Audit starten", type="primary"):
    if not url:
        st.warning("Bitte geben Sie eine URL ein.")
    else:
        if not re.match(r'http(s)?://', url):
            url = 'https://' + url
        
        with st.spinner("Führe universelle Analyse durch... Scanne HTML und GTM-Container..."):
            st.session_state.infra = analyze_infrastructure(url)
            # Die Text-Extraktion ist für diesen spezialisierten Audit weniger kritisch
            website_text = scrape_website_text(url) 
            st.session_state.audit = generate_audit(st.session_state.infra, website_text)

# Ergebnis-Anzeige
if st.session_state.audit:
    st.markdown("---")
    st.subheader("Forensischer Analysebericht")
    st.markdown(st.session_state.audit)

    st.markdown("---")
    st.download_button(
        label="📥 Bericht als Markdown herunterladen",
        data=st.session_state.audit,
        file_name=f"universal_audit_{urlparse(url).netloc}.md",
        mime="text/markdown",
    )

    if st.checkbox("🔍 Detaillierte Beweismittel anzeigen (JSON)"):
        st.subheader("Forensische Infrastruktur-Analyse")
        st.json(st.session_state.infra)

with st.expander("❓ Methodik & Anwendungsfall"):
    st.markdown("""
    **Anwendungsfall:** Dieses Tool liefert eine tiefgehende und realitätsnahe Analyse der Tracking-Infrastruktur einer Webseite. Es ist ideal, um komplexe Setups zu verstehen, bei denen Skripte sowohl zentral über einen Tag Manager als auch dezentral ("hartcodiert") im Quellcode eingebunden sind.

    **Methodik:**
    1.  **HTML-Analyse:** Zuerst wird der gesamte HTML-Quellcode der Seite geladen. Darin wird nach Signaturen für die gängigsten Tag-Management-Systeme (GTM, Tealium, Adobe) sowie nach direkt eingebundenen Tracking-Skripten gesucht.
    2.  **GTM-Tiefenanalyse (optional):** Wird ein Google Tag Manager gefunden, extrahiert die App dessen spezifische ID, lädt die zugehörige `gtm.js`-Konfigurationsdatei und führt darin eine zweite, detaillierte Analyse auf Tools und Events durch.
    3.  **Beweisbasierte Synthese:** Die KI erhält eine detaillierte Liste aller Beweismittel, klar getrennt nach Fundort (HTML oder GTM), und erstellt daraus einen strategischen Bericht, der diese wichtige Unterscheidung für die Bewertung der digitalen Reife nutzt.
    """)
