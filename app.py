# TEMPORÄRER DEBUG-CODE ZUM EINFÜGEN
if st.button("DATEN-SAMMLUNG TESTEN", type="primary"):
    if not url:
        st.warning("Bitte geben Sie eine URL ein.")
    else:
        if not re.match(r'http(s)?://', url):
            url = 'https://' + url

        st.info("Führe Datensammlung durch...")

        # Reset der Session-Daten
        st.session_state.infra = {}
        st.session_state.text = ""

        # Führe beide Sammel-Funktionen aus
        infra_data = analyze_infrastructure(url)
        website_text = scrape_website_text(url)

        # Zeige die rohen Ergebnisse direkt an
        st.markdown("---")
        st.subheader("Beweismittel 1: Ergebnis der Infrastruktur-Analyse (JSON)")
        st.json(infra_data)

        st.markdown("---")
        st.subheader("Beweismittel 2: Extrahierter Webseiten-Text")
        st.text_area("Gesammelter Text:", website_text, height=400)
