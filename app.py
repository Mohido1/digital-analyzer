import streamlit as st
import google.generativeai as genai

# --- App-Konfiguration ---
# Setzt den Titel und das Icon, die im Browser-Tab angezeigt werden.
# Dies sollte der erste Streamlit-Befehl im Skript sein.
st.set_page_config(page_title="Gemini Modell-Liste", page_icon="🤖")


# --- Hauptteil der App ---

# 1. Überschrift erstellen
st.header("Verfügbare KI-Modelle von Gemini")
st.write(
    "Diese App zeigt alle Modelle an, die über die Google Gemini API verfügbar sind "
    "und die `generateContent`-Methode unterstützen."
)

# 2. API-Schlüssel sicher aus den Streamlit Secrets lesen
try:
    # Lädt den API-Schlüssel aus dem Streamlit Secret Management.
    api_key = st.secrets["GEMINI_API_KEY"]
    # Konfiguriert die google.generativeai Bibliothek mit dem Schlüssel.
    genai.configure(api_key=api_key)

# 3. Fehlerbehandlung für den API-Schlüssel
except (KeyError, FileNotFoundError):
    # Zeigt eine deutliche Fehlermeldung an, wenn der Schlüssel nicht gefunden wird.
    st.error("⚠️ **Fehler:** Der `GEMINI_API_KEY` wurde nicht gefunden.")
    st.info(
        "Bitte füge deinen Gemini API-Schlüssel zu den Streamlit Secrets hinzu. "
        "Eine Anleitung findest du im ausklappbaren Bereich unten."
    )
    # Stoppt die Ausführung der App, da ohne Schlüssel keine API-Anfrage möglich ist.
    st.stop()


# 4. Modelle von der API abrufen und anzeigen
try:
    st.markdown("---")
    st.subheader("Unterstützte Modelle:")

    # Zeigt einen "Spinner" (Ladeanimation), während die Daten im Hintergrund abgerufen werden.
    with st.spinner("Modelle werden von der Google API geladen..."):
        # 5. Alle Modelle auflisten
        all_models = genai.list_models()

        # 6. Modelle durchgehen und filtern
        # Erstellt eine Liste nur mit den Namen der Modelle, die 'generateContent' unterstützen.
        supported_models = [
            model.name for model in all_models if 'generateContent' in model.supported_generation_methods
        ]

    # Überprüfen, ob Modelle gefunden wurden
    if supported_models:
        # Die gefilterten und sortierten Modellnamen anzeigen
        for model_name in sorted(supported_models):
            st.text(f"✅ {model_name}")
    else:
        st.warning("Keine Modelle gefunden, die 'generateContent' unterstützen.")

# 7. Fehlerbehandlung für die API-Verbindung
except Exception as e:
    st.error(f"Ein Fehler ist bei der Verbindung zur API aufgetreten: {e}")
    st.info(
        "Stelle sicher, dass dein API-Schlüssel gültig ist und deine Internetverbindung funktioniert."
    )


# --- Anleitung zur Einrichtung ---
st.markdown("---")
with st.expander("❓ Anleitung: Wie richte ich die App ein?"):
    st.markdown("""
    Um diese App selbst zu betreiben, benötigst du einen API-Schlüssel.

    1.  **Erstelle einen Gemini API-Schlüssel**: Gehe zum [Google AI Studio](https://aistudio.google.com/app/apikey) und erstelle einen kostenlosen Schlüssel.
    2.  **Füge den Schlüssel zu Streamlit Secrets hinzu**:
        * Wenn du die App auf der Streamlit Community Cloud bereitstellst, gehe zu den App-Einstellungen (`Settings > Secrets`).
        * Erstelle ein neues Secret mit dem Namen `GEMINI_API_KEY`.
        * Füge deinen API-Schlüssel als Wert ein und speichere.
    3.  **Fertig!** Die App verbindet sich nun sicher mit der API.
    """)
