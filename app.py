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
        
# ==================== BLOCK 2: GTM DEEP-DIVE ====================
# Diesen KOMPLETTEN Block nach den Helper Functions (crawl_multiple_pages) 
# aber VOR der main() Function einfügen

@st.cache_data(ttl=3600)
def ultra_precise_gtm_analysis(html_content):
    """Ultra-präzise GTM-Analyse"""
    
    analysis = {
        "containers": [],
        "container_details": {},
        "datalayer": {
            "found": False,
            "events": [],
            "variables": {},
            "ecommerce": {"found": False, "type": None, "events_found": []}
        },
        "tags": {"total_count": 0, "by_type": {}, "details": []},
        "triggers": {"total_count": 0, "types_found": []},
        "variables": {"total_count": 0, "types_found": [], "custom_js": False},
        "advanced_features": {
            "server_side_tagging": False,
            "consent_mode": False,
            "cross_domain_tracking": False,
            "user_id_tracking": False,
            "custom_events": False
        },
        "implementation_quality": {
            "score": 0,
            "max_score": 100,
            "grade": "F",
            "issues": [],
            "recommendations": []
        }
    }
    
    # Container finden
    containers_found = re.findall(r'GTM-[A-Z0-9]{4,10}', html_content)
    analysis["containers"] = list(set(containers_found))
    
    if not analysis["containers"]:
        analysis["implementation_quality"]["issues"].append("❌ KRITISCH: Kein GTM-Container gefunden")
        return analysis
    
    # DataLayer Check
    if re.search(r'window\.dataLayer|dataLayer\s*=\s*\[', html_content):
        analysis["datalayer"]["found"] = True
    else:
        analysis["implementation_quality"]["issues"].append("⚠️ WARNUNG: DataLayer nicht gefunden")
    
    # DataLayer Events extrahieren
    push_patterns = [
        r'dataLayer\.push\s*\(\s*({[^}]+})\s*\)',
        r'dataLayer\.push\s*\(\s*({[^}]*{[^}]*}[^}]*})\s*\)'
    ]
    
    all_pushes = []
    for pattern in push_patterns:
        pushes = re.findall(pattern, html_content, re.DOTALL)
        all_pushes.extend(pushes)
    
    for push_str in all_pushes[:50]:  # Limit 50
        try:
            # Event-Name
            event_match = re.search(r"['\"]event['\"]:\s*['\"]([^'\"]+)['\"]", push_str)
            if event_match:
                event_name = event_match.group(1)
                if event_name and event_name not in analysis["datalayer"]["events"]:
                    analysis["datalayer"]["events"].append(event_name)
            
            # Variablen
            var_pattern = r"['\"]?([a-zA-Z_][a-zA-Z0-9_]*)['\"]?\s*:\s*(?:['\"]([^'\"]*)['\"]|(\d+\.?\d*)|({[^}]*})|(true|false))"
            for match in re.finditer(var_pattern, push_str):
                var_name = match.group(1)
                var_value = match.group(2) or match.group(3) or match.group(5) or "object"
                
                if var_name and var_name != 'event' and var_name not in analysis["datalayer"]["variables"]:
                    analysis["datalayer"]["variables"][var_name] = {
                        "sample_value": str(var_value)[:100],
                        "type": "string" if match.group(2) else "number" if match.group(3) else "boolean" if match.group(5) else "object"
                    }
            
            # E-Commerce
            ecom_indicators = ['ecommerce', 'purchase', 'add_to_cart', 'items', 'transaction']
            for indicator in ecom_indicators:
                if indicator in push_str:
                    analysis["datalayer"]["ecommerce"]["found"] = True
                    if 'items' in push_str:
                        analysis["datalayer"]["ecommerce"]["type"] = "GA4"
                    elif 'ecommerce' in push_str:
                        analysis["datalayer"]["ecommerce"]["type"] = "UA Enhanced"
                    if indicator not in analysis["datalayer"]["ecommerce"]["events_found"]:
                        analysis["datalayer"]["ecommerce"]["events_found"].append(indicator)
                    break
        except:
            continue
    
    # Container Details analysieren
    for container_id in analysis["containers"]:
        container_analysis = {
            "id": container_id,
            "accessible": False,
            "size_kb": 0,
            "tags_detected": []
        }
        
        try:
            gtm_url = f"https://www.googletagmanager.com/gtm.js?id={container_id}"
            resp = requests.get(gtm_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            
            if resp.status_code == 200:
                container_analysis["accessible"] = True
                gtm_content = resp.text
                container_analysis["size_kb"] = round(len(gtm_content) / 1024, 2)
                
                # Tag-Signaturen
                tag_sigs = {
                    "Google Analytics 4": [r'google-analytics\.com/g/collect', r'measurement_id.*G-'],
                    "Google Analytics Universal": [r'google-analytics\.com/analytics\.js', r'UA-\d+'],
                    "Google Ads": [r'googleadservices\.com', r'AW-\d+'],
                    "Campaign Manager 360": [r'fls\.doubleclick\.net', r'2mdn\.net'],
                    "Meta Pixel": [r'connect\.facebook\.net', r'facebook\.com/tr'],
                    "LinkedIn Insight": [r'snap\.licdn\.com'],
                    "TikTok Pixel": [r'analytics\.tiktok\.com'],
                    "Twitter Pixel": [r'static\.ads-twitter\.com'],
                    "Hotjar": [r'static\.hotjar\.com'],
                    "Microsoft Clarity": [r'clarity\.ms'],
                    "HubSpot": [r'js\.hs-scripts\.com'],
                    "Salesforce": [r'pi\.pardot\.com']
                }
                
                for tag_name, patterns in tag_sigs.items():
                    for pattern in patterns:
                        if re.search(pattern, gtm_content, re.IGNORECASE):
                            container_analysis["tags_detected"].append(tag_name)
                            
                            if tag_name not in analysis["tags"]["by_type"]:
                                analysis["tags"]["by_type"][tag_name] = {"count": 0, "containers": []}
                            
                            analysis["tags"]["by_type"][tag_name]["count"] += 1
                            analysis["tags"]["by_type"][tag_name]["containers"].append(container_id)
                            break
                
                analysis["tags"]["total_count"] = len(analysis["tags"]["by_type"])
                
                # Triggers
                trigger_types = {
                    "Page View": [r'pageview', r'gtm\.js'],
                    "Click": [r'gtm\.click', r'linkClick'],
                    "Form Submit": [r'gtm\.formSubmit'],
                    "Scroll Depth": [r'scroll.*depth'],
                    "Timer": [r'gtm\.timer']
                }
                
                for trigger, patterns in trigger_types.items():
                    for pattern in patterns:
                        if re.search(pattern, gtm_content, re.IGNORECASE):
                            if trigger not in analysis["triggers"]["types_found"]:
                                analysis["triggers"]["types_found"].append(trigger)
                            break
                
                analysis["triggers"]["total_count"] = len(analysis["triggers"]["types_found"])
                
                # Advanced Features
                if re.search(r'sgtm\.|server-container|\.run\.app', gtm_content, re.IGNORECASE):
                    analysis["advanced_features"]["server_side_tagging"] = True
                
                if re.search(r'consent.*default|ad_storage|analytics_storage', gtm_content):
                    analysis["advanced_features"]["consent_mode"] = True
                
                if re.search(r'linker|allowLinker', gtm_content):
                    analysis["advanced_features"]["cross_domain_tracking"] = True
                
                if re.search(r'user_id|userId', gtm_content):
                    analysis["advanced_features"]["user_id_tracking"] = True
                
                if re.search(r'customEvent', gtm_content):
                    analysis["advanced_features"]["custom_events"] = True
        
        except:
            pass
        
        analysis["container_details"][container_id] = container_analysis
    
    # Quality Score
    score = 0
    if analysis["datalayer"]["found"]: score += 10
    if len(analysis["datalayer"]["events"]) > 0: score += 10
    if len(analysis["datalayer"]["variables"]) >= 3: score += 10
    if analysis["tags"]["total_count"] >= 5: score += 20
    elif analysis["tags"]["total_count"] >= 3: score += 15
    elif analysis["tags"]["total_count"] >= 1: score += 10
    if analysis["triggers"]["total_count"] >= 5: score += 15
    elif analysis["triggers"]["total_count"] >= 3: score += 10
    if analysis["datalayer"]["ecommerce"]["found"]: score += 10
    
    advanced_count = sum(1 for v in analysis["advanced_features"].values() if v)
    score += min(20, advanced_count * 4)
    
    analysis["implementation_quality"]["score"] = score
    percentage = (score / 100) * 100
    
    if percentage >= 90: analysis["implementation_quality"]["grade"] = "A+"
    elif percentage >= 80: analysis["implementation_quality"]["grade"] = "A"
    elif percentage >= 70: analysis["implementation_quality"]["grade"] = "B"
    elif percentage >= 60: analysis["implementation_quality"]["grade"] = "C"
    elif percentage >= 50: analysis["implementation_quality"]["grade"] = "D"
    else: analysis["implementation_quality"]["grade"] = "F"
    
    # Issues
    if not analysis["datalayer"]["found"]:
        analysis["implementation_quality"]["recommendations"].append("🔧 DataLayer implementieren: window.dataLayer = [];")
    
    if len(analysis["datalayer"]["events"]) == 0 and analysis["datalayer"]["found"]:
        analysis["implementation_quality"]["issues"].append("⚠️ Keine Events im DataLayer")
    
    if analysis["tags"]["total_count"] < 2:
        analysis["implementation_quality"]["recommendations"].append("🔧 Mehr Tags hinzufügen: Analytics, Ads, Remarketing")
    
    if not analysis["advanced_features"]["consent_mode"]:
        analysis["implementation_quality"]["issues"].append("⚠️ Consent Mode v2 fehlt (GDPR)")
        analysis["implementation_quality"]["recommendations"].append("🔧 Consent Mode für GDPR-Compliance")
    
    if not analysis["advanced_features"]["server_side_tagging"]:
        analysis["implementation_quality"]["recommendations"].append("💡 Server-Side Tagging für bessere Datenqualität (ROI: 400%)")
    
    return analysis


def display_gtm_analysis(gtm_data):
    """Zeigt GTM-Analyse im modernen UI"""
    
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<h2 class="section-header">🔬 GTM Deep-Dive Analysis</h2>', unsafe_allow_html=True)
    
    # Container
    if gtm_data["containers"]:
        st.markdown(f"### 📦 GTM Container ({len(gtm_data['containers'])})")
        for container_id in gtm_data["containers"]:
            details = gtm_data["container_details"].get(container_id, {})
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**{container_id}**")
            with col2:
                if details.get("accessible"):
                    st.markdown(f'<span class="badge badge-success">✓ {details.get("size_kb", 0)} KB</span>', unsafe_allow_html=True)
    
    # Quality Score
    st.markdown("### 🎯 Implementation Quality")
    quality = gtm_data["implementation_quality"]
    score_pct = (quality["score"] / 100) * 100
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f'<div class="metric-modern"><h2>{quality["score"]}</h2><p>von 100 Punkten</p></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="metric-modern"><h2>{quality["grade"]}</h2><p>Grade</p></div>', unsafe_allow_html=True)
    with col3:
        color = "#10b981" if score_pct >= 70 else "#f59e0b" if score_pct >= 50 else "#ef4444"
        st.markdown(f'<div class="progress-modern"><div class="progress-bar" style="width: {score_pct}%; background: {color};"></div></div>', unsafe_allow_html=True)
    
    # DataLayer
    st.markdown("### 📊 DataLayer")
    dl = gtm_data["datalayer"]
    
    if dl["found"]:
        st.markdown(f'<span class="badge badge-success">✓ DataLayer Found</span>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Events ({len(dl['events'])})**")
            for evt in dl["events"][:8]:
                st.markdown(f'<div class="tool-item">🎯 {evt}</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"**Variables ({len(dl['variables'])})**")
            for var, data in list(dl["variables"].items())[:8]:
                st.markdown(f'<div class="tool-item">📌 {var}<br><small>{data["type"]}: {data["sample_value"][:40]}</small></div>', unsafe_allow_html=True)
        
        if dl["ecommerce"]["found"]:
            st.markdown(f'<span class="badge badge-success">✓ E-Commerce: {dl["ecommerce"]["type"]}</span>', unsafe_allow_html=True)
    else:
        st.markdown(f'<span class="badge badge-danger">✗ DataLayer fehlt</span>', unsafe_allow_html=True)
    
    # Tags
    st.markdown(f"### 🏷️ Tags ({gtm_data['tags']['total_count']})")
    for tag, data in gtm_data["tags"]["by_type"].items():
        st.markdown(f'<div class="tool-item"><strong>{tag}</strong> <span class="badge badge-info">{data["count"]}x</span></div>', unsafe_allow_html=True)
    
    # Triggers & Advanced
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"### ⚡ Triggers ({gtm_data['triggers']['total_count']})")
        for t in gtm_data["triggers"]["types_found"]:
            st.markdown(f'<span class="badge badge-info">{t}</span>', unsafe_allow_html=True)
    
    with col2:
        st.markdown("### 🚀 Advanced Features")
        for name, enabled in gtm_data["advanced_features"].items():
            label = name.replace("_", " ").title()
            badge = "badge-success" if enabled else "badge-warning"
            icon = "✓" if enabled else "✗"
            st.markdown(f'<span class="badge {badge}">{icon} {label}</span>', unsafe_allow_html=True)
    
    # Issues & Recommendations
    if quality["issues"]:
        st.markdown("### ⚠️ Issues")
        for issue in quality["issues"]:
            st.markdown(f'<div class="recommendation-card">{issue}</div>', unsafe_allow_html=True)
    
    if quality["recommendations"]:
        st.markdown("### 💡 Recommendations")
        for rec in quality["recommendations"]:
            st.markdown(f'<div class="recommendation-card info">{rec}</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
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
       # GTM Analyse
        if "gtm_analysis" not in st.session_state:
            with st.spinner("🔬 Analysiere GTM..."):
                gtm_results = ultra_precise_gtm_analysis(crawl['combined_html'])
                st.session_state.gtm_analysis = gtm_results
        
        if "gtm_analysis" in st.session_state:
            display_gtm_analysis(st.session_state.gtm_analysis)
        # Download Raw HTML (für Testing)
        with st.expander("🔍 Raw HTML anzeigen (für Debugging)"):
            st.text_area("Combined HTML", crawl['combined_html'][:5000] + "...", height=200)

if __name__ == "__main__":
    main()
