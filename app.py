import streamlit as st
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import json
import re
from urllib.parse import urljoin, urlparse
from datetime import datetime
import sqlite3
import pandas as pd
import time
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors

try:
    import whois
    WHOIS_AVAILABLE = True
except ImportError:
    WHOIS_AVAILABLE = False

# ==================== CONFIG ====================
st.set_page_config(page_title="MarTech Analyzer Pro", page_icon="🎯", layout="wide")
PRIMARY_COLOR = "#174f78"
SECONDARY_COLOR = "#a1acbd"
ACCENT_COLOR = "#ffab40"

st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap');
html, body, [class*="css"] {{ font-family: 'Montserrat', sans-serif; font-size: 14px; }}
.main-header {{ background: linear-gradient(135deg, {PRIMARY_COLOR} 0%, #1a5f8a 100%); padding: 2rem; border-radius: 10px; color: white; margin-bottom: 2rem; }}
.score-card {{ background: white; border-left: 5px solid {PRIMARY_COLOR}; padding: 1.5rem; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 1rem; }}
.metric-card {{ background: linear-gradient(135deg, {PRIMARY_COLOR} 0%, #2a6f98 100%); color: white; padding: 1.5rem; border-radius: 8px; text-align: center; }}
.success-card {{ background: #d4edda; border-left: 5px solid #28a745; padding: 1rem; border-radius: 8px; margin: 1rem 0; }}
.stButton>button {{ background-color: {PRIMARY_COLOR}; color: white; border-radius: 8px; padding: 0.75rem 2rem; font-weight: 600; }}
</style>""", unsafe_allow_html=True)

# ==================== DATABASE ====================
def init_db():
    conn = sqlite3.connect('martech.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS analyses (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT, domain TEXT, 
                 timestamp TEXT, overall_score INTEGER, maturity_level TEXT, category_scores TEXT, detected_tools TEXT, 
                 recommendations TEXT, raw_data TEXT, performance_score INTEGER, security_grade TEXT, company_size TEXT, domain_age REAL)''')
    conn.commit()
    conn.close()

def save_analysis(url, domain, score, maturity, cat_scores, tools, recs, raw, perf=None, sec=None, size=None, age=None):
    conn = sqlite3.connect('martech.db')
    c = conn.cursor()
    c.execute('''INSERT INTO analyses (url, domain, timestamp, overall_score, maturity_level, category_scores, 
                 detected_tools, recommendations, raw_data, performance_score, security_grade, company_size, domain_age)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (url, domain, datetime.now().isoformat(), score, maturity, json.dumps(cat_scores), 
               json.dumps(tools), json.dumps(recs), json.dumps(raw), perf, sec, size, age))
    conn.commit()
    conn.close()

def get_history(limit=10):
    conn = sqlite3.connect('martech.db')
    c = conn.cursor()
    c.execute('SELECT id, url, domain, timestamp, overall_score, maturity_level, performance_score, security_grade FROM analyses ORDER BY timestamp DESC LIMIT ?', (limit,))
    results = c.fetchall()
    conn.close()
    return results

def get_by_id(aid):
    conn = sqlite3.connect('martech.db')
    c = conn.cursor()
    c.execute('SELECT * FROM analyses WHERE id = ?', (aid,))
    result = c.fetchone()
    conn.close()
    return result

# ==================== TECH SIGNATURES ====================
TECH_SIGS = {
    "analytics": {"weight": 0.20, "name": "Analytics & Data", "tools": {
        "Google Analytics 4": {"score": 10, "patterns": [r"G-[A-Z0-9]{10,}", r"gtag.*config.*G-"], "critical": True, "gmp": False},
        "Google Analytics Universal": {"score": 6, "patterns": [r"UA-\d+-\d+"], "critical": True, "gmp": False},
        "Adobe Analytics": {"score": 9, "patterns": [r"s_code\.js", r"AppMeasurement"], "critical": True, "gmp": False},
        "Matomo": {"score": 8, "patterns": [r"matomo\.js", r"_paq\.push"], "critical": False, "gmp": False}}},
    "advertising": {"weight": 0.25, "name": "Advertising & Performance", "tools": {
        "Google Ads": {"score": 9, "patterns": [r"AW-\d+"], "critical": True, "gmp": False},
        "Campaign Manager 360": {"score": 10, "patterns": [r"fls\.doubleclick\.net"], "critical": True, "gmp": True},
        "Meta Pixel": {"score": 9, "patterns": [r"fbq\(", r"facebook\.com/tr"], "critical": True, "gmp": False},
        "LinkedIn Insight": {"score": 8, "patterns": [r"linkedin_data_partner_id"], "critical": True, "gmp": False}}},
    "tagManagement": {"weight": 0.15, "name": "Tag Management", "tools": {
        "Google Tag Manager": {"score": 10, "patterns": [r"GTM-[A-Z0-9]+"], "critical": True, "gmp": False},
        "Adobe Launch": {"score": 9, "patterns": [r"assets\.adobedtm\.com"], "critical": True, "gmp": False}}},
    "cro": {"weight": 0.15, "name": "CRO & UX", "tools": {
        "Hotjar": {"score": 8, "patterns": [r"static\.hotjar\.com"], "critical": False, "gmp": False},
        "Microsoft Clarity": {"score": 7, "patterns": [r"clarity\.ms"], "critical": False, "gmp": False}}},
    "crm": {"weight": 0.15, "name": "CRM & Automation", "tools": {
        "HubSpot": {"score": 9, "patterns": [r"js\.hs-scripts\.com"], "critical": True, "gmp": False},
        "Salesforce": {"score": 10, "patterns": [r"salesforce\.com", r"pi\.pardot"], "critical": True, "gmp": False}}},
    "consent": {"weight": 0.10, "name": "Consent & Privacy", "tools": {
        "Cookiebot": {"score": 9, "patterns": [r"consent\.cookiebot"], "critical": True, "gmp": False},
        "OneTrust": {"score": 10, "patterns": [r"cdn\.cookielaw\.org"], "critical": True, "gmp": False}}}
}

# ==================== ANALYSIS FUNCTIONS ====================
@st.cache_data(ttl=3600)
def get_whois(domain):
    if not WHOIS_AVAILABLE: return None
    try:
        if domain.startswith('http'): domain = urlparse(domain).netloc
        w = whois.whois(domain)
        safe_get = lambda v: v[0] if isinstance(v, list) and v else v if v else None
        data = {
            "org": w.org if hasattr(w, 'org') and w.org else None,
            "country": w.country if hasattr(w, 'country') and w.country else None,
            "registrar": w.registrar or "Unbekannt",
            "creation_date": safe_get(w.creation_date),
            "domain_age_years": None
        }
        if data["creation_date"]:
            data["domain_age_years"] = round((datetime.now() - data["creation_date"]).days / 365.25, 1)
        age = data["domain_age_years"]
        data["estimated_company_size"] = "Enterprise (500+)" if age and age > 15 else "Mid-Market (100-500)" if age and age > 10 else "SMB (10-100)" if age and age > 5 else "Startup (10-50)" if age and age > 2 else "Early-Stage (<10)"
        return data
    except: return None

@st.cache_data(ttl=3600)
def crawl_pages(base_url, max_pages=5):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    urls_to_visit, processed, all_html, pages = {base_url}, set(), "", []
    keywords = ['about', 'ueber', 'company', 'services', 'product', 'pricing', 'contact', 'impressum']
    
    try:
        resp = requests.get(base_url, timeout=15, headers=headers)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, 'html.parser')
            processed.add(base_url)
            all_html += resp.text
            pages.append({"url": base_url, "title": soup.title.string if soup.title else "Homepage", "status": "✓"})
            for link in soup.find_all('a', href=True):
                full_url = urljoin(base_url, link['href'])
                if urlparse(full_url).netloc == urlparse(base_url).netloc and any(k in full_url.lower() for k in keywords):
                    urls_to_visit.add(full_url)
        
        for url in list(urls_to_visit)[1:max_pages]:
            if url in processed: continue
            try:
                time.sleep(0.5)
                resp = requests.get(url, timeout=10, headers=headers)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.content, 'html.parser')
                    all_html += resp.text
                    processed.add(url)
                    pages.append({"url": url, "title": soup.title.string if soup.title else "Page", "status": "✓"})
            except: continue
        
        return {"combined_html": all_html, "pages": pages, "total_pages_analyzed": len(processed)}
    except: return None

@st.cache_data(ttl=600)
def pagespeed_api(url):
    try:
        api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&strategy=mobile&category=PERFORMANCE&category=SEO"
        if "PAGESPEED_API_KEY" in st.secrets: api_url += f"&key={st.secrets['PAGESPEED_API_KEY']}"
        resp = requests.get(api_url, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "lighthouse_score": data.get("lighthouseResult", {}).get("categories", {}).get("performance", {}).get("score", 0) * 100,
                "seo_score": data.get("lighthouseResult", {}).get("categories", {}).get("seo", {}).get("score", 0) * 100
            }
    except: return None

def security_headers(url):
    try:
        resp = requests.get(url, timeout=10, allow_redirects=True)
        headers, score, issues = resp.headers, 0, []
        critical = {'Strict-Transport-Security': 15, 'Content-Security-Policy': 15, 'X-Frame-Options': 15, 'X-Content-Type-Options': 15}
        for h, p in critical.items():
            if h in headers: score += p
            else: issues.append(f"❌ {h} fehlt")
        grade = "A+" if score >= 60 else "A" if score >= 50 else "B" if score >= 40 else "C" if score >= 30 else "D" if score >= 20 else "F"
        return {"score": score, "grade": grade, "issues": issues}
    except: return None

@st.cache_data(ttl=600)
def analyze_website(url):
    results = {"url": url, "timestamp": datetime.now().isoformat(), "detected_tools": {}, "category_scores": {}, 
               "gtm_container": None, "performance_data": None, "security_data": None, "whois_data": None, "multi_page_data": None}
    
    try:
        domain = urlparse(url).netloc
        results["whois_data"] = get_whois(domain)
        
        crawl_data = crawl_pages(url, 5)
        if crawl_data:
            results["multi_page_data"] = crawl_data
            html_content = crawl_data["combined_html"]
        else:
            resp = requests.get(url, timeout=15)
            html_content = resp.text
            results["multi_page_data"] = {"pages": [{"url": url, "title": "Homepage", "status": "✓"}], "total_pages_analyzed": 1}
        
        for cat, cat_data in TECH_SIGS.items():
            results["category_scores"][cat] = {"score": 0, "max_score": sum(t["score"] for t in cat_data["tools"].values()), "detected": [], "weight": cat_data["weight"]}
            for tool_name, tool_info in cat_data["tools"].items():
                for pattern in tool_info["patterns"]:
                    if re.search(pattern, html_content, re.IGNORECASE):
                        results["category_scores"][cat]["detected"].append(tool_name)
                        results["category_scores"][cat]["score"] += tool_info["score"]
                        if tool_name not in results["detected_tools"]:
                            results["detected_tools"][tool_name] = {"category": cat, "score": tool_info["score"], 
                                                                    "critical": tool_info["critical"], "gmp": tool_info["gmp"], "source": "regex"}
                        break
        
        if "Campaign Manager 360" in results["detected_tools"]:
            if "Display & Video 360" not in results["detected_tools"]:
                results["detected_tools"]["Display & Video 360 (inferred)"] = {"category": "advertising", "score": 10, "critical": True, "gmp": True, "source": "inference", "confidence": "sehr wahrscheinlich"}
        
        gtm_match = re.search(r'GTM-[A-Z0-9]+', html_content)
        if gtm_match: results["gtm_container"] = gtm_match.group(0)
        
        results["performance_data"] = pagespeed_api(url)
        results["security_data"] = security_headers(url)
        
        total_score = sum((data["score"] / data["max_score"]) * 100 * data["weight"] if data["max_score"] > 0 else 0 
                         for data in results["category_scores"].values())
        results["overall_score"] = round(total_score)
        results["maturity_level"] = "🏆 Advanced" if total_score >= 80 else "📈 Intermediate" if total_score >= 60 else "📊 Basic" if total_score >= 40 else "🔰 Beginner"
        
        return results
    except Exception as e:
        st.error(f"❌ Fehler: {e}")
        return None

def gen_recommendations(results):
    recs = []
    if results.get("security_data") and results["security_data"]["score"] < 40:
        recs.append({"priority": "🔴 Kritisch", "category": "Security", "title": f"Sicherheitslücken (Grade: {results['security_data']['grade']})", 
                    "action": "Security Headers implementieren", "impact": "Schutz vor Angriffen", "effort": "Low", "timeframe": "1-2 Tage", "roi": "Risk Mitigation"})
    
    if results.get("performance_data") and results["performance_data"].get("lighthouse_score", 100) < 50:
        recs.append({"priority": "🟠 Hoch", "category": "Performance", "title": "Performance-Probleme", "action": "Core Web Vitals optimieren", 
                    "impact": "Höhere Conversion Rate", "effort": "Medium", "timeframe": "2-4 Wochen", "roi": "250%"})
    
    for cat, data in results["category_scores"].items():
        perc = (data["score"] / data["max_score"]) * 100 if data["max_score"] > 0 else 0
        if perc < 30 and cat == "analytics":
            recs.append({"priority": "🔴 Kritisch", "category": "Analytics", "title": "Keine Datengrundlage", "action": "Google Analytics 4 implementieren", 
                        "impact": "Datenbasierte Optimierung", "effort": "Medium", "timeframe": "1-2 Wochen", "roi": "500%"})
    
    has_gmp = any(t.get("gmp", False) for t in results["detected_tools"].values())
    if not has_gmp and results["overall_score"] >= 60:
        recs.append({"priority": "💎 Strategisch", "category": "Enterprise", "title": "Bereit für GMP", "action": "GMP-Stack evaluieren", 
                    "impact": "Enterprise Attribution", "effort": "High", "timeframe": "3-6 Monate", "roi": "Variable"})
    
    return sorted(recs, key=lambda x: 0 if "Kritisch" in x["priority"] else 1)[:5]

def calc_roi(results):
    improvement = 100 - results["overall_score"]
    potential = improvement * 1000
    investment = len(gen_recommendations(results)) * 5000
    roi = round((potential / investment) * 100) if investment > 0 else 0
    return {"potential_revenue": round(potential), "estimated_investment": investment, "roi_percentage": roi}

def gen_ai_insights(results):
    try:
        api_key = st.secrets.get("GEMINI_API_KEY")
        if not api_key: return None
        genai.configure(api_key=api_key)
        
        context = f"""Domain: {urlparse(results['url']).netloc}
Score: {results['overall_score']}/100 ({results['maturity_level']})
Tools: {len(results['detected_tools'])}
Unternehmensgröße: {results.get('whois_data', {}).get('estimated_company_size', 'N/A') if results.get('whois_data') else 'N/A'}

Erstelle eine kompakte Bewertung (max 120 Wörter):
1. Executive Summary (2 Sätze)
2. Größte Stärke (1 Satz)
3. Kritischste Schwäche (1 Satz)
4. Quick Win (1 Tipp)
Nutze Emojis."""
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        return model.generate_content(context).text
    except: return None

def gen_pdf(results, recs, roi):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = [Paragraph("MarTech Stack Analyse", styles['Title']), Spacer(1, 12)]
    
    data = [["Metric", "Wert"], ["Score", f"{results['overall_score']}/100"], ["Reifegrad", results['maturity_level']]]
    if results.get("whois_data"): data.append(["Unternehmen", results["whois_data"].get("estimated_company_size", "N/A")])
    
    t = Table(data)
    t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor(PRIMARY_COLOR)), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('GRID', (0,0), (-1,-1), 1, colors.grey)]))
    story.append(t)
    story.append(Spacer(1, 20))
    
    for i, rec in enumerate(recs, 1):
        story.append(Paragraph(f"<b>{i}. {rec['title']}</b> ({rec['priority']})", styles['Normal']))
        story.append(Paragraph(f"Action: {rec['action']} | ROI: {rec['roi']}", styles['Normal']))
        story.append(Spacer(1, 10))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

# ==================== UI ====================
def main():
    init_db()
    
    st.markdown(f'<div class="main-header"><h1>🎯 MarTech Stack Analyzer Pro</h1><p>KI-Insights, Multi-Page-Crawling & Whois-Intelligence</p></div>', unsafe_allow_html=True)
    
    with st.sidebar:
        st.header("📊 Navigation")
        page = st.radio("", ["🔍 Neue Analyse", "📜 Historie", "📊 Benchmark"])
        st.markdown("---")
        st.markdown("### 🎨 Features")
        st.markdown("✅ Gemini AI\n✅ PageSpeed\n✅ Multi-Crawler\n✅ Whois\n✅ Security")
        st.markdown("---")
        if "GEMINI_API_KEY" in st.secrets: st.success("✓ Gemini")
        else: st.error("✗ Gemini (erforderlich)")
        if WHOIS_AVAILABLE: st.success("✓ Whois")
        else: st.warning("⚠ Whois (pip install python-whois)")
    
    if page == "🔍 Neue Analyse":
        col1, col2 = st.columns([3, 1])
        with col1: url_input = st.text_input("🌐 URL", placeholder="https://beispiel.de")
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            analyze_btn = st.button("🚀 Starten", type="primary", use_container_width=True)
        
        if analyze_btn and url_input:
            if not url_input.startswith(('http://', 'https://')): 
                st.error("❌ Vollständige URL benötigt")
            else:
                with st.spinner("🔍 Analysiere... (40-60s)"):
                    prog = st.progress(0)
                    prog.progress(20)
                    results = analyze_website(url_input)
                    if results:
                        prog.progress(60)
                        recs = gen_recommendations(results)
                        roi = calc_roi(results)
                        prog.progress(80)
                        ai = gen_ai_insights(results)
                        prog.progress(100)
                        
                        domain = urlparse(url_input).netloc
                        save_analysis(url_input, domain, results["overall_score"], results["maturity_level"], 
                                    results["category_scores"], results["detected_tools"], recs, results,
                                    results.get("performance_data", {}).get("lighthouse_score") if results.get("performance_data") else None,
                                    results.get("security_data", {}).get("grade") if results.get("security_data") else None,
                                    results.get("whois_data", {}).get("estimated_company_size") if results.get("whois_data") else None,
                                    results.get("whois_data", {}).get("domain_age_years") if results.get("whois_data") else None)
                        
                        st.session_state.current = {"results": results, "recs": recs, "roi": roi, "ai": ai}
                        prog.empty()
                        st.success("✅ Fertig!")
                        st.rerun()
        
        if "current" in st.session_state:
            r, recs, roi, ai = st.session_state.current["results"], st.session_state.current["recs"], st.session_state.current["roi"], st.session_state.current.get("ai")
            
            st.markdown("---")
            
            if ai:
                st.markdown(f'<div style="background: linear-gradient(135deg, {ACCENT_COLOR}, #ff8c00); color: white; padding: 1.5rem; border-radius: 10px; margin-bottom: 2rem;"><h3>🤖 KI-Insights</h3><p>{ai.replace(chr(10), "<br>")}</p></div>', unsafe_allow_html=True)
            
            if r.get("whois_data"):
                w = r["whois_data"]
                st.markdown(f'<div style="background: linear-gradient(135deg, {PRIMARY_COLOR}, #2a6f98); color: white; padding: 1.5rem; border-radius: 10px; margin-bottom: 2rem;"><h3>🏢 Unternehmens-Intel</h3><div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem;"><div><small>Größe</small><br><b>{w.get("estimated_company_size", "N/A")}</b></div><div><small>Alter</small><br><b>{w.get("domain_age_years", "N/A")} Jahre</b></div><div><small>Land</small><br><b>{w.get("country", "N/A")}</b></div><div><small>Inhaber</small><br><b>{w.get("org", "N/A")}</b></div></div></div>', unsafe_allow_html=True)
            
            if r.get("multi_page_data"):
                with st.expander(f"📄 {r['multi_page_data']['total_pages_analyzed']} Seiten analysiert"):
                    for p in r["multi_page_data"]["pages"]: st.caption(f"{p['status']} {p['title']}")
            
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1: st.markdown(f'<div class="metric-card"><div style="font-size: 3rem;">{r["overall_score"]}</div><small>Maturity</small></div>', unsafe_allow_html=True)
            with col2: st.markdown(f'<div class="metric-card"><div style="font-size: 1.5rem;">{r["maturity_level"]}</div><small>Level</small></div>', unsafe_allow_html=True)
            with col3: st.markdown(f'<div class="metric-card"><div style="font-size: 1.8rem;">{len(r["detected_tools"])}</div><small>Tools</small></div>', unsafe_allow_html=True)
            with col4: 
                perf = r.get("performance_data", {}).get("lighthouse_score", 0) if r.get("performance_data") else 0
                st.markdown(f'<div class="metric-card"><div style="font-size: 1.8rem;">{round(perf) if perf else "N/A"}</div><small>Performance</small></div>', unsafe_allow_html=True)
            with col5:
                sec = r.get("security_data", {}).get("grade", "N/A") if r.get("security_data") else "N/A"
                st.markdown(f'<div class="metric-card"><div style="font-size: 1.8rem;">{sec}</div><small>Security</small></div>', unsafe_allow_html=True)
            
            st.markdown(f'<div class="success-card"><h3 style="color: {PRIMARY_COLOR};">💰 ROI-Potenzial</h3><div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem;"><div><h2 style="color: #28a745;">€{roi["potential_revenue"]:,}</h2><small>Umsatzpotenzial</small></div><div><h2 style="color: {PRIMARY_COLOR};">€{roi["estimated_investment"]:,}</h2><small>Investition</small></div><div><h2 style="color: {ACCENT_COLOR};">{roi["roi_percentage"]}%</h2><small>ROI</small></div></div></div>', unsafe_allow_html=True)
            
            st.markdown("### 📊 Kategorien")
            for cat, data in r["category_scores"].items():
                perc = round((data["score"] / data["max_score"]) * 100) if data["max_score"] > 0 else 0
                color = "#28a745" if perc >= 70 else ACCENT_COLOR if perc >= 40 else "#dc3545"
                st.markdown(f'<div style="margin-bottom: 1rem;"><div style="display: flex; justify-content: space-between;"><b>{TECH_SIGS[cat]["name"]}</b><span style="color: {color}; font-weight: bold;">{perc}%</span></div><div style="background: #e0e0e0; height: 8px; border-radius: 4px;"><div style="background: {color}; height: 100%; width: {perc}%;"></div></div></div>', unsafe_allow_html=True)
            
            st.markdown("### 🔧 Tools")
            with st.expander(f"{len(r['detected_tools'])} Tools erkannt"):
                for tool, info in r["detected_tools"].items():
                    badge = "🏆 GMP" if info.get("gmp") else ""
                    st.markdown(f"**{tool}** {badge} - {info['category']}")
            
            st.markdown("### 🎯 Empfehlungen")
            for i, rec in enumerate(recs, 1):
                st.markdown(f'<div style="border-left: 5px solid {ACCENT_COLOR}; padding: 1rem; background: white; border-radius: 8px; margin-bottom: 1rem;"><b>{i}. {rec["title"]}</b> ({rec["priority"]})<br><small>{rec["action"]} | {rec["timeframe"]} | ROI: {rec["roi"]}</small></div>', unsafe_allow_html=True)
            
            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            with col1:
                pdf = gen_pdf(r, recs, roi)
                st.download_button("📄 PDF-Report", pdf, file_name=f"analysis_{urlparse(r['url']).netloc}.pdf", mime="application/pdf", use_container_width=True)
            with col2:
                st.download_button("📋 JSON-Export", json.dumps(r, indent=2, ensure_ascii=False), file_name=f"data_{urlparse(r['url']).netloc}.json", mime="application/json", use_container_width=True)
            with col3:
                if st.button("🔄 Neue Analyse", use_container_width=True):
                    del st.session_state.current
                    st.rerun()
    
    elif page == "📜 Historie":
        st.header("📜 Analyse-Historie")
        history = get_history(20)
        
        if not history:
            st.info("Noch keine Analysen durchgeführt.")
        else:
            st.markdown(f"**{len(history)} Analysen** gespeichert")
            
            df = pd.DataFrame(history, columns=["ID", "URL", "Domain", "Timestamp", "Score", "Maturity", "Performance", "Security"])
            df["Timestamp"] = pd.to_datetime(df["Timestamp"]).dt.strftime("%d.%m.%Y %H:%M")
            
            for idx, row in df.iterrows():
                col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                with col1:
                    st.markdown(f"**{row['Domain']}**")
                    st.caption(row['Timestamp'])
                with col2:
                    st.caption(row['URL'])
                with col3:
                    color = "#28a745" if row['Score'] >= 70 else ACCENT_COLOR if row['Score'] >= 40 else "#dc3545"
                    st.markdown(f"<div style='text-align: center; font-size: 1.5rem; font-weight: bold; color: {color};'>{row['Score']}</div>", unsafe_allow_html=True)
                with col4:
                    if st.button("📊", key=f"v_{row['ID']}"):
                        data = get_by_id(row['ID'])
                        if data:
                            raw = json.loads(data[9])
                            st.session_state.current = {
                                "results": raw,
                                "recs": json.loads(data[7]),
                                "roi": calc_roi(raw),
                                "ai": None
                            }
                            st.rerun()
                st.markdown("---")
    
    elif page == "📊 Benchmark":
        st.header("📊 Benchmark-Vergleich")
        history = get_history(50)
        
        if len(history) < 2:
            st.info("Mindestens 2 Analysen erforderlich.")
        else:
            df = pd.DataFrame(history, columns=["ID", "URL", "Domain", "Timestamp", "Score", "Maturity", "Performance", "Security"])
            
            st.markdown("### 🏆 Top-Performer")
            top10 = df.nlargest(10, "Score")[["Domain", "Score"]]
            st.bar_chart(top10.set_index("Domain"))
            
            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            with col1: st.metric("Durchschnitt", f"{df['Score'].mean():.1f}")
            with col2: st.metric("Median", f"{df['Score'].median():.1f}")
            with col3: st.metric("Höchster Score", f"{df['Score'].max()}")
            
            st.markdown("---")
            st.markdown("### 📈 Performance-Übersicht")
            df_perf = df[df["Performance"].notna()]
            if not df_perf.empty:
                st.metric("Durchschnittliche Performance", f"{df_perf['Performance'].mean():.1f}/100")
                st.dataframe(df_perf.nlargest(5, "Performance")[["Domain", "Performance", "Score"]], use_container_width=True, hide_index=True)
            else:
                st.info("Keine Performance-Daten verfügbar")
            
            st.markdown("---")
            st.markdown("### 🔒 Security-Verteilung")
            df_sec = df[df["Security"].notna()]
            if not df_sec.empty:
                grade_counts = df_sec["Security"].value_counts()
                st.bar_chart(grade_counts)
                for grade, count in grade_counts.items():
                    perc = (count / len(df_sec)) * 100
                    st.markdown(f"**{grade}**: {count} ({perc:.1f}%)")
            else:
                st.info("Keine Security-Daten verfügbar")

if __name__ == "__main__":
    main()
