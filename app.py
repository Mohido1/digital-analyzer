# ERSETZEN SIE DIE GESAMTE FUNKTION MIT DIESER VERSION
def generate_dossier(infra_data: dict, website_text: str) -> str:
    """
    Erstellt den forensischen Audit mit Beweisführung mithilfe der Gemini API.
    Diese Version nutzt eine sicherere Methode zur Prompt-Erstellung.
    """
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
    except (KeyError, FileNotFoundError):
        st.error("GEMINI_API_KEY nicht in den Streamlit Secrets gefunden. Bitte fügen Sie ihn hinzu.")
        return None

    evidence = {
        "Forensische Analyse": infra_data,
        "Webseiten-Inhalt": website_text[:40000] # Gekürzt, um das Limit nicht zu sprengen
    }
    evidence_json = json.dumps(evidence, indent=2, ensure_ascii=False)

    # Statische Vorlage des Prompts mit einem einzigen, sicheren Platzhalter
    prompt_template = """
Du bist ein Partner bei einer Top-Management-Beratung (z.B. McKinsey, BCG) mit Spezialisierung auf digitale Transformation und datengetriebene Geschäftsmodelle. Deine Aufgabe ist es, ein strategisches Dossier für eine Vorstandssitzung zu erstellen.

Beweismittel: {}

Dein Auftrag: Erstelle einen strategischen Bericht. Sei präzise, direkt und begründe jeden Punkt mit klaren Geschäftsrisiken oder -chancen.

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
- **Status:** [Bewerte das gefundene Tag Management System aus den Beweismitteln]

**2. Data & Analytics**
- **Gefundene Tools:** [Liste gefundene Tools. Wenn leer: "Keine"]
- **Status & Implikation:** [Wenn keine Tools gefunden wurden, schreibe: "🔴 Lücke: Dem Unternehmen fehlt die grundlegendste Fähigkeit, das Nutzerverhalten zu analysieren. Entscheidungen werden 'blind' getroffen."]
- **Reifegrad (1-5):** [Bewerte von 1-5]

**3. Advertising & Kundengewinnung**
- **Gefundene Tools:** [Liste gefundene Tools, z.B. 🟢 Meta Pixel, 🟡 Google Ads (ohne Events)]
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
    
    # Die dynamischen "Beweismittel" werden sicher in den Platzhalter eingefügt
    prompt = prompt_template.format(evidence_json)
    
    try:
        model = genai.GenerativedaMlo('gemini-1.5-flash-latest')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"Fehler bei der Kommunikation mit der Gemini API: {e}")
        return None
