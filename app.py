import streamlit as st
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import json
import re
from urllib.parse import urljoin, urlparse, quote_plus
from datetime import datetime
import sqlite3
import pandas as pd
import time
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

try:
    import whois
    WHOIS_AVAILABLE = True
except ImportError:
    WHOIS_AVAILABLE = False

# ==================== CONFIG ====================
st.set_page_config(page_title="MarTech Analyzer Pro v4.0", page_icon="🎯", layout="wide")
PRIMARY_COLOR = "#174f78"
ACCENT_COLOR = "#ffab40"

st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap');
html, body, [class*="css"] {{ font-family: 'Montserrat', sans-serif; font-size: 14px; }}
.main-header {{ background: linear-gradient(135deg, {PRIMARY_COLOR} 0%, #1a5f8a 100%); padding: 2rem; border-radius: 10px; color: white; margin-bottom: 2rem; }}
.metric-card {{ background: linear-gradient(135deg, {PRIMARY_COLOR} 0%, #2a6f98 100%); color: white; padding: 1.5rem; border-radius: 8px; text-align: center; }}
.insight-card {{ background: white; border-left: 5px solid {ACCENT_COLOR}; padding: 1.5rem; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 1rem; }}
</style>""", unsafe_allow_html=True)

# ==================== DATABASE ====================
def init_db():
    conn = sqlite3.connect('martech_pro.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS analyses (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT, domain TEXT, 
                 timestamp TEXT, overall_score INTEGER, raw_data TEXT, gtm_analysis TEXT, company_data TEXT)''')
    conn.commit()
    conn.close()

def save_analysis(url, domain, score, raw, gtm_data, company_data):
    conn = sqlite3.connect('martech_pro.db')
    c = conn.cursor()
    c.execute('INSERT INTO analyses (url, domain, timestamp, overall_score, raw_data, gtm_analysis, company_data) VALUES (?, ?, ?, ?, ?, ?, ?)',
              (url, domain, datetime.now().isoformat(), score, json.dumps(raw), json.dumps(gtm_data), json.dumps(company_data)))
    conn.commit()
    conn.close()

# ==================== DEEP GTM ANALYSIS ====================
@st.cache_data(ttl=3600)
def deep_gtm_analysis(gtm_id, html_content):
    """Tiefe GTM-Analyse: Container, DataLayer, Events, Tags"""
    analysis = {
        "container_id": gtm_id,
        "datalayer_found": False,
        "datalayer_events": [],
        "datalayer_variables": [],
        "tags_detected": [],
        "triggers_detected": [],
        "implementation_quality": 0,
        "issues": [],
        "gtm_config": {}
    }
    
    # GTM.js Container laden
    try:
        gtm_url = f"https://www.googletagmanager.com/gtm.js?id={gtm_id}"
        resp = requests.get(gtm_url, timeout=10)
        if resp.status_code == 200:
            gtm_content = resp.text
            
            # Analysiere GTM Container-Konfiguration
            analysis["gtm_config"] = {
                "size_kb": round(len(gtm_content) / 1024, 2),
                "minified": ".min." in gtm_url or len(gtm_content) < 50000
            }
            
            # Erkenne Tags im Container
            tag_patterns = {
                "Google Analytics": r"google-analytics\.com|googletagmanager\.com.*analytics",
                "Google Ads": r"googleadservices\.com|googlesyndication",
                "Meta Pixel": r"facebook\.com/tr|fbevents",
                "LinkedIn": r"snap\.licdn\.com|linkedin.*insight",
                "Floodlight": r"fls\.doubleclick\.net",
                "Hotjar": r"hotjar\.com",
                "Custom HTML": r"<script|customScripts"
            }
            
            for tag_name, pattern in tag_patterns.items():
                if re.search(pattern, gtm_content, re.IGNORECASE):
                    analysis["tags_detected"].append(tag_name)
            
            # Trigger-Analyse
            trigger_types = []
            if re.search(r"pageview|gtm\.js", gtm_content, re.IGNORECASE):
                trigger_types.append("Pageview")
            if re.search(r"click|gtm\.click", gtm_content, re.IGNORECASE):
                trigger_types.append("Click")
            if re.search(r"formSubmit|submit", gtm_content, re.IGNORECASE):
                trigger_types.append("Form Submit")
            if re.search(r"timer|interval", gtm_content, re.IGNORECASE):
                trigger_types.append("Timer")
            if re.search(r"scroll|depth", gtm_content, re.IGNORECASE):
                trigger_types.append("Scroll")
            
            analysis["triggers_detected"] = trigger_types
            
    except Exception as e:
        analysis["issues"].append(f"GTM Container nicht erreichbar: {e}")
    
    # DataLayer-Analyse im HTML
    if re.search(r"window\.dataLayer\s*=|dataLayer\s*=\s*\[", html_content):
        analysis["datalayer_found"] = True
        
        # Extrahiere dataLayer.push Events
        push_pattern = r"dataLayer\.push\s*\(\s*\{([^}]+)\}\s*\)"
        pushes = re.findall(push_pattern, html_content)
        
        for push in pushes[:20]:  # Limit auf 20 Events
            # Extrahiere 'event'-Werte
            event_match = re.search(r"['\"]event['\"]:\s*['\"]([^'\"]+)['\"]", push)
            if event_match:
                event_name = event_match.group(1)
                if event_name not in analysis["datalayer_events"]:
                    analysis["datalayer_events"].append(event_name)
            
            # Extrahiere Variablen (außer 'event')
            var_matches = re.findall(r"['\"]([a-zA-Z_][a-zA-Z0-9_]*)['\"]:\s*['\"]?([^,'\"}\]]+)['\"]?", push)
            for var_name, var_value in var_matches:
                if var_name != 'event' and var_name not in [v["name"] for v in analysis["datalayer_variables"]]:
                    analysis["datalayer_variables"].append({
                        "name": var_name,
                        "sample_value": var_value.strip()[:50]
                    })
    
    # Implementation Quality Score
    quality = 0
    if analysis["datalayer_found"]:
        quality += 30
    if len(analysis["datalayer_events"]) > 0:
        quality += 20
    if len(analysis["datalayer_variables"]) > 3:
        quality += 15
    if len(analysis["tags_detected"]) > 2:
        quality += 20
    if "Form Submit" in analysis["triggers_detected"]:
        quality += 10
    if "Scroll" in analysis["triggers_detected"]:
        quality += 5
    
    analysis["implementation_quality"] = min(100, quality)
    
    # Issues identifizieren
    if not analysis["datalayer_found"]:
        analysis["issues"].append("⚠️ Kein dataLayer gefunden - Tracking möglicherweise fehlerhaft")
    if len(analysis["datalayer_events"]) == 0:
        analysis["issues"].append("⚠️ Keine Events im dataLayer - Event-Tracking fehlt")
    if len(analysis["tags_detected"]) < 2:
        analysis["issues"].append("⚠️ Sehr wenige Tags erkannt - GTM wird nicht ausgenutzt")
    
    return analysis

# ==================== COMPANY INTELLIGENCE ====================
@st.cache_data(ttl=3600)
def get_company_intelligence(domain, html_content):
    """Sammelt Firmeninformationen aus Website + externen Quellen"""
    company = {
        "name": None,
        "industry": None,
        "description": None,
        "size_estimate": None,
        "headquarters": None,
        "founded": None,
        "revenue_estimate": None,
        "business_model": None,
        "target_audience": None,
        "products_services": [],
        "social_media": {},
        "technologies_used": []
    }
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 1. Firmenname aus mehreren Quellen
    # - Title Tag
    if soup.title:
        title = soup.title.string
        company["name"] = title.split('|')[0].split('-')[0].strip() if title else None
    
    # - Meta Tags
    for meta in soup.find_all('meta'):
        if meta.get('property') == 'og:site_name' or meta.get('name') == 'application-name':
            company["name"] = meta.get('content')
            break
    
    # 2. Branche/Industrie aus Keywords & Content
    industry_keywords = {
        "E-Commerce": ["shop", "store", "buy", "cart", "checkout", "product", "woocommerce", "shopify"],
        "SaaS/Software": ["software", "platform", "cloud", "api", "saas", "dashboard", "login", "pricing"],
        "Finance/Banking": ["bank", "financial", "investment", "insurance", "loan", "credit"],
        "Healthcare": ["health", "medical", "clinic", "hospital", "patient", "doctor"],
        "Education": ["education", "learning", "course", "training", "university", "school"],
        "Real Estate": ["property", "real estate", "apartment", "house", "rent"],
        "Travel/Hospitality": ["hotel", "travel", "booking", "flight", "vacation"],
        "Media/Publishing": ["news", "article", "blog", "magazine", "publishing"],
        "Agency/Consulting": ["agency", "consulting", "services", "solutions", "strategy"],
        "Manufacturing": ["manufacturing", "production", "factory", "industrial"]
    }
    
    html_lower = html_content.lower()
    industry_scores = {}
    for industry, keywords in industry_keywords.items():
        score = sum(html_lower.count(kw) for kw in keywords)
        if score > 0:
            industry_scores[industry] = score
    
    if industry_scores:
        company["industry"] = max(industry_scores, key=industry_scores.get)
    
    # 3. Business Model erkennen
    if any(kw in html_lower for kw in ["buy", "shop", "cart", "price"]):
        company["business_model"] = "B2C E-Commerce"
    elif any(kw in html_lower for kw in ["enterprise", "business", "solution", "b2b"]):
        company["business_model"] = "B2B"
    elif any(kw in html_lower for kw in ["free trial", "pricing", "subscription"]):
        company["business_model"] = "SaaS/Subscription"
    
    # 4. Firmenbeschreibung aus Meta Description
    for meta in soup.find_all('meta'):
        if meta.get('name') == 'description' or meta.get('property') == 'og:description':
            company["description"] = meta.get('content', '')[:300]
            break
    
    # 5. Social Media Links
    social_patterns = {
        "LinkedIn": r"linkedin\.com/company/([^/\s]+)",
        "Facebook": r"facebook\.com/([^/\s]+)",
        "Twitter": r"twitter\.com/([^/\s]+)",
        "Instagram": r"instagram\.com/([^/\s]+)",
        "YouTube": r"youtube\.com/(c/|channel/|user/)?([^/\s]+)"
    }
    
    for platform, pattern in social_patterns.items():
        match = re.search(pattern, html_content)
        if match:
            company["social_media"][platform] = match.group(1) if len(match.groups()) == 1 else match.group(2)
    
    # 6. Produkte/Services aus Navigation
    nav_texts = []
    for nav in soup.find_all(['nav', 'header']):
        for link in nav.find_all('a'):
            if link.string:
                nav_texts.append(link.string.strip())
    
    service_keywords = ["products", "services", "solutions", "pricing", "features"]
    company["products_services"] = [text for text in nav_texts if any(kw in text.lower() for kw in service_keywords)][:5]
    
    # 7. Whois für Domain-Alter & Inhaber
    if WHOIS_AVAILABLE:
        try:
            w = whois.whois(domain)
            if hasattr(w, 'creation_date') and w.creation_date:
                creation = w.creation_date[0] if isinstance(w.creation_date, list) else w.creation_date
                if creation:
                    age = (datetime.now() - creation).days / 365.25
                    company["founded"] = creation.year
                    company["domain_age_years"] = round(age, 1)
                    
                    # Größenschätzung basierend auf Domain-Alter
                    if age > 15:
                        company["size_estimate"] = "Enterprise (500+ Mitarbeiter)"
                        company["revenue_estimate"] = ">€50M"
                    elif age > 10:
                        company["size_estimate"] = "Mid-Market (100-500 Mitarbeiter)"
                        company["revenue_estimate"] = "€10-50M"
                    elif age > 5:
                        company["size_estimate"] = "SMB (50-100 Mitarbeiter)"
                        company["revenue_estimate"] = "€2-10M"
                    elif age > 2:
                        company["size_estimate"] = "Startup (10-50 Mitarbeiter)"
                        company["revenue_estimate"] = "€0.5-2M"
                    else:
                        company["size_estimate"] = "Early-Stage (<10 Mitarbeiter)"
                        company["revenue_estimate"] = "<€500k"
        except:
            pass
    
    # 8. Externe Suche: Wikipedia (wenn verfügbar)
    if company["name"]:
        try:
            wiki_search = requests.get(
                f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={quote_plus(company['name'])}&format=json",
                timeout=5
            )
            if wiki_search.status_code == 200:
                wiki_data = wiki_search.json()
                if wiki_data.get("query", {}).get("search"):
                    # Wikipedia-Treffer gefunden - könnte für Extrakt genutzt werden
                    company["wikipedia_found"] = True
        except:
            pass
    
    # 9. Technologien aus HTML
    tech_indicators = {
        "WordPress": r"wp-content|wp-includes",
        "Shopify": r"cdn\.shopify\.com",
        "React": r"react|_jsx",
        "Vue.js": r"vue\.js|__vue__",
        "Angular": r"ng-app|angular",
        "jQuery": r"jquery"
    }
    
    for tech, pattern in tech_indicators.items():
        if re.search(pattern, html_content, re.IGNORECASE):
            company["technologies_used"].append(tech)
    
    return company

# ==================== MAIN ANALYSIS ====================
@st.cache_data(ttl=600)
def analyze_website_professional(url):
    """Professionelle Deep-Dive Analyse"""
    results = {
        "url": url,
        "timestamp": datetime.now().isoformat(),
        "company_intelligence": {},
        "gtm_deep_dive": {},
        "tools_detected": [],
        "overall_score": 0,
        "maturity_level": ""
    }
    
    try:
        # 1. Multi-Page Crawl
        headers = {'User-Agent': 'Mozilla/5.0'}
        urls_to_crawl = [url]
        
        # Finde wichtige Unterseiten
        resp = requests.get(url, timeout=15, headers=headers)
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        important_keywords = ['about', 'ueber', 'company', 'products', 'services', 'pricing', 'contact']
        for link in soup.find_all('a', href=True)[:50]:
            href = urljoin(url, link['href'])
            if urlparse(href).netloc == urlparse(url).netloc and any(kw in href.lower() for kw in important_keywords):
                urls_to_crawl.append(href)
        
        # Crawle bis zu 7 Seiten
        all_html = ""
        for crawl_url in urls_to_crawl[:7]:
            try:
                time.sleep(0.3)
                r = requests.get(crawl_url, timeout=10, headers=headers)
                if r.status_code == 200:
                    all_html += r.text + "\n"
            except:
                continue
        
        # 2. Company Intelligence
        domain = urlparse(url).netloc
        results["company_intelligence"] = get_company_intelligence(domain, all_html)
        
        # 3. GTM Deep-Dive
        gtm_match = re.search(r'GTM-[A-Z0-9]+', all_html)
        if gtm_match:
            gtm_id = gtm_match.group(0)
            results["gtm_deep_dive"] = deep_gtm_analysis(gtm_id, all_html)
        
        # 4. Tool-Erkennung (erweitert)
        tool_patterns = {
            "Google Analytics 4": r"G-[A-Z0-9]{10,}",
            "Google Ads": r"AW-\d+",
            "Meta Pixel": r"fbq\(",
            "LinkedIn Insight": r"linkedin_data_partner",
            "TikTok Pixel": r"ttq\(",
            "Hotjar": r"static\.hotjar\.com",
            "Clarity": r"clarity\.ms",
            "HubSpot": r"js\.hs-scripts\.com",
            "Salesforce": r"salesforce\.com",
            "Shopify": r"cdn\.shopify\.com",
            "WordPress": r"wp-content",
            "Cookiebot": r"consent\.cookiebot",
            "OneTrust": r"cdn\.cookielaw\.org"
        }
        
        for tool, pattern in tool_patterns.items():
            if re.search(pattern, all_html, re.IGNORECASE):
                results["tools_detected"].append(tool)
        
        # 5. Scoring
        base_score = len(results["tools_detected"]) * 5
        if results["gtm_deep_dive"]:
            gtm_quality = results["gtm_deep_dive"].get("implementation_quality", 0)
            base_score += gtm_quality * 0.3
        
        results["overall_score"] = min(100, round(base_score))
        results["maturity_level"] = "🏆 Advanced" if base_score >= 80 else "📈 Intermediate" if base_score >= 60 else "📊 Basic" if base_score >= 40 else "🔰 Beginner"
        
        return results
        
    except Exception as e:
        st.error(f"❌ Fehler: {e}")
        return None

# ==================== UI ====================
def main():
    init_db()
    
    st.markdown(f'<div class="main-header"><h1>🎯 MarTech Analyzer v4.0 Professional</h1><p>Deep GTM Analysis • Company Intelligence • Multi-Source Data</p></div>', unsafe_allow_html=True)
    
    with st.sidebar:
        st.header("📊 Pro Features")
        st.markdown("✅ GTM Container Deep-Dive")
        st.markdown("✅ DataLayer-Analyse")
        st.markdown("✅ Company Intelligence")
        st.markdown("✅ Multi-Page Crawling (7 Seiten)")
        st.markdown("✅ External Data Sources")
        st.markdown("✅ Implementation Quality")
        
        if "GEMINI_API_KEY" in st.secrets:
            st.success("✓ Gemini AI")
        else:
            st.warning("⚠ Gemini optional")
    
    url_input = st.text_input("🌐 Website-URL", placeholder="https://www.beispiel.de")
    
    col1, col2 = st.columns([1, 4])
    with col1:
        analyze_btn = st.button("🚀 Deep-Analyse", type="primary", use_container_width=True)
    
    if analyze_btn and url_input:
        if not url_input.startswith(('http://', 'https://')):
            st.error("❌ Vollständige URL benötigt")
        else:
            with st.spinner("🔬 Führe profunde Analyse durch... (60-90s)"):
                prog = st.progress(0)
                
                prog.progress(30)
                results = analyze_website_professional(url_input)
                
                if results:
                    prog.progress(100)
                    
                    domain = urlparse(url_input).netloc
                    save_analysis(url_input, domain, results["overall_score"], results, 
                                results.get("gtm_deep_dive", {}), results.get("company_intelligence", {}))
                    
                    st.session_state.pro_results = results
                    prog.empty()
                    st.success("✅ Profunde Analyse abgeschlossen!")
                    st.rerun()
    
    if "pro_results" in st.session_state:
        r = st.session_state.pro_results
        
        st.markdown("---")
        
        # Company Intelligence Card
        if r.get("company_intelligence"):
            c = r["company_intelligence"]
            st.markdown(f"""
                <div class="insight-card">
                    <h2 style="color: {PRIMARY_COLOR}; margin-top:0;">🏢 Company Intelligence</h2>
                    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem;">
                        <div><b>Firma:</b> {c.get('name', 'N/A')}</div>
                        <div><b>Branche:</b> {c.get('industry', 'N/A')}</div>
                        <div><b>Geschäftsmodell:</b> {c.get('business_model', 'N/A')}</div>
                        <div><b>Größe:</b> {c.get('size_estimate', 'N/A')}</div>
                        <div><b>Umsatz (geschätzt):</b> {c.get('revenue_estimate', 'N/A')}</div>
                        <div><b>Gegründet:</b> {c.get('founded', 'N/A')}</div>
                    </div>
                    <p style="margin-top: 1rem;"><b>Beschreibung:</b><br>{c.get('description', 'N/A')}</p>
                    {f"<p><b>Social Media:</b> {', '.join([f'{k}: @{v}' for k,v in c.get('social_media', {}).items()])}</p>" if c.get('social_media') else ""}
                    {f"<p><b>Technologien:</b> {', '.join(c.get('technologies_used', []))}</p>" if c.get('technologies_used') else ""}
                </div>
            """, unsafe_allow_html=True)
        
        # GTM Deep-Dive
        if r.get("gtm_deep_dive"):
            gtm = r["gtm_deep_dive"]
            st.markdown(f"""
                <div class="insight-card">
                    <h2 style="color: {PRIMARY_COLOR}; margin-top:0;">🔬 GTM Deep-Dive Analysis</h2>
                    <p><b>Container ID:</b> {gtm.get('container_id', 'N/A')}</p>
                    <p><b>Implementation Quality:</b> <span style="font-size: 1.5rem; font-weight: bold; color: {'#28a745' if gtm.get('implementation_quality', 0) >= 70 else ACCENT_COLOR};">{gtm.get('implementation_quality', 0)}/100</span></p>
                    
                    <div style="background: #e0e0e0; height: 10px; border-radius: 5px; margin: 1rem 0;">
                        <div style="background: {'#28a745' if gtm.get('implementation_quality', 0) >= 70 else ACCENT_COLOR}; height: 100%; width: {gtm.get('implementation_quality', 0)}%; border-radius: 5px;"></div>
                    </div>
                    
                    <p><b>DataLayer:</b> {'✅ Gefunden' if gtm.get('datalayer_found') else '❌ Nicht gefunden'}</p>
                    
                    {f"<p><b>DataLayer Events ({len(gtm.get('datalayer_events', []))}):</b><br>{', '.join(gtm.get('datalayer_events', [])[:10])}</p>" if gtm.get('datalayer_events') else ""}
                    
                    {f"<p><b>DataLayer Variablen ({len(gtm.get('datalayer_variables', []))}):</b><br>{', '.join([v['name'] for v in gtm.get('datalayer_variables', [])])}</p>" if gtm.get('datalayer_variables') else ""}
                    
                    {f"<p><b>Tags im Container ({len(gtm.get('tags_detected', []))}):</b><br>{', '.join(gtm.get('tags_detected', []))}</p>" if gtm.get('tags_detected') else ""}
                    
                    {f"<p><b>Trigger-Typen:</b> {', '.join(gtm.get('triggers_detected', []))}</p>" if gtm.get('triggers_detected') else ""}
                    
                    {f"<div style='background: #fff3cd; padding: 1rem; border-radius: 5px; margin-top: 1rem;'><b>⚠️ Issues:</b><ul>{''.join([f'<li>{issue}</li>' for issue in gtm.get('issues', [])])}</ul></div>" if gtm.get('issues') else ""}
                </div>
            """, unsafe_allow_html=True)
        
        # Metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f'<div class="metric-card"><div style="font-size: 3rem;">{r["overall_score"]}</div><small>Overall Score</small></div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f'<div class="metric-card"><div style="font-size: 1.5rem;">{r["maturity_level"]}</div><small>Maturity Level</small></div>', unsafe_allow_html=True)
        with col3:
            st.markdown(f'<div class="metric-card"><div style="font-size: 1.8rem;">{len(r["tools_detected"])}</div><small>Tools Detected</small></div>', unsafe_allow_html=True)
        
        # Tools
        st.markdown("### 🔧 Detected Tools & Technologies")
        if r["tools_detected"]:
            cols = st.columns(4)
            for idx, tool in enumerate(r["tools_detected"]):
                with cols[idx % 4]:
                    st.markdown(f"✅ **{tool}**")
        else:
            st.info("Keine Standard-Tools erkannt")
        
        # Export
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📋 JSON Export", use_container_width=True):
                st.download_button("Download", json.dumps(r, indent=2, ensure_ascii=False), 
                                 file_name=f"analysis_{urlparse(r['url']).netloc}.json", 
                                 mime="application/json", use_container_width=True)
        with col2:
            if st.button("🔄 Neue Analyse", use_container_width=True):
                del st.session_state.pro_results
                st.rerun()

if __name__ == "__main__":
    main()
