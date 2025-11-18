"""
MarTech Analyzer Pro v5.0 - KOMPLETT
Block 1: Core & Modern Design
Block 2: GTM Deep-Dive
Block 3: Company Intelligence with AI

Installation:
pip install streamlit requests beautifulsoup4 google-generativeai pandas python-whois

Secrets (.streamlit/secrets.toml):
GEMINI_API_KEY = "your_key_here"
"""

import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import re
from urllib.parse import urljoin, urlparse, quote_plus
from datetime import datetime
import sqlite3
import pandas as pd
import time

try:
    import whois
    WHOIS_AVAILABLE = True
except ImportError:
    WHOIS_AVAILABLE = False

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# ==================== CONFIGURATION ====================
st.set_page_config(
    page_title="MarTech Analyzer Pro v5.0",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== MODERN DESIGN ====================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap');
    * { font-family: 'Inter', sans-serif; }
    
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 3rem 2rem;
        border-radius: 20px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 20px 60px rgba(102, 126, 234, 0.4);
    }
    
    .glass-card {
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(10px);
        border-radius: 20px;
        padding: 2rem;
        border: 1px solid rgba(255, 255, 255, 0.3);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        margin-bottom: 1.5rem;
        transition: transform 0.3s ease;
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
    }
    
    .progress-bar {
        height: 100%;
        border-radius: 10px;
        transition: width 1s ease;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
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
        transition: all 0.3s;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4);
    }
    
    .section-header {
        font-size: 1.5rem;
        font-weight: 700;
        color: #1f2937;
        margin: 2rem 0 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ==================== DATABASE ====================
def init_database():
    conn = sqlite3.connect('martech_v5.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT, domain TEXT, timestamp TEXT,
        overall_score INTEGER, raw_data TEXT
    )''')
    conn.commit()
    conn.close()

def save_analysis(url, domain, score, raw_data):
    conn = sqlite3.connect('martech_v5.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('INSERT INTO analyses (url, domain, timestamp, overall_score, raw_data) VALUES (?, ?, ?, ?, ?)',
              (url, domain, datetime.now().isoformat(), score, json.dumps(raw_data)))
    conn.commit()
    conn.close()

# ==================== BLOCK 1: CRAWLING ====================
def crawl_multiple_pages(base_url, max_pages=7):
    """Intelligentes Multi-Page Crawling"""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    urls_to_visit = {base_url}
    processed_urls = set()
    all_html = ""
    pages_info = []
    
    priority_keywords = ['about', 'ueber', 'uber', 'company', 'unternehmen', 
                        'products', 'produkte', 'services', 'pricing', 'contact']
    
    try:
        resp = requests.get(base_url, timeout=15, headers=headers)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, 'html.parser')
            processed_urls.add(base_url)
            all_html += resp.text + "\n"
            
            title = soup.title.string if soup.title else "Homepage"
            pages_info.append({"url": base_url, "title": title, "status": "✓"})
            
            for link in soup.find_all('a', href=True):
                full_url = urljoin(base_url, link['href'])
                if urlparse(full_url).netloc == urlparse(base_url).netloc:
                    if any(kw in full_url.lower() for kw in priority_keywords):
                        urls_to_visit.add(full_url)
        
        for url in list(urls_to_visit)[1:max_pages]:
            if url in processed_urls:
                continue
            try:
                time.sleep(0.3)
                resp = requests.get(url, timeout=10, headers=headers)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.content, 'html.parser')
                    all_html += resp.text + "\n"
                    processed_urls.add(url)
                    title = soup.title.string if soup.title else "Page"
                    pages_info.append({"url": url, "title": title, "status": "✓"})
            except:
                continue
        
        return {
            "combined_html": all_html,
            "pages": pages_info,
            "total_pages": len(processed_urls)
        }
    except:
        return None

# ==================== BLOCK 2: GTM DEEP-DIVE ====================
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
        "tags": {"total_count": 0, "by_type": {}},
        "triggers": {"total_count": 0, "types_found": []},
        "advanced_features": {
            "server_side_tagging": False,
            "consent_mode": False,
            "cross_domain_tracking": False,
            "user_id_tracking": False
        },
        "implementation_quality": {
            "score": 0,
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
        analysis["implementation_quality"]["issues"].append("⚠️ DataLayer nicht gefunden")
    
    # DataLayer Events
    push_patterns = [
        r'dataLayer\.push\s*\(\s*({[^}]+})\s*\)',
        r'dataLayer\.push\s*\(\s*({[^}]*{[^}]*}[^}]*})\s*\)'
    ]
    
    all_pushes = []
    for pattern in push_patterns:
        pushes = re.findall(pattern, html_content, re.DOTALL)
        all_pushes.extend(pushes)
    
    for push_str in all_pushes[:50]:
        try:
            event_match = re.search(r"['\"]event['\"]:\s*['\"]([^'\"]+)['\"]", push_str)
            if event_match:
                event_name = event_match.group(1)
                if event_name and event_name not in analysis["datalayer"]["events"]:
                    analysis["datalayer"]["events"].append(event_name)
            
            var_pattern = r"['\"]?([a-zA-Z_][a-zA-Z0-9_]*)['\"]?\s*:\s*(?:['\"]([^'\"]*)['\"]|(\d+\.?\d*)|({[^}]*})|(true|false))"
            for match in re.finditer(var_pattern, push_str):
                var_name = match.group(1)
                var_value = match.group(2) or match.group(3) or match.group(5) or "object"
                
                if var_name and var_name != 'event' and var_name not in analysis["datalayer"]["variables"]:
                    analysis["datalayer"]["variables"][var_name] = {
                        "sample_value": str(var_value)[:100],
                        "type": "string" if match.group(2) else "number" if match.group(3) else "boolean" if match.group(5) else "object"
                    }
            
            ecom_indicators = ['ecommerce', 'purchase', 'add_to_cart', 'items']
            for indicator in ecom_indicators:
                if indicator in push_str:
                    analysis["datalayer"]["ecommerce"]["found"] = True
                    if 'items' in push_str:
                        analysis["datalayer"]["ecommerce"]["type"] = "GA4"
                    if indicator not in analysis["datalayer"]["ecommerce"]["events_found"]:
                        analysis["datalayer"]["ecommerce"]["events_found"].append(indicator)
                    break
        except:
            continue
    
    # Container Details
    for container_id in analysis["containers"]:
        container_analysis = {"id": container_id, "accessible": False, "size_kb": 0, "tags_detected": []}
        
        try:
            gtm_url = f"https://www.googletagmanager.com/gtm.js?id={container_id}"
            resp = requests.get(gtm_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            
            if resp.status_code == 200:
                container_analysis["accessible"] = True
                gtm_content = resp.text
                container_analysis["size_kb"] = round(len(gtm_content) / 1024, 2)
                
                tag_sigs = {
                    "Google Analytics 4": [r'google-analytics\.com/g/collect', r'measurement_id.*G-'],
                    "Google Analytics Universal": [r'google-analytics\.com/analytics\.js'],
                    "Google Ads": [r'googleadservices\.com', r'AW-\d+'],
                    "Campaign Manager 360": [r'fls\.doubleclick\.net'],
                    "Meta Pixel": [r'connect\.facebook\.net'],
                    "LinkedIn Insight": [r'snap\.licdn\.com'],
                    "TikTok Pixel": [r'analytics\.tiktok\.com'],
                    "Hotjar": [r'static\.hotjar\.com'],
                    "Microsoft Clarity": [r'clarity\.ms'],
                    "HubSpot": [r'js\.hs-scripts\.com']
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
                    "Click": [r'gtm\.click'],
                    "Form Submit": [r'gtm\.formSubmit'],
                    "Scroll": [r'scroll.*depth']
                }
                
                for trigger, patterns in trigger_types.items():
                    for pattern in patterns:
                        if re.search(pattern, gtm_content, re.IGNORECASE):
                            if trigger not in analysis["triggers"]["types_found"]:
                                analysis["triggers"]["types_found"].append(trigger)
                            break
                
                analysis["triggers"]["total_count"] = len(analysis["triggers"]["types_found"])
                
                # Advanced Features
                if re.search(r'sgtm\.|server-container', gtm_content):
                    analysis["advanced_features"]["server_side_tagging"] = True
                if re.search(r'consent.*default|ad_storage', gtm_content):
                    analysis["advanced_features"]["consent_mode"] = True
                if re.search(r'linker|allowLinker', gtm_content):
                    analysis["advanced_features"]["cross_domain_tracking"] = True
                if re.search(r'user_id|userId', gtm_content):
                    analysis["advanced_features"]["user_id_tracking"] = True
        except:
            pass
        
        analysis["container_details"][container_id] = container_analysis
    
    # Quality Score
    score = 0
    if analysis["datalayer"]["found"]: score += 10
    if len(analysis["datalayer"]["events"]) > 0: score += 10
    if len(analysis["datalayer"]["variables"]) >= 3: score += 10
    if analysis["tags"]["total_count"] >= 5: score += 20
    elif analysis["tags"]["total_count"] >= 1: score += 10
    if analysis["triggers"]["total_count"] >= 3: score += 10
    if analysis["datalayer"]["ecommerce"]["found"]: score += 10
    
    advanced_count = sum(1 for v in analysis["advanced_features"].values() if v)
    score += min(20, advanced_count * 5)
    
    analysis["implementation_quality"]["score"] = score
    percentage = score
    
    if percentage >= 90: analysis["implementation_quality"]["grade"] = "A+"
    elif percentage >= 80: analysis["implementation_quality"]["grade"] = "A"
    elif percentage >= 70: analysis["implementation_quality"]["grade"] = "B"
    elif percentage >= 60: analysis["implementation_quality"]["grade"] = "C"
    elif percentage >= 50: analysis["implementation_quality"]["grade"] = "D"
    else: analysis["implementation_quality"]["grade"] = "F"
    
    # Recommendations
    if not analysis["datalayer"]["found"]:
        analysis["implementation_quality"]["recommendations"].append("🔧 DataLayer implementieren")
    if len(analysis["datalayer"]["events"]) == 0:
        analysis["implementation_quality"]["issues"].append("⚠️ Keine Events im DataLayer")
    if not analysis["advanced_features"]["consent_mode"]:
        analysis["implementation_quality"]["recommendations"].append("🔧 Consent Mode v2 (GDPR)")
    if not analysis["advanced_features"]["server_side_tagging"]:
        analysis["implementation_quality"]["recommendations"].append("💡 Server-Side Tagging (ROI: 400%)")
    
    return analysis

def display_gtm_analysis(gtm_data):
    """Zeigt GTM-Analyse"""
    
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<h2 class="section-header">🔬 GTM Deep-Dive Analysis</h2>', unsafe_allow_html=True)
    
    if gtm_data["containers"]:
        st.markdown(f"### 📦 Container ({len(gtm_data['containers'])})")
        for cid in gtm_data["containers"]:
            det = gtm_data["container_details"].get(cid, {})
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**{cid}**")
            with col2:
                if det.get("accessible"):
                    st.markdown(f'<span class="badge badge-success">✓ {det.get("size_kb")} KB</span>', unsafe_allow_html=True)
    
    st.markdown("### 🎯 Quality")
    q = gtm_data["implementation_quality"]
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f'<div class="metric-modern"><h2>{q["score"]}</h2><p>Score</p></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="metric-modern"><h2>{q["grade"]}</h2><p>Grade</p></div>', unsafe_allow_html=True)
    with col3:
        color = "#10b981" if q["score"] >= 70 else "#f59e0b" if q["score"] >= 50 else "#ef4444"
        st.markdown(f'<div class="progress-modern"><div class="progress-bar" style="width: {q["score"]}%; background: {color};"></div></div>', unsafe_allow_html=True)
    
    st.markdown("### 📊 DataLayer")
    dl = gtm_data["datalayer"]
    
    if dl["found"]:
        st.markdown(f'<span class="badge badge-success">✓ Found</span>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Events ({len(dl['events'])})**")
            for e in dl["events"][:6]:
                st.markdown(f'<div class="tool-item">🎯 {e}</div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f"**Variables ({len(dl['variables'])})**")
            for v, d in list(dl["variables"].items())[:6]:
                st.markdown(f'<div class="tool-item">📌 {v}<br><small>{d["type"]}</small></div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<span class="badge badge-danger">✗ Not Found</span>', unsafe_allow_html=True)
    
    st.markdown(f"### 🏷️ Tags ({gtm_data['tags']['total_count']})")
    for tag, data in gtm_data["tags"]["by_type"].items():
        st.markdown(f'<div class="tool-item"><strong>{tag}</strong> <span class="badge badge-info">{data["count"]}x</span></div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"### ⚡ Triggers ({gtm_data['triggers']['total_count']})")
        for t in gtm_data["triggers"]["types_found"]:
            st.markdown(f'<span class="badge badge-info">{t}</span>', unsafe_allow_html=True)
    
    with col2:
        st.markdown("### 🚀 Advanced")
        for name, enabled in gtm_data["advanced_features"].items():
            badge = "badge-success" if enabled else "badge-warning"
            icon = "✓" if enabled else "✗"
            st.markdown(f'<span class="badge {badge}">{icon} {name.replace("_", " ").title()}</span>', unsafe_allow_html=True)
    
    if q["issues"]:
        st.markdown("### ⚠️ Issues")
        for issue in q["issues"]:
            st.markdown(f'<div class="recommendation-card">{issue}</div>', unsafe_allow_html=True)
    
    if q["recommendations"]:
        st.markdown("### 💡 Recommendations")
        for rec in q["recommendations"]:
            st.markdown(f'<div class="recommendation-card info">{rec}</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

# ==================== BLOCK 3: COMPANY INTELLIGENCE ====================
@st.cache_data(ttl=3600)
def get_company_intelligence_ai(domain, html_content):
    """Company Intelligence mit AI-Enrichment"""
    
    company = {
        "name": None,
        "industry": None,
        "business_model": None,
        "description": None,
        "size_estimate": None,
        "revenue_estimate": None,
        "founded": None,
        "headquarters": None,
        "social_media": {}
    }
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Name
    if soup.title:
        company["name"] = soup.title.string.split('|')[0].split('-')[0].strip()
    
    for meta in soup.find_all('meta'):
        if meta.get('property') == 'og:site_name':
            company["name"] = meta.get('content')
            break
    
    # Description
    for meta in soup.find_all('meta'):
        if meta.get('name') == 'description':
            company["description"] = meta.get('content', '')[:300]
            break
    
    # Branche (Keyword-basiert)
    industry_keywords = {
        "E-Commerce": ["shop", "store", "buy", "cart", "product"],
        "SaaS/Software": ["software", "platform", "cloud", "api", "saas"],
        "Finance": ["bank", "financial", "investment", "insurance"],
        "Healthcare": ["health", "medical", "clinic", "patient"],
        "Education": ["education", "learning", "course", "university"],
        "Real Estate": ["property", "real estate", "apartment"],
        "Agency/Consulting": ["agency", "consulting", "services", "solutions"],
        "Manufacturing": ["manufacturing", "production", "factory"]
    }
    
    html_lower = html_content.lower()
    industry_scores = {}
    for industry, keywords in industry_keywords.items():
        score = sum(html_lower.count(kw) for kw in keywords)
        if score > 0:
            industry_scores[industry] = score
    
    if industry_scores:
        company["industry"] = max(industry_scores, key=industry_scores.get)
    
    # Business Model
    if any(kw in html_lower for kw in ["buy", "shop", "cart", "price"]):
        company["business_model"] = "B2C E-Commerce"
    elif any(kw in html_lower for kw in ["enterprise", "business", "b2b"]):
        company["business_model"] = "B2B"
    elif any(kw in html_lower for kw in ["subscription", "pricing"]):
        company["business_model"] = "SaaS/Subscription"
    
    # Social Media
    social_patterns = {
        "LinkedIn": r"linkedin\.com/company/([^/\s\"']+)",
        "Facebook": r"facebook\.com/([^/\s\"']+)",
        "Twitter": r"twitter\.com/([^/\s\"']+)",
        "Instagram": r"instagram\.com/([^/\s\"']+)"
    }
    
    for platform, pattern in social_patterns.items():
        match = re.search(pattern, html_content)
        if match:
            company["social_media"][platform] = match.group(1)
    
    # Whois
    if WHOIS_AVAILABLE:
        try:
            w = whois.whois(domain)
            if hasattr(w, 'creation_date') and w.creation_date:
                creation = w.creation_date[0] if isinstance(w.creation_date, list) else w.creation_date
                if creation:
                    age = (datetime.now() - creation).days / 365.25
                    company["founded"] = creation.year
                    
                    if age > 15:
                        company["size_estimate"] = "Enterprise (500+ MA)"
                        company["revenue_estimate"] = ">€50M"
                    elif age > 10:
                        company["size_estimate"] = "Mid-Market (100-500 MA)"
                        company["revenue_estimate"] = "€10-50M"
                    elif age > 5:
                        company["size_estimate"] = "SMB (50-100 MA)"
                        company["revenue_estimate"] = "€2-10M"
                    elif age > 2:
                        company["size_estimate"] = "Startup (10-50 MA)"
                        company["revenue_estimate"] = "€0.5-2M"
                    else:
                        company["size_estimate"] = "Early-Stage (<10 MA)"
                        company["revenue_estimate"] = "<€500k"
        except:
            pass
    
    # AI-Enrichment via Gemini
    if GENAI_AVAILABLE and "GEMINI_API_KEY" in st.secrets:
        try:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            
            prompt = f"""Analysiere diese Firma basierend auf den Daten:

Domain: {domain}
Name: {company.get('name', 'Unbekannt')}
Beschreibung: {company.get('description', 'N/A')}
Erkannte Branche: {company.get('industry', 'N/A')}

Gib eine präzise Einschätzung als JSON:
{{
  "industry_refined": "Genaue Branche",
  "target_audience": "Zielgruppe (B2B/B2C)",
  "headquarters_guess": "Wahrscheinlicher Standort",
  "key_products": ["Produkt1", "Produkt2"]
}}

Nur JSON zurückgeben, keine Erklärung."""
            
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            
            try:
                ai_data = json.loads(response.text.strip().replace('```json', '').replace('```', ''))
                if ai_data.get("industry_refined"):
                    company["industry"] = ai_data["industry_refined"]
                if ai_data.get("headquarters_guess"):
                    company["headquarters"] = ai_data["headquarters_guess"]
                company["ai_enriched"] = True
            except:
                company["ai_enriched"] = False
        except:
            pass
    
    return company

def display_company_intelligence(company_data):
    """Zeigt Company Intelligence"""
    
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<h2 class="section-header">🏢 Company Intelligence</h2>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"**Firma:** {company_data.get('name', 'N/A')}")
        st.markdown(f"**Branche:** {company_data.get('industry', 'N/A')}")
        st.markdown(f"**Geschäftsmodell:** {company_data.get('business_model', 'N/A')}")
        st.markdown(f"**Größe:** {company_data.get('size_estimate', 'N/A')}")
    
    with col2:
        st.markdown(f"**Umsatz (geschätzt):** {company_data.get('revenue_estimate', 'N/A')}")
        st.markdown(f"**Gegründet:** {company_data.get('founded', 'N/A')}")
        st.markdown(f"**Standort:** {company_data.get('headquarters', 'N/A')}")
        if company_data.get("ai_enriched"):
            st.markdown(f'<span class="badge badge-purple">✨ AI-Enhanced</span>', unsafe_allow_html=True)
    
    if company_data.get("description"):
        st.markdown(f"**Beschreibung:**")
        st.info(company_data["description"])
    
    if company_data.get("social_media"):
        st.markdown("**Social Media:**")
        for platform, handle in company_data["social_media"].items():
            st.markdown(f'<span class="badge badge-info">{platform}: @{handle}</span>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

# ==================== MAIN UI ====================
def main():
    init_database()
    
    st.markdown("""
        <div class="main-header">
            <h1 style="margin:0; font-size: 2.8rem; font-weight: 800;">🎯 MarTech Analyzer Pro v5.0</h1>
            <p style="margin:0.5rem 0 0 0; font-size: 1.1rem; opacity: 0.95;">
                GTM Deep-Dive • Company Intelligence • Konkrete Empfehlungen
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    with st.sidebar:
        st.markdown("### 🚀 Module")
        st.markdown("""
        ✅ **Block 1:** Multi-Page Crawl  
        ✅ **Block 2:** GTM Deep-Dive  
        ✅ **Block 3:** Company Intelligence  
        ⏳ **Block 4:** Tool Detection  
        ⏳ **Block 5:** Recommendations
        """)
        
        st.markdown("---")
        st.markdown("### ⚙️ Status")
        
        if WHOIS_AVAILABLE:
            st.success("✓ Whois")
        else:
            st.error("✗ Whois")
        
        if GENAI_AVAILABLE and "GEMINI_API_KEY" in st.secrets:
            st.success("✓ Gemini AI")
        else:
            st.warning("⚠ Gemini")
    
    # Input
    col1, col2 = st.columns([3, 1])
    
    with col1:
        url_input = st.text_input(
            "🌐 Website-URL",
            placeholder="https://www.beispiel.de",
            help="Vollständige URL mit https://"
        )
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        analyze_btn = st.button("🚀 Analyse", type="primary", use_container_width=True)
    
    # Analyse
    if analyze_btn and url_input:
        if not url_input.startswith(('http://', 'https://')):
            st.error("❌ Vollständige URL benötigt")
        else:
            with st.spinner("🔬 Analysiere..."):
                prog = st.progress(0)
                
                # Crawling
                prog.progress(20)
                crawl_data = crawl_multiple_pages(url_input, 7)
                
                if crawl_data:
                    prog.progress(40)
                    
                    # GTM Analyse
                    gtm_data = ultra_precise_gtm_analysis(crawl_data['combined_html'])
                    prog.progress(60)
                    
                    # Company Intelligence
                    domain = urlparse(url_input).netloc
                    company_data = get_company_intelligence_ai(domain, crawl_data['combined_html'])
                    prog.progress(80)
                    
                    # Speichern
                    overall_score = gtm_data["implementation_quality"]["score"]
                    save_analysis(url_input, domain, overall_score, {
                        "crawl": crawl_data,
                        "gtm": gtm_data,
                        "company": company_data
                    })
                    
                    prog.progress(100)
                    
                    st.session_state.crawl_data = crawl_data
                    st.session_state.gtm_analysis = gtm_data
                    st.session_state.company_intel = company_data
                    st.session_state.url = url_input
                    
                    prog.empty()
                    st.success("✅ Analyse abgeschlossen!")
                    st.rerun()
    
    # Ergebnisse
    if "crawl_data" in st.session_state:
        crawl = st.session_state.crawl_data
        
        st.markdown("---")
        
        # Crawl Info
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown(f'<h3 class="section-header">📄 Multi-Page Crawl</h3>', unsafe_allow_html=True)
        st.markdown(f"**{crawl['total_pages']} Seiten** analysiert")
        
        with st.expander("Seiten anzeigen"):
            for page in crawl['pages']:
                st.markdown(f"""
                    <div class="tool-item">
                        <strong>{page['status']}</strong> {page['title']}<br>
                        <small style="opacity: 0.7;">{page['url']}</small>
                    </div>
                """, unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Company Intelligence
        if "company_intel" in st.session_state:
            display_company_intelligence(st.session_state.company_intel)
        
        # GTM Analysis
        if "gtm_analysis" in st.session_state:
            display_gtm_analysis(st.session_state.gtm_analysis)
        
        # Status
        st.markdown("---")
        st.info("""
            ✅ **Block 1:** Multi-Page Crawling  
            ✅ **Block 2:** GTM Deep-Dive  
            ✅ **Block 3:** Company Intelligence  
            
            **Nächste Schritte:** Block 4 (Complete Tool Detection) & Block 5 (Recommendations) folgen!
        """)
        
        # Export & Reset
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📥 JSON Export"):
                data = {
                    "crawl": st.session_state.crawl_data,
                    "gtm": st.session_state.gtm_analysis,
                    "company": st.session_state.company_intel
                }
                st.download_button(
                    "Download",
                    json.dumps(data, indent=2, ensure_ascii=False),
                    file_name=f"analysis_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                    mime="application/json"
                )
        
        with col2:
            if st.button("🔄 Neue Analyse"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

if __name__ == "__main__":
    main()
