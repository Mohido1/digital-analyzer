import streamlit as st
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import pyperclip

# --- Konfiguration ---
TECHNOLOGY_SIGNATURES = {
    # Analytics & Tracking
    "Google Analytics 4": ["G-"], "Google Analytics (Universal)": ["UA-"], "Adobe Analytics": ["s_code.js", "AppMeasurement.js"], "Matomo / Piwik": ["_paq.push"],
    # Advertising & Retargeting
    "Google Ads": ["AW-", "google_ad_conversion_id"], "Google Marketing Platform (Floodlight)": ["fls.doubleclick.net"], "Meta Pixel": ["fbq('init'"], "LinkedIn Insight Tag": ["linkedin_data_partner_id"], "TikTok Pixel": ["ttq('init'"], "Criteo": ["static.criteo.net"], "AdRoll": ["adroll_adv_id"], "Taboola": ["trc.taboola.com"],
    # DSPs (Demand-Side Platforms)
    "The Trade Desk": ["insight.adsrvr.org"], "Xandr (AppNexus)": ["anj.adnxs.com"], "MediaMath": ["mathads.com"],
    # Customer Experience & CRO
    "Hotjar": ["hj('event'"], "Optimizely": ["optimizely.com/js"], "VWO": ["dev.vwo.com"],
    # Marketing Automation & CRM
    "HubSpot": ["js.hs-scripts.com", "_hsq.push"], "Salesforce Pardot": ["pi.pardot.com"], "Marketo": ["munchkin.js"],
    # Consent Management Platforms (CMP)
    "Cookiebot": ["consent.cookiebot.com"], "Usercentrics": ["app.usercentrics.eu"], "OneTrust": ["cdn.cookielaw.org"],
    # E-Commerce Platforms
    "Shopify": ["Shopify.theme", "cdn.shopify.com"], "Magento": ["mage-init"], "WooCommerce": ["/wp-content/plugins/woocommerce"],
    # Cloud & Content Delivery
    "Amazon Web Services (AWS)": ["amazonaws.com"], "Google Cloud Platform (GCP)": ["storage.googleapis.com"], "Cloudflare": ["cdn-cgi/scripts"], "Microsoft Azure": ["azureedge.net"],
    # Customer Data Platforms (CDP)
    "Segment": ["cdn.segment.com"], "Tealium": ["tags.tiqcdn.com"]
}

# --- Gemini API Konfiguration ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-flash-latest')
except KeyError:
    st.error("Der GEMINI_API_KEY ist in den Streamlit Secrets nicht hinterlegt. Bitte fügen Sie ihn hinzu.")
    st.stop()
except Exception as e:
    st.error(f"Fehler bei der Konfiguration der Gemini API: {e}")
    st.stop()

# --- Funktionen ---

def analyze_website_technologies(url):
    """Analysiert die Webseite und gtm.js-Skripte nach Technologiesignaturen."""
    found_technologies = set()
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Hebt HTTPError für schlechte Antworten (4xx oder 5xx)

        soup = BeautifulSoup(response.text, 'html.parser')

        # Durchsuche den HTML-Inhalt und alle Skripte
        all_text = response.text
        script_tags = soup.find_all('script')
        for script in script_tags:
            if script.string:
                all_text += script.string
            if script.get('src'):
                script_url = script.get('src')
                # Überprüfe gtm.js direkt
                if 'gtm.js' in script_url:
                    try:
                        gtm_response = requests.get(script_url, headers=headers, timeout=5)
                        gtm_response.raise_for_status()
                        all_text += gtm_response.text
                    except requests.exceptions.RequestException as e:
                        st.warning(f"Konnte gtm.js unter {script_url} nicht abrufen: {e}")

        # Überprüfe alle Signaturen
        for tech_name, signatures in TECHNOLOGY_SIGNATURES.items():
            for signature in signatures:
                if signature in all_text:
                    found_technologies.add(tech_name)
                    break # Eine Signatur reicht aus, um die Technologie zu erkennen

    except requests.exceptions.MissingSchema:
        st.error("Ungültige URL. Bitte stellen Sie sicher, dass die URL mit 'http://' oder 'https://' beginnt.")
        return None
    except requests.exceptions.ConnectionError:
        st.error("Verbindungsfehler. Die Webseite ist möglicherweise nicht erreichbar oder die URL ist falsch.")
        return None
    except requests.exceptions.Timeout:
        st.error("Zeitüberschreitung beim Verbindungsaufbau zur Webseite. Bitte versuchen Sie es später erneut.")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Ein unerwarteter Fehler ist aufgetreten: {e}")
        return None
    return sorted(list(found_technologies))

def get_gemini_strategic_assessment(technologies):
    """Ruft die Google Gemini API auf, um eine strategische Einschätzung zu erhalten."""
    if not technologies:
        return "Keine Technologien zur Analyse gefunden."

    tech_list_str = ", ".join(technologies)
    prompt = f"Du bist ein erfahrener Digital-Stratege. Basierend auf dieser Liste von erkannten Technologien: [{tech_list_str}], erstelle eine prägnante Analyse. Gliedere deine Antwort in drei Bereiche mit den Überschriften: **Stärken:** (1-2 Stichpunkte), **Schwächen:** (1-2 Stichpunkte) und **Größte Chance:** (ein konkreter Vorschlag)."

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"Fehler beim Aufruf der Gemini API: {e}")
        return "Die KI-Auswertung konnte nicht generiert werden."

# --- Streamlit UI ---
st.set_page_config(page_title="Digital Infrastructure Analyzer", layout="wide")

st.title("Digital Infrastructure Analyzer")

website_url = st.text_input("Geben Sie eine Website-URL ein (z.B. https://www.example.com):", "https://www.google.com")

if st.button("Analysieren"):
    if not website_url:
        st.warning("Bitte geben Sie eine Website-URL ein.")
    else:
        with st.spinner("Analysiere Webseite und erstelle KI-Bewertung..."):
            found_techs = analyze_website_technologies(website_url)

            if found_techs is not None:
                st.subheader("KI-gestützte Strategische Einschätzung")
                gemini_assessment = get_gemini_strategic_assessment(found_techs)
                st.markdown(gemini_assessment)

                st.markdown("---") # Trennlinie

                if st.checkbox("Details der erkannten Technologien anzeigen"):
                    if found_techs:
                        st.subheader("Erkannte Technologien:")
                        for tech in found_techs:
                            st.write(f"- {tech}")
                    else:
                        st.info("Es wurden keine spezifischen Technologien gefunden.")

                # Button zum Kopieren der Analyse
                if st.button("Analyse in Zwischenablage kopieren"):
                    analysis_text = f"KI-gestützte Strategische Einschätzung für {website_url}:\n\n{gemini_assessment}"
                    if found_techs:
                        analysis_text += "\n\nErkannte Technologien:\n" + "\n".join([f"- {tech}" for tech in found_techs])
                    
                    try:
                        pyperclip.copy(analysis_text)
                        st.success("Analyse erfolgreich in die Zwischenablage kopiert!")
                    except pyperclip.PyperclipException:
                        st.warning("Konnte nicht automatisch in die Zwischenablage kopieren. Bitte kopieren Sie den Text manuell.")
                        st.text_area("Manuell kopieren:", value=analysis_text, height=300)
