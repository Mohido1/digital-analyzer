"""
MarTech Analyzer Pro v5.0 - Block 1: Core & Modern Design
Installiere: pip install streamlit requests beautifulsoup4 google-generativeai pandas python-whois
"""

import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import re
from urllib.parse import urljoin, urlparse
from datetime import datetime
import sqlite3
import pandas as pd
import time

try:
    import whois
    WHOIS_AVAILABLE = True
except ImportError:
    WHOIS_AVAILABLE = False
    st.warning("⚠️ python-whois nicht installiert. `pip install python-whois`")

# ==================== CONFIGURATION ====================
st.set_page_config(
    page_title="MarTech Analyzer Pro v5.0",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== MODERN GLASSMORPHISM DESIGN ====================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap');
    
    * {
        font-family: 'Inter', sans-serif;
    }
    
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 3rem 2rem;
        border-radius: 20px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 20px 60px rgba(102, 126, 234, 0.4);
        animation: fadeIn 0.5s ease-in;
    }
    
    .glass-card {
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border-radius: 20px;
        padding: 2rem;
        border: 1px solid rgba(255, 255, 255, 0.3);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        margin-bottom: 1.5rem;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    
    .glass-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 12px 48px rgba(0, 0, 0, 0.15);
    }
    
    .metric-modern {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 20px;
        text-align: center;
        color: white;
        box-shadow: 0 10px 40px rgba(102, 126, 234, 0.3);
        transition: transform 0.3s ease;
    }
    
    .metric-modern:hover {
        transform: scale(1.05);
    }
    
    .metric-modern h2 {
        font-size: 3.5rem;
        font-weight: 800;
        margin: 0;
        line-height: 1;
    }
    
    .metric-modern p {
        font-size: 0.9rem;
        opacity: 0.9;
        margin: 0.5rem 0 0 0;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    .badge {
        display: inline-block;
        padding: 0.4rem 1rem;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        margin: 0.25rem;
    }
    
    .badge-success { background: #10b981; color: white; }
    .badge-warning { background: #f59e0b; color: white; }
    .badge-danger { background: #ef4444; color: white; }
    .badge-info { background: #3b82f6; color: white; }
    .badge-purple { background: #8b5cf6; color: white; }
    
    .progress-modern {
        background: #e5e7eb;
        height: 14px;
        border-radius: 10px;
        overflow: hidden;
        margin: 1rem 0;
        box-shadow: inset 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .progress-bar {
        height: 100%;
        border-radius: 10px;
        transition: width 1s ease;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        box-shadow: 0 2px 8px rgba(102, 126, 234, 0.4);
    }
    
    .tool-item {
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
        padding: 1rem 1.5rem;
        border-radius: 12px;
        margin: 0.5rem 0;
        border-left: 4px solid #667eea;
        transition: all 0.3s ease;
    }
    
    .tool-item:hover {
        transform: translateX(5px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.2);
    }
    
    .recommendation-card {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(239, 68, 68, 0.05) 100%);
        border-left: 5px solid #ef4444;
        padding: 1.5rem;
        border-radius: 12px;
        margin: 1rem 0;
        transition: transform 0.3s ease;
    }
    
    .recommendation-card:hover {
        transform: translateX(5px);
    }
    
    .recommendation-card.warning {
        background: linear-gradient(135deg, rgba(245, 158, 11, 0.1) 0%, rgba(245, 158, 11, 0.05) 100%);
        border-left-color: #f59e0b;
    }
    
    .recommendation-card.info {
        background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(59, 130, 246, 0.05) 100%);
        border-left-color: #3b82f6;
    }
    
    .stButton>button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 0.75rem 2rem;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4);
    }
    
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(-20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .section-header {
        font-size: 1.5rem;
        font-weight: 700;
        color: #1f2937;
        margin: 2rem 0 1rem 0;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# ==================== DATABASE SETUP ====================
def init_database():
    """Initialisiert SQLite-Datenbank"""
    conn = sqlite3.connect('martech_v5.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT NOT NULL,
        domain TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        overall_score INTEGER,
        raw_data TEXT,
        company_data TEXT,
        gtm_data TEXT,
        tools_data TEXT,
        recommendations TEXT
    )''')
    conn.commit()
    conn.close()

def save_analysis(url, domain, score, raw_data, company_data, gtm_data, tools_data, recommendations):
    """Speichert Analyse in DB"""
    conn = sqlite3.connect('martech_v5.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''INSERT INTO analyses 
                 (url, domain, timestamp, overall_score, raw_data, company_data, gtm_data, tools_data, recommendations)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (url, domain, datetime.now().isoformat(), score,
               json.dumps(raw_data), json.dumps(company_data), json.dumps(gtm_data),
               json.dumps(tools_data), json.dumps(recommendations)))
    conn.commit()
    conn.close()

def get_analysis_history(limit=20):
    """Holt Analyse-Historie"""
    conn = sqlite3.connect('martech_v5.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('SELECT id, url, domain, timestamp, overall_score FROM analyses ORDER BY timestamp DESC LIMIT ?', (limit,))
    results = c.fetchall()
    conn.close()
    return results

# ==================== HELPER FUNCTIONS ====================
def crawl_multiple_pages(base_url, max_pages=7):
    """Intelligentes Multi-Page Crawling"""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    urls_to_visit = {base_url}
    processed_urls = set()
    all_html = ""
    pages_info = []
    
    # Priority Keywords für intelligente Seitenauswahl
    priority_keywords = [
        'about', 'ueber', 'uber', 'company', 'unternehmen',
        'products', 'produkte', 'services', 'leistungen',
        'pricing', 'preise', 'contact', 'kontakt',
        'impressum', 'imprint', 'team'
    ]
    
    try:
        # Startseite laden
        resp = requests.get(base_url, timeout=15, headers=headers)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, 'html.parser')
            processed_urls.add(base_url)
            all_html += resp.text + "\n"
            
            title = soup.title.string if soup.title else "Homepage"
            pages_info.append({
                "url": base_url,
                "title": title,
                "status": "✓ Analyzed"
            })
            
            # Links sammeln
            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin(base_url, href)
                
                # Nur interne Links
                if urlparse(full_url).netloc == urlparse(base_url).netloc:
                    # Priorisiere relevante Seiten
                    if any(kw in full_url.lower() for kw in priority_keywords):
                        urls_to_visit.add(full_url)
        
        # Weitere Seiten crawlen
        for url in list(urls_to_visit)[1:max_pages]:
            if url in processed_urls:
                continue
            
            try:
                time.sleep(0.3)  # Rate limiting
                resp = requests.get(url, timeout=10, headers=headers)
                
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.content, 'html.parser')
                    all_html += resp.text + "\n"
                    processed_urls.add(url)
                    
                    title = soup.title.string if soup.title else "Page"
                    pages_info.append({
                        "url": url,
                        "title": title,
                        "status": "✓ Analyzed"
                    })
            except:
                continue
        
        return {
            "combined_html": all_html,
            "pages": pages_info,
            "total_pages": len(processed_urls)
        }
        
    except Exception as e:
        return None

# ==================== MAIN UI ====================
def main():
    # DB initialisieren
    init_database()
    
    # Header
    st.markdown("""
        <div class="main-header">
            <h1 style="margin:0; font-size: 2.8rem; font-weight: 800;">🎯 MarTech Analyzer Pro v5.0</h1>
            <p style="margin:0.5rem 0 0 0; font-size: 1.1rem; opacity: 0.95; font-weight: 400;">
                Präzise GTM-Analyse • Company Intelligence • Konkrete Empfehlungen
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("### 🚀 Analyse-Module")
        st.markdown("""
        **Block 1:** ✅ Core & Design  
        **Block 2:** ⏳ GTM Deep-Dive  
        **Block 3:** ⏳ Company Intel  
        **Block 4:** ⏳ Tool Detection  
        **Block 5:** ⏳ Recommendations
        """)
        
        st.markdown("---")
        st.markdown("### ⚙️ Status")
        
        if WHOIS_AVAILABLE:
            st.success("✓ Whois verfügbar")
        else:
            st.error("✗ Whois fehlt")
        
        try:
            import google.generativeai as genai
            if "GEMINI_API_KEY" in st.secrets:
                st.success("✓ Gemini AI")
            else:
                st.warning("⚠ Gemini Key fehlt")
        except:
            st.warning("⚠ Gemini nicht installiert")
    
    # Main Input
    col1, col2 = st.columns([3, 1])
    
    with col1:
        url_input = st.text_input(
            "🌐 Website-URL eingeben",
            placeholder="https://www.beispiel-unternehmen.de",
            help="Vollständige URL mit https:// erforderlich"
        )
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        analyze_button = st.button("🚀 Analyse starten", type="primary", use_container_width=True)
    
    # Analyse starten
    if analyze_button and url_input:
        if not url_input.startswith(('http://', 'https://')):
            st.error("❌ Bitte vollständige URL eingeben (https://...)")
        else:
            with st.spinner("🔬 Crawle Website..."):
                progress = st.progress(0)
                
                # Crawling
                progress.progress(30)
                crawl_data = crawl_multiple_pages(url_input, max_pages=7)
                
                if crawl_data:
                    progress.progress(100)
                    
                    # Session State speichern
                    st.session_state.crawl_data = crawl_data
                    st.session_state.url = url_input
                    
                    progress.empty()
                    st.success(f"✅ {crawl_data['total_pages']} Seiten erfolgreich analysiert!")
                    st.rerun()
    
    # Ergebnisse anzeigen
    if "crawl_data" in st.session_state:
        crawl = st.session_state.crawl_data
        
        st.markdown("---")
        
        # Crawl Info
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown(f'<h3 class="section-header">📄 Multi-Page Crawl Ergebnis</h3>', unsafe_allow_html=True)
        st.markdown(f"**{crawl['total_pages']} Seiten** analysiert:")
        
        for page in crawl['pages']:
            st.markdown(f"""
                <div class="tool-item">
                    <strong>{page['status']}</strong> {page['title']}<br>
                    <small style="opacity: 0.7;">{page['url']}</small>
                </div>
            """, unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Info: Weitere Blöcke folgen
        st.info("📦 **Block 1 abgeschlossen!** Die weiteren Analyse-Module (GTM, Company Intel, Tools, Recommendations) folgen in den nächsten Blöcken.")
        
        # Download Raw HTML (für Testing)
        with st.expander("🔍 Raw HTML anzeigen (für Debugging)"):
            st.text_area("Combined HTML", crawl['combined_html'][:5000] + "...", height=200)

if __name__ == "__main__":
    main()
