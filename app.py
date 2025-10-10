# NEUE VERSION HIER EINFÜGEN
def generate_audit(infra_data: dict, website_text: str, company_name: str) -> str:
    """
    Erstellt den forensischen Audit und nutzt den vorab extrahierten Firmennamen.
    """
    prompt = f"""
Du bist ein Senior Digital Forensics Analyst. Deine Aufgabe ist es, einen unangreifbaren Audit für unser Sales-Team zu erstellen, bei dem jede Kernaussage mit einem Beweis untermauert wird.

Beweismittel: {json.dumps(infra_data, indent=2, ensure_ascii=False)}

Dein Auftrag: Erstelle einen forensischen Bericht. Halte dich exakt an die folgende Berichtsstruktur.

**Berichtsstruktur (Markdown):**

# Forensischer Digital-Audit (mit Beweisführung)

---

## Teil 1: Firmenprofil
- **Unternehmen:** {company_name}
- **Kernbotschaft:** [Fasse die Hauptbotschaft oder den Slogan der Webseite in einem Satz zusammen]
- **Tätigkeit & Branche:** [Beschreibe detailliert, was die Firma macht und in welcher Branche sie tätig ist]
- **Zielgruppe:** [Leite aus der Sprache und den Angeboten ab, wer die typischen Kunden sind]

---

[... Rest des KI-Prompts bleibt exakt gleich ...]
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
