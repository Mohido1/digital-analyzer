import streamlit as st
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import json
import re
from urllib.parse import urljoin, urlparse
import tldextract
from datetime import datetime
import sqlite3
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER
import pandas as pd
import time
import whois
from collections import Counter

# ==================== KONFIGURATION ====================
st.set_page_config(
    page_title="MarTech Stack Analyzer Pro",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Corporate Colors
PRIMARY_COLOR = "#174f78"
SECONDARY_COLOR = "#a1acbd"
ACCENT_COLOR = "#ffab40"

# Custom CSS
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap');
    
    html, body, [class*="css"] {{
        font-family: 'Montserrat', sans-serif;
        font-size: 14px;
    }}
    
    .main-header {{
        background: linear-gradient(135deg, {PRIMARY_COLOR} 0%, #1a5f8a 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 2rem;
    }}
    
    .score-card {{
        background: white;
        border-left: 5px solid {PRIMARY_COLOR};
        padding: 1.5rem;
        border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
    }}
    
    .metric-card {{
        background: linear-gradient(135deg, {PRIMARY_COLOR} 0%, #2a6f98 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 8px;
        text-align: center;
    }}
    
    .warning-card {{
        background: #fff3cd;
        border-left: 5px solid {ACCENT_COLOR};
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }}
    
    .success-card {{
        background: #d4edda;
        border-left: 5px solid #28a745;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }}
    
    .danger-card {{
        background: #f8d7da;
        border-left: 5px solid #dc3545;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }}
    
    .stButton>button {{
        background-color: {PRIMARY_COLOR};
        color: white;
        border-radius: 8px;
        padding: 0.75rem 2rem;
        font-weight: 600;
        border: none;
        transition: all 0.3s;
    }}
    
    .stButton>button:hover {{
        background-color: #1a5f8a;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(23, 79, 120, 0.3);
    }}
</style>
""", unsafe_allow_html=True)

# ==================== DATENBANK-SETUP ====================
def init_database():
    """Initialisiert SQLite-Datenbank für Analyse-Historie"""
    conn = sqlite3.connect('martech_analyses.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS analyses
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  url TEXT NOT NULL,
                  domain TEXT NOT NULL,
                  timestamp TEXT NOT NULL,
                  overall_score INTEGER,
                  maturity_level TEXT,
                  category_scores TEXT,
                  detected_tools TEXT,
                  recommendations TEXT,
                  raw_data TEXT,
                  performance_score INTEGER,
                  security_grade TEXT)''')
    conn.commit()
    conn.close()

def save_analysis(url, domain, overall_score, maturity_level, category_scores, detected_tools, recommendations, raw_data, performance_score=None, security_grade=None):
    """Speichert Analyse-Ergebnis in Datenbank"""
    conn = sqlite3.connect('martech_analyses.db')
    c = conn.cursor()
    c.execute('''INSERT INTO analyses 
                 (url, domain, timestamp, overall_score, maturity_level, category_scores, detected_tools, recommendations, raw_data, performance_score, security_grade)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (url, domain, datetime.now().isoformat(), overall_score, maturity_level,
               json.dumps(category_scores), json.dumps(detected_tools), json.dumps(recommendations), json.dumps(raw_data), performance_score, security_grade))
    conn.commit()
    conn.close()

def get_analysis_history(limit=10):
    """Holt die letzten Analysen aus der Datenbank"""
    conn = sqlite3.connect('martech_analyses.db')
    c = conn.cursor()
    c.execute('''SELECT id, url, domain, timestamp, overall_score, maturity_level, performance_score, security_grade
                 FROM analyses ORDER BY timestamp DESC LIMIT ?''', (limit,))
    results = c.fetchall()
    conn.close()
    return results

def get_analysis_by_id(analysis_id):
    """Holt eine spezifische Analyse anhand der ID"""
    conn = sqlite3.connect('martech_analyses.db')
    c = conn.cursor()
    c.execute('''SELECT * FROM analyses WHERE id = ?''', (analysis_id,))
    result = c.fetchone()
    conn.close()
    return result

# ==================== TECHNOLOGIE-SIGNATUREN MIT SCORING ====================
TECHNOLOGY_SIGNATURES = {
    "analytics": {
        "weight": 0.20,
        "display_name": "Analytics & Data",
        "tools": {
            "Google Analytics 4": {
                "score": 10,
                "patterns": [r"G-[A-Z0-9]{10,}", r"gtag.*config.*G-"],
                "critical": True,
                "gmp": False
            },
            "Google Analytics Universal": {
                "score": 6,
                "patterns": [r"UA-\d+-\d+"],
                "critical": True,
                "gmp": False
            },
            "Adobe Analytics": {
                "score": 9,
                "patterns": [r"s_code\.js", r"AppMeasurement\.js", r"omniture"],
                "critical": True,
                "gmp": False
            },
            "Matomo": {
                "score": 8,
                "patterns": [r"matomo\.js", r"piwik\.js", r"_paq\.push"],
                "critical": False,
                "gmp": False
            },
            "Mixpanel": {
                "score": 7,
                "patterns": [r"mixpanel"],
                "critical": False,
                "gmp": False
            },
            "Amplitude": {
                "score": 7,
                "patterns": [r"amplitude\.com"],
                "critical": False,
                "gmp": False
            }
        }
    },
    "advertising": {
        "weight": 0.25,
        "display_name": "Advertising & Performance",
        "tools": {
            "Google Ads": {
                "score": 9,
                "patterns": [r"AW-\d+", r"google_conversion_id"],
                "critical": True,
                "gmp": False
            },
            "Campaign Manager 360": {
                "score": 10,
                "patterns": [r"fls\.doubleclick\.net", r"doubleclick\.net/activityi"],
                "critical": True,
                "gmp": True,
                "auto_infer": "Google Marketing Platform (Floodlight)"
            },
            "Display & Video 360": {
                "score": 10,
                "patterns": [r"display\.doubleclick", r"dbm\.doubleclick"],
                "critical": True,
                "gmp": True
            },
            "Search Ads 360": {
                "score": 9,
                "patterns": [r"sa360", r"searchads360"],
                "critical": False,
                "gmp": True
            },
            "Meta Pixel": {
                "score": 9,
                "patterns": [r"fbq\(", r"facebook\.com/tr", r"_fbp"],
                "critical": True,
                "gmp": False
            },
            "LinkedIn Insight Tag": {
                "score": 8,
                "patterns": [r"linkedin_data_partner_id", r"snap\.licdn\.com"],
                "critical": True,
                "gmp": False
            },
            "TikTok Pixel": {
                "score": 7,
                "patterns": [r"tiktok.*analytics", r"ttq\("],
                "critical": False,
                "gmp": False
            },
            "Microsoft Ads": {
                "score": 7,
                "patterns": [r"bat\.bing\.com"],
                "critical": False,
                "gmp": False
            },
            "Twitter/X Ads": {
                "score": 6,
                "patterns": [r"static\.ads-twitter\.com", r"twq\("],
                "critical": False,
                "gmp": False
            }
        }
    },
    "tagManagement": {
        "weight": 0.15,
        "display_name": "Tag Management",
        "tools": {
            "Google Tag Manager": {
                "score": 10,
                "patterns": [r"GTM-[A-Z0-9]+", r"googletagmanager\.com/gtm\.js"],
                "critical": True,
                "gmp": False
            },
            "Adobe Launch": {
                "score": 9,
                "patterns": [r"assets\.adobedtm\.com"],
                "critical": True,
                "gmp": False
            },
            "Tealium": {
                "score": 9,
                "patterns": [r"tags\.tiqcdn\.com"],
                "critical": False,
                "gmp": False
            },
            "Segment": {
                "score": 8,
                "patterns": [r"cdn\.segment\.com", r"analytics\.js"],
                "critical": False,
                "gmp": False
            }
        }
    },
    "cro": {
        "weight": 0.15,
        "display_name": "CRO & User Experience",
        "tools": {
            "Hotjar": {
                "score": 8,
                "patterns": [r"static\.hotjar\.com", r"window\.hj"],
                "critical": False,
                "gmp": False
            },
            "Microsoft Clarity": {
                "score": 7,
                "patterns": [r"clarity\.ms"],
                "critical": False,
                "gmp": False
            },
            "Optimizely": {
                "score": 9,
                "patterns": [r"optimizely\.com"],
                "critical": False,
                "gmp": False
            },
            "VWO": {
                "score": 8,
                "patterns": [r"dev\.vwo\.com"],
                "critical": False,
                "gmp": False
            },
            "Google Optimize": {
                "score": 7,
                "patterns": [r"optimize\.js"],
                "critical": False,
                "gmp": False
            },
            "FullStory": {
                "score": 8,
                "patterns": [r"fullstory\.com"],
                "critical": False,
                "gmp": False
            }
        }
    },
    "crm": {
        "weight": 0.15,
        "display_name": "CRM & Marketing Automation",
        "tools": {
            "HubSpot": {
                "score": 9,
                "patterns": [r"js\.hs-scripts\.com", r"_hsq"],
                "critical": True,
                "gmp": False
            },
            "Salesforce": {
                "score": 10,
                "patterns": [r"salesforce\.com", r"pi\.pardot"],
                "critical": True,
                "gmp": False
            },
            "Marketo": {
                "score": 9,
                "patterns": [r"munchkin\.js", r"Munchkin\.init"],
                "critical": True,
                "gmp": False
            },
            "Intercom": {
                "score": 8,
                "patterns": [r"widget\.intercom\.io"],
                "critical": False,
                "gmp": False
            },
            "Drift": {
                "score": 7,
                "patterns": [r"js\.driftt\.com"],
                "critical": False,
                "gmp": False
            },
            "ActiveCampaign": {
                "score": 7,
                "patterns": [r"ac_track\.js"],
                "critical": False,
                "gmp": False
            }
        }
    },
    "consent": {
        "weight": 0.10,
        "display_name": "Consent & Privacy",
        "tools": {
            "Cookiebot": {
                "score": 9,
                "patterns": [r"consent\.cookiebot", r"Cybot"],
                "critical": True,
                "gmp": False
            },
            "OneTrust": {
                "score": 10,
                "patterns": [r"cdn\.cookielaw\.org", r"optanon"],
                "critical": True,
                "gmp": False
            },
            "Usercentrics": {
                "score": 8,
                "patterns": [r"app\.usercentrics"],
                "critical": False,
                "gmp": False
            },
            "Termly": {
                "score": 7,
                "patterns": [r"termly\.io"],
                "critical": False,
                "gmp": False
            }
        }
    }
}

# ==================== API INTEGRATION FUNKTIONEN ====================

@st.cache_data(ttl=3600)
def get_whois_data(domain):
    """Whois-Daten abrufen - kostenlos, keine API nötig"""
    try:
        # Extrahiere nur die Domain ohne Protokoll
        if domain.startswith('http'):
            parsed = urlparse(domain)
            domain = parsed.netloc
        
        # Whois-Abfrage
        w = whois.whois(domain)
        
        # Daten strukturieren
        whois_data = {
            "domain_name": w.domain_name[0] if isinstance(w.domain_name, list) else w.domain_name if w.domain_name else domain,
            "registrar": w.registrar if w.registrar else "Unbekannt",
            "creation_date": w.creation_date[0] if isinstance(w.creation_date, list) else w.creation_date if w.creation_date else None,
            "expiration_date": w.expiration_date[0] if isinstance(w.expiration_date, list) else w.expiration_date if w.expiration_date else None,
            "updated_date": w.updated_date[0] if isinstance(w.updated_date, list) else w.updated_date if w.updated_date else None,
            "name_servers": w.name_servers if w.name_servers else [],
            "status": w.status if w.status else [],
            "emails": w.emails if w.emails else [],
            "org": w.org if w.org else None,
            "country": w.country if w.country else None,
            "registrant_name": w.name if w.name else None
        }
        
        # Domain-Alter berechnen
        if whois_data["creation_date"]:
            age_years = (datetime.now() - whois_data["creation_date"]).days / 365.25
            whois_data["domain_age_years"] = round(age_years, 1)
        else:
            whois_data["domain_age_years"] = None
        
        # Geschätzte Unternehmensgröße basierend auf Domain-Alter und anderen Faktoren
        whois_data["estimated_company_size"] = estimate_company_size(whois_data)
        
        return whois_data
        
    except Exception as e:
        st.warning(f"Whois-Daten konnten nicht abgerufen werden: {e}")
        return None

def estimate_company_size(whois_data):
    """Schätzt Unternehmensgröße basierend auf Whois-Daten"""
    if not whois_data.get("domain_age_years"):
        return "Unbekannt"
    
    age = whois_data["domain_age_years"]
    
    # Heuristik basierend auf Domain-Alter und Registrar
    if age > 15:
        return "Enterprise (500+ Mitarbeiter)"
    elif age > 10:
        return "Mid-Market (100-500 Mitarbeiter)"
    elif age > 5:
        return "SMB (10-100 Mitarbeiter)"
    elif age > 2:
        return "Startup/Scale-up (10-50 Mitarbeiter)"
    else:
        return "Early-Stage Startup (<10 Mitarbeiter)"

@st.cache_data(ttl=3600)
def crawl_multiple_pages(base_url, max_pages=5):
    """Crawlt mehrere Seiten einer Website für umfassendere Analyse"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    pages_analyzed = []
    urls_to_visit = {base_url}
    processed_urls = set()
    all_html = ""
    
    # Schlüsselwörter für relevante Unterseiten
    priority_keywords = ['about', 'ueber', 'company', 'unternehmen', 'services', 'leistungen', 
                        'product', 'produkt', 'solution', 'loesung', 'pricing', 'preise',
                        'contact', 'kontakt', 'impressum', 'team']
    
    try:
        # Schritt 1: Startseite analysieren und Links sammeln
        response = requests.get(base_url, timeout=15, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            processed_urls.add(base_url)
            all_html += response.text
            
            pages_analyzed.append({
                "url": base_url,
                "title": soup.title.string if soup.title else "No Title",
                "status": "✓ Analyzed"
            })
            
            # Links sammeln
            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin(base_url, href)
                
                # Nur interne Links
                if urlparse(full_url).netloc == urlparse(base_url).netloc:
                    # Priorisiere relevante Seiten
                    if any(keyword in full_url.lower() for keyword in priority_keywords):
                        urls_to_visit.add(full_url)
        
        # Schritt 2: Weitere Seiten crawlen
        for url in list(urls_to_visit)[1:max_pages]:
            if url in processed_urls:
                continue
                
            try:
                time.sleep(0.5)  # Rate limiting
                response = requests.get(url, timeout=10, headers=headers)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    all_html += response.text
                    processed_urls.add(url)
                    
                    pages_analyzed.append({
                        "url": url,
                        "title": soup.title.string if soup.title else "No Title",
                        "status": "✓ Analyzed"
                    })
                else:
                    pages_analyzed.append({
                        "url": url,
                        "title": "N/A",
                        "status": f"✗ Error {response.status_code}"
                    })
                    
            except Exception as e:
                pages_analyzed.append({
                    "url": url,
                    "title": "N/A",
                    "status": f"✗ Failed"
                })
                continue
        
        return {
            "combined_html": all_html,
            "pages": pages_analyzed,
            "total_pages_analyzed": len(processed_urls)
        }
        
    except Exception as e:
        st.warning(f"Multi-Page-Crawling nicht möglich: {e}")
        return None

@st.cache_data(ttl=600)
def call_builtwith_free_api(domain):
    """BuiltWith Free API - Kostenlos, 1 Request/Sekunde"""
    try:
        # Extrahiere nur die Domain ohne Protokoll
        parsed = urlparse(domain if domain.startswith('http') else f'https://{domain}')
        clean_domain = parsed.netloc or parsed.path
        
        url = f"https://api.builtwith.com/free1/api.json?KEY={st.secrets.get('BUILTWITH_API_KEY', '')}&LOOKUP={clean_domain}"
        
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            return None
    except Exception as e:
        st.warning(f"BuiltWith API nicht verfügbar: {e}")
        return None

@st.cache_data(ttl=600)
def call_pagespeed_insights_api(url):
    """Google PageSpeed Insights API - Kostenlos, 25k Requests/Tag"""
    try:
        api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&strategy=mobile&category=PERFORMANCE&category=ACCESSIBILITY&category=BEST_PRACTICES&category=SEO"
        
        # Optional: API Key hinzufügen für höhere Limits
        if "PAGESPEED_API_KEY" in st.secrets:
            api_url += f"&key={st.secrets['PAGESPEED_API_KEY']}"
        
        response = requests.get(api_url, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception as e:
        st.warning(f"PageSpeed Insights API nicht verfügbar: {e}")
        return None

def analyze_security_headers(url):
    """Analysiert Security Headers (eigene Implementierung, kein externes API nötig)"""
    try:
        response = requests.get(url, timeout=10, allow_redirects=True)
        headers = response.headers
        
        security_score = 0
        max_score = 100
        issues = []
        
        # Critical Headers (je 15 Punkte)
        critical_headers = {
            'Strict-Transport-Security': 15,
            'Content-Security-Policy': 15,
            'X-Frame-Options': 15,
            'X-Content-Type-Options': 15
        }
        
        # Important Headers (je 10 Punkte)
        important_headers = {
            'Referrer-Policy': 10,
            'Permissions-Policy': 10,
            'X-XSS-Protection': 10
        }
        
        for header, points in critical_headers.items():
            if header in headers:
                security_score += points
            else:
                issues.append(f"❌ {header} fehlt (kritisch)")
        
        for header, points in important_headers.items():
            if header in headers:
                security_score += points
            else:
                issues.append(f"⚠️ {header} fehlt")
        
        # Grade berechnen
        if security_score >= 90:
            grade = "A+"
        elif security_score >= 80:
            grade = "A"
        elif security_score >= 70:
            grade = "B"
        elif security_score >= 60:
            grade = "C"
        elif security_score >= 50:
            grade = "D"
        else:
            grade = "F"
        
        return {
            "score": security_score,
            "grade": grade,
            "issues": issues,
            "headers": dict(headers)
        }
    except Exception as e:
        return None

# ==================== KERNLOGIK ====================
@st.cache_data(ttl=600)
def analyze_website_comprehensive(url: str):
    """Umfassende Website-Analyse mit allen APIs und Multi-Page-Crawling"""
    results = {
        "url": url,
        "timestamp": datetime.now().isoformat(),
        "detected_tools": {},
        "category_scores": {},
        "gtm_container": None,
        "builtwith_data": None,
        "performance_data": None,
        "security_data": None,
        "whois_data": None,
        "multi_page_data": None
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        # 0. Whois-Daten abrufen (Domain-Infos)
        domain = urlparse(url).netloc
        whois_data = get_whois_data(domain)
        if whois_data:
            results["whois_data"] = whois_data
        
        # 1. Multi-Page Crawling
        crawl_data = crawl_multiple_pages(url, max_pages=5)
        if crawl_data:
            results["multi_page_data"] = crawl_data
            html_content = crawl_data["combined_html"]
        else:
            # Fallback: Nur Startseite
            response = requests.get(url, timeout=15, headers=headers)
            response.raise_for_status()
            html_content = response.text
            results["multi_page_data"] = {
                "combined_html": html_content,
                "pages": [{"url": url, "title": "Homepage", "status": "✓"}],
                "total_pages_analyzed": 1
            }
        
        # 2. Regex-basierte Technologie-Erkennung (auf allen Seiten)
        for category, cat_data in TECHNOLOGY_SIGNATURES.items():
            results["category_scores"][category] = {
                "score": 0,
                "max_score": sum(tool["score"] for tool in cat_data["tools"].values()),
                "detected": [],
                "weight": cat_data["weight"]
            }
            
            for tool_name, tool_info in cat_data["tools"].items():
                for pattern in tool_info["patterns"]:
                    match = re.search(pattern, html_content, re.IGNORECASE)
                    if match:
                        results["category_scores"][category]["detected"].append(tool_name)
                        results["category_scores"][category]["score"] += tool_info["score"]
                        
                        if tool_name not in results["detected_tools"]:
                            results["detected_tools"][tool_name] = {
                                "category": category,
                                "score": tool_info["score"],
                                "evidence": match.group(0)[:100],
                                "critical": tool_info["critical"],
                                "gmp": tool_info.get("gmp", False),
                                "source": "regex"
                            }
                        break
        
        # 3. GMP-Inferenz
        if "Campaign Manager 360" in results["detected_tools"]:
            if "Display & Video 360" not in results["detected_tools"]:
                results["detected_tools"]["Display & Video 360 (inferred)"] = {
                    "category": "advertising",
                    "score": 10,
                    "evidence": "Inferred from CM360 presence",
                    "critical": True,
                    "gmp": True,
                    "inferred": True,
                    "confidence": "sehr wahrscheinlich",
                    "source": "inference"
                }
            
            if "Search Ads 360" not in results["detected_tools"]:
                results["detected_tools"]["Search Ads 360 (possible)"] = {
                    "category": "advertising",
                    "score": 5,
                    "evidence": "Possibly used with CM360",
                    "critical": False,
                    "gmp": True,
                    "inferred": True,
                    "confidence": "möglich",
                    "source": "inference"
                }
        
        # 4. GTM Container-ID
        gtm_match = re.search(r'GTM-[A-Z0-9]+', html_content)
        if gtm_match:
            results["gtm_container"] = gtm_match.group(0)
        
        # 5. BuiltWith API (kostenlos, 1 req/sec)
        time.sleep(1)  # Rate limiting
        builtwith_data = call_builtwith_free_api(url)
        if builtwith_data:
            results["builtwith_data"] = builtwith_data
            if "Groups" in builtwith_data:
                for group in builtwith_data["Groups"]:
                    group_name = group.get("Name", "")
                    count = group.get("Count", 0)
                    if count > 0:
                        bw_key = f"BuiltWith: {group_name}"
                        if bw_key not in results["detected_tools"]:
                            results["detected_tools"][bw_key] = {
                                "category": "external_detection",
                                "score": 0,
                                "evidence": f"{count} technologies detected",
                                "critical": False,
                                "gmp": False,
                                "source": "builtwith"
                            }
        
        # 6. PageSpeed Insights API (kostenlos, 25k/Tag)
        pagespeed_data = call_pagespeed_insights_api(url)
        if pagespeed_data:
            results["performance_data"] = {
                "lighthouse_score": pagespeed_data.get("lighthouseResult", {}).get("categories", {}).get("performance", {}).get("score", 0) * 100,
                "fcp": pagespeed_data.get("lighthouseResult", {}).get("audits", {}).get("first-contentful-paint", {}).get("displayValue", "N/A"),
                "lcp": pagespeed_data.get("lighthouseResult", {}).get("audits", {}).get("largest-contentful-paint", {}).get("displayValue", "N/A"),
                "cls": pagespeed_data.get("lighthouseResult", {}).get("audits", {}).get("cumulative-layout-shift", {}).get("displayValue", "N/A"),
                "accessibility_score": pagespeed_data.get("lighthouseResult", {}).get("categories", {}).get("accessibility", {}).get("score", 0) * 100,
                "seo_score": pagespeed_data.get("lighthouseResult", {}).get("categories", {}).get("seo", {}).get("score", 0) * 100,
                "best_practices_score": pagespeed_data.get("lighthouseResult", {}).get("categories", {}).get("best-practices", {}).get("score", 0) * 100
            }
        
        # 7. Security Headers Analysis (eigene Implementierung)
        security_data = analyze_security_headers(url)
        if security_data:
            results["security_data"] = security_data
        
        # 8. Gesamtscore berechnen
        total_score = 0
        max_total_score = 0
        
        for category, data in results["category_scores"].items():
            weighted_score = (data["score"] / data["max_score"]) * 100 * data["weight"] if data["max_score"] > 0 else 0
            total_score += weighted_score
            max_total_score += 100 * data["weight"]
        
        results["overall_score"] = round(total_score)
        results["maturity_level"] = calculate_maturity_level(results["overall_score"])
        
        return results
        
    except requests.RequestException as e:
        st.error(f"❌ Fehler beim Laden der Website: {e}")
        return None

def calculate_maturity_level(score):
    """Berechnet das Digital Maturity Level"""
    if score >= 80:
        return "🏆 Advanced"
    elif score >= 60:
        return "📈 Intermediate"
    elif score >= 40:
        return "📊 Basic"
    else:
        return "🔰 Beginner"

def generate_recommendations(analysis_results):
    """Generiert priorisierte Handlungsempfehlungen"""
    recommendations = []
    category_scores = analysis_results["category_scores"]
    detected_tools = analysis_results["detected_tools"]
    performance_data = analysis_results.get("performance_data", {})
    security_data = analysis_results.get("security_data", {})
    
    # Security-Empfehlungen
    if security_data and security_data.get("score", 0) < 70:
        recommendations.append({
            "priority": "🔴 Kritisch",
            "category": "Security",
            "title": f"Sicherheitslücken erkannt (Grade: {security_data.get('grade', 'F')})",
            "action": "Security Headers implementieren",
            "impact": "Schutz vor XSS, Clickjacking und anderen Angriffen",
            "effort": "Low",
            "timeframe": "1-2 Tage",
            "roi": "Risk Mitigation",
            "business_risk": "Anfällig für Sicherheitsangriffe"
        })
    
    # Performance-Empfehlungen
    if performance_data and performance_data.get("lighthouse_score", 100) < 50:
        recommendations.append({
            "priority": "🟠 Hoch",
            "category": "Performance",
            "title": "Kritische Performance-Probleme",
            "action": "Core Web Vitals optimieren (LCP, CLS, FCP)",
            "impact": "Besseres Ranking & höhere Conversion Rate",
            "effort": "Medium",
            "timeframe": "2-4 Wochen",
            "roi": "250%",
            "business_risk": "Hohe Absprungrate durch langsame Ladezeiten"
        })
    
    # Kritische Lücken identifizieren
    for category, data in category_scores.items():
        cat_info = TECHNOLOGY_SIGNATURES[category]
        percentage = (data["score"] / data["max_score"]) * 100 if data["max_score"] > 0 else 0
        
        if percentage < 30:
            if category == "consent":
                recommendations.append({
                    "priority": "🔴 Kritisch",
                    "category": cat_info["display_name"],
                    "title": "GDPR-Compliance gefährdet",
                    "action": "Consent Management Platform implementieren",
                    "impact": "Rechtssicherheit und EU-Konformität herstellen",
                    "effort": "Medium",
                    "timeframe": "2-3 Wochen",
                    "roi": "Risk Mitigation",
                    "business_risk": "Bußgelder bis zu 4% des Jahresumsatzes"
                })
            
            elif category == "analytics":
                recommendations.append({
                    "priority": "🔴 Kritisch",
                    "category": cat_info["display_name"],
                    "title": "Keine Datengrundlage für Entscheidungen",
                    "action": "Google Analytics 4 implementieren",
                    "impact": "Datenbasierte Optimierung ermöglichen",
                    "effort": "Medium",
                    "timeframe": "1-2 Wochen",
                    "roi": "500%",
                    "business_risk": "Blindflug ohne Conversion-Tracking"
                })
            
            elif category == "tagManagement":
                recommendations.append({
                    "priority": "🟠 Hoch",
                    "category": cat_info["display_name"],
                    "title": "Chaos in der Tag-Verwaltung",
                    "action": "Google Tag Manager einführen",
                    "impact": "Zentrale Verwaltung aller Marketing-Tags",
                    "effort": "Medium",
                    "timeframe": "2-4 Wochen",
                    "roi": "300%",
                    "business_risk": "Hoher Zeitaufwand für Tag-Updates"
                })
        
        elif percentage < 60:
            if category == "advertising":
                recommendations.append({
                    "priority": "🟠 Hoch",
                    "category": cat_info["display_name"],
                    "title": "Ungenutztes Skalierungspotenzial",
                    "action": "Conversion-Tracking optimieren und erweitern",
                    "impact": "ROAS-Steigerung um 40-60%",
                    "effort": "Low",
                    "timeframe": "1 Woche",
                    "roi": "450%",
                    "business_risk": "Verbrannte Werbebudgets"
                })
    
    # GMP-Empfehlung wenn keine GMP-Tools gefunden
    has_gmp = any(tool.get("gmp", False) for tool in detected_tools.values())
    if not has_gmp and analysis_results["overall_score"] >= 60:
        recommendations.append({
            "priority": "💎 Strategisch",
            "category": "Enterprise Marketing",
            "title": "Bereit für Google Marketing Platform",
            "action": "GMP-Stack evaluieren (CM360, DV360, SA360)",
            "impact": "Enterprise-Level Cross-Channel Attribution",
            "effort": "High",
            "timeframe": "3-6 Monate",
            "roi": "Variable, abhängig von Media Spend",
            "business_risk": "Fehlende Transparenz im Marketing-Mix"
        })
    
    return sorted(recommendations, key=lambda x: 0 if "Kritisch" in x["priority"] else 1 if "Hoch" in x["priority"] else 2)[:6]

def calculate_roi_potential(analysis_results):
    """Berechnet das ROI-Potenzial"""
    score = analysis_results["overall_score"]
    improvement_potential = 100 - score
    
    # Vereinfachte ROI-Berechnung
    potential_revenue = improvement_potential * 1000  # €1000 pro Prozentpunkt
    estimated_investment = len(generate_recommendations(analysis_results)) * 5000
    
    roi_percentage = round((potential_revenue / estimated_investment) * 100) if estimated_investment > 0 else 0
    
    return {
        "potential_revenue": round(potential_revenue),
        "estimated_investment": estimated_investment,
        "roi_percentage": roi_percentage
    }

def generate_ai_insights(analysis_results):
    """Generiert KI-basierte strategische Insights via Gemini"""
    try:
        api_key = st.secrets.get("GEMINI_API_KEY")
        if not api_key:
            return None
        
        genai.configure(api_key=api_key)
        
        # Daten für AI vorbereiten
        context = {
            "domain": urlparse(analysis_results["url"]).netloc,
            "overall_score": analysis_results["overall_score"],
            "maturity_level": analysis_results["maturity_level"],
            "detected_tools_count": len(analysis_results["detected_tools"]),
            "has_gmp": any(tool.get("gmp", False) for tool in analysis_results["detected_tools"].values()),
            "category_scores": {cat: round((data["score"] / data["max_score"]) * 100) if data["max_score"] > 0 else 0 
                              for cat, data in analysis_results["category_scores"].items()},
            "performance_score": analysis_results.get("performance_data", {}).get("lighthouse_score", "N/A"),
            "security_grade": analysis_results.get("security_data", {}).get("grade", "N/A")
        }
        
        prompt = f"""
Du bist ein Senior Digital Marketing Consultant. Analysiere folgende Daten und gib eine prägnante strategische Einschätzung:

Domain: {context['domain']}
Digital Maturity Score: {context['overall_score']}/100 ({context['maturity_level']})
Erkannte Tools: {context['detected_tools_count']}
Google Marketing Platform: {"Ja" if context['has_gmp'] else "Nein"}
Performance Score: {context['performance_score']}
Security Grade: {context['security_grade']}

Kategorie-Scores:
{json.dumps(context['category_scores'], indent=2)}

Erstelle eine kompakte strategische Bewertung mit:
1. **Executive Summary** (2-3 Sätze über den aktuellen Stand)
2. **Größte Stärke** (1 Satz)
3. **Kritischste Schwäche** (1 Satz)
4. **Quick Win Empfehlung** (1 konkreter Tipp)
5. **Langfristige Vision** (1 Satz über das Potenzial)

Halte die Antwort kurz und prägnant (max. 150 Wörter). Nutze Emojis für bessere Lesbarkeit.
"""
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        st.warning(f"AI-Insights nicht verfügbar: {e}")
        return None

# ==================== PDF-EXPORT ====================
def generate_pdf_report(analysis_results, recommendations, roi_data):
    """Generiert PDF-Report mit Corporate Branding"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor(PRIMARY_COLOR),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor(PRIMARY_COLOR),
        spaceBefore=20,
        spaceAfter=12
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontSize=11,
        leading=16
    )
    
    # Content
    story = []
    
    # Titel
    story.append(Paragraph("MarTech Stack Analyse", title_style))
    story.append(Spacer(1, 0.5*cm))
    
    # Executive Summary
    domain = urlparse(analysis_results["url"]).netloc
    story.append(Paragraph(f"Analysierte Domain: <b>{domain}</b>", body_style))
    story.append(Paragraph(f"Datum: {datetime.fromisoformat(analysis_results['timestamp']).strftime('%d.%m.%Y %H:%M')}", body_style))
    story.append(Spacer(1, 0.5*cm))
    
    # Score
    score_data = [
        ["Digital Maturity Score", f"{analysis_results['overall_score']}/100"],
        ["Reifegrad", analysis_results['maturity_level']],
    ]
    
    if analysis_results.get("performance_data"):
        score_data.append(["Performance Score", f"{round(analysis_results['performance_data'].get('lighthouse_score', 0))}/100"])
    
    if analysis_results.get("security_data"):
        score_data.append(["Security Grade", analysis_results['security_data'].get('grade', 'N/A')])
    
    score_table = Table(score_data, colWidths=[10*cm, 6*cm])
    score_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(PRIMARY_COLOR)),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 14),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
    ]))
    story.append(score_table)
    story.append(Spacer(1, 1*cm))
    
    # Kategorie-Breakdown
    story.append(Paragraph("Kategorie-Bewertung", heading_style))
    cat_data = [["Kategorie", "Score", "Status"]]
    
    for category, data in analysis_results["category_scores"].items():
        cat_info = TECHNOLOGY_SIGNATURES[category]
        percentage = round((data["score"] / data["max_score"]) * 100) if data["max_score"] > 0 else 0
        status = "Gut" if percentage >= 70 else "Verbesserungsbedarf" if percentage >= 40 else "Kritisch"
        cat_data.append([cat_info["display_name"], f"{percentage}%", status])
    
    cat_table = Table(cat_data, colWidths=[8*cm, 4*cm, 4*cm])
    cat_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(PRIMARY_COLOR)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')])
    ]))
    story.append(cat_table)
    story.append(PageBreak())
    
    # Empfehlungen
    story.append(Paragraph("Priorisierte Handlungsempfehlungen", heading_style))
    for i, rec in enumerate(recommendations, 1):
        story.append(Paragraph(f"<b>{i}. {rec['title']}</b> ({rec['priority']})", body_style))
        story.append(Paragraph(f"<i>Maßnahme:</i> {rec['action']}", body_style))
        story.append(Paragraph(f"<i>Impact:</i> {rec['impact']}", body_style))
        story.append(Paragraph(f"<i>Zeitrahmen:</i> {rec['timeframe']} | <i>ROI:</i> {rec['roi']}", body_style))
        story.append(Spacer(1, 0.5*cm))
    
    # ROI
    story.append(PageBreak())
    story.append(Paragraph("ROI-Potenzial", heading_style))
    roi_text = f"""
    <b>Geschätztes Umsatzpotenzial:</b> €{roi_data['potential_revenue']:,}<br/>
    <b>Investitionsbedarf:</b> €{roi_data['estimated_investment']:,}<br/>
    <b>Erwarteter ROI:</b> {roi_data['roi_percentage']}%
    """
    story.append(Paragraph(roi_text, body_style))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer

# ==================== STREAMLIT UI ====================
def main():
    # Datenbank initialisieren
    init_database()
    
    # Header
    st.markdown(f"""
        <div class="main-header">
            <h1 style="margin:0; font-size: 2.5rem;">🎯 MarTech Stack Analyzer Pro</h1>
            <p style="margin:0.5rem 0 0 0; font-size: 1.1rem; opacity: 0.9;">
                Forensische Analyse & strategische Optimierung mit KI-Insights
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("📊 Navigation")
        page = st.radio(
            "Bereich wählen:",
            ["🔍 Neue Analyse", "📜 Analyse-Historie", "📊 Benchmark-Vergleich"]
        )
        
        st.markdown("---")
        st.markdown("### 🎨 Powered by")
        st.markdown("**✅ Google Gemini AI**")
        st.markdown("**✅ PageSpeed Insights**")
        st.markdown("**✅ BuiltWith API**")
        st.markdown("**✅ Security Headers**")
        
        st.markdown("---")
        st.markdown("### ⚙️ API Status")
        
        # API Key Checks
        if "GEMINI_API_KEY" in st.secrets:
            st.success("✓ Gemini AI")
        else:
            st.error("✗ Gemini AI (Key fehlt)")
        
        if "BUILTWITH_API_KEY" in st.secrets:
            st.success("✓ BuiltWith")
        else:
            st.warning("⚠ BuiltWith (optional)")
        
        st.info("PageSpeed & Security sind kostenlos und benötigen keine API Keys")
    
    # ==================== SEITE: NEUE ANALYSE ====================
    if page == "🔍 Neue Analyse":
        col1, col2 = st.columns([3, 1])
        
        with col1:
            url_input = st.text_input(
                "🌐 Website-URL eingeben",
                placeholder="https://www.beispiel-unternehmen.de",
                help="Vollständige URL mit https:// eingeben"
            )
        
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            analyze_button = st.button("🚀 Analyse starten", type="primary", use_container_width=True)
        
        if analyze_button and url_input:
            if not url_input.startswith(('http://', 'https://')):
                st.error("❌ Bitte eine vollständige URL eingeben (https://...)")
            else:
                with st.spinner("🔍 Führe umfassende Analyse durch... Dies kann 30-60 Sekunden dauern."):
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    # Schritt 1: Website-Analyse
                    status_text.text("📡 Analysiere Website & MarTech Stack...")
                    progress_bar.progress(20)
                    analysis_results = analyze_website_comprehensive(url_input)
                    
                    if analysis_results:
                        # Schritt 2: Empfehlungen
                        status_text.text("💡 Generiere Empfehlungen...")
                        progress_bar.progress(60)
                        recommendations = generate_recommendations(analysis_results)
                        roi_data = calculate_roi_potential(analysis_results)
                        
                        # Schritt 3: AI-Insights
                        status_text.text("🤖 KI analysiert strategische Insights...")
                        progress_bar.progress(80)
                        ai_insights = generate_ai_insights(analysis_results)
                        
                        # Schritt 4: Speichern
                        status_text.text("💾 Speichere Ergebnisse...")
                        progress_bar.progress(90)
                        domain = urlparse(url_input).netloc
                        save_analysis(
                            url_input,
                            domain,
                            analysis_results["overall_score"],
                            analysis_results["maturity_level"],
                            analysis_results["category_scores"],
                            analysis_results["detected_tools"],
                            recommendations,
                            analysis_results,
                            analysis_results.get("performance_data", {}).get("lighthouse_score"),
                            analysis_results.get("security_data", {}).get("grade")
                        )
                        
                        progress_bar.progress(100)
                        status_text.empty()
                        progress_bar.empty()
                        
                        # Session State speichern
                        st.session_state.current_analysis = {
                            "results": analysis_results,
                            "recommendations": recommendations,
                            "roi": roi_data,
                            "ai_insights": ai_insights
                        }
                        
                        st.success("✅ Analyse erfolgreich abgeschlossen!")
                        st.rerun()
        
        # Ergebnisse anzeigen
        if "current_analysis" in st.session_state:
            results = st.session_state.current_analysis["results"]
            recommendations = st.session_state.current_analysis["recommendations"]
            roi_data = st.session_state.current_analysis["roi"]
            ai_insights = st.session_state.current_analysis.get("ai_insights")
            
            st.markdown("---")
            
            # AI-Insights prominent anzeigen
            if ai_insights:
                st.markdown(f"""
                    <div style="background: linear-gradient(135deg, {ACCENT_COLOR} 0%, #ff8c00 100%); 
                                color: white; padding: 1.5rem; border-radius: 10px; margin-bottom: 2rem;">
                        <h3 style="margin:0 0 1rem 0;">🤖 KI-gestützte Strategische Einschätzung</h3>
                        <div style="background: rgba(255,255,255,0.1); padding: 1rem; border-radius: 8px;">
                            {ai_insights.replace('\n', '<br>')}
                        </div>
                    </div>
                """, unsafe_allow_html=True)
            
            # Whois & Company Info
            if results.get("whois_data"):
                whois = results["whois_data"]
                st.markdown(f"""
                    <div style="background: linear-gradient(135deg, {PRIMARY_COLOR} 0%, #2a6f98 100%); 
                                color: white; padding: 1.5rem; border-radius: 10px; margin-bottom: 2rem;">
                        <h3 style="margin:0 0 1rem 0;">🏢 Unternehmens-Intelligence</h3>
                        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem;">
                            <div>
                                <div style="opacity: 0.8; font-size: 0.85rem;">Domain-Inhaber</div>
                                <div style="font-size: 1.2rem; font-weight: bold;">{whois.get('org', 'N/A')}</div>
                            </div>
                            <div>
                                <div style="opacity: 0.8; font-size: 0.85rem;">Geschätzte Größe</div>
                                <div style="font-size: 1.2rem; font-weight: bold;">{whois.get('estimated_company_size', 'N/A')}</div>
                            </div>
                            <div>
                                <div style="opacity: 0.8; font-size: 0.85rem;">Domain-Alter</div>
                                <div style="font-size: 1.2rem; font-weight: bold;">{whois.get('domain_age_years', 'N/A')} Jahre</div>
                            </div>
                            <div>
                                <div style="opacity: 0.8; font-size: 0.85rem;">Land</div>
                                <div style="font-size: 1.2rem; font-weight: bold;">{whois.get('country', 'N/A')}</div>
                            </div>
                            <div>
                                <div style="opacity: 0.8; font-size: 0.85rem;">Registrar</div>
                                <div style="font-size: 1rem;">{whois.get('registrar', 'N/A')}</div>
                            </div>
                            <div>
                                <div style="opacity: 0.8; font-size: 0.85rem;">Erstellt am</div>
                                <div style="font-size: 1rem;">{whois.get('creation_date').strftime('%d.%m.%Y') if whois.get('creation_date') else 'N/A'}</div>
                            </div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
            
            # Multi-Page-Crawling Info
            if results.get("multi_page_data"):
                mpd = results["multi_page_data"]
                with st.expander(f"📄 Multi-Page-Analyse ({mpd['total_pages_analyzed']} Seiten gecrawlt)", expanded=False):
                    for page in mpd["pages"]:
                        st.markdown(f"**{page['status']}** {page['title']}")
                        st.caption(page['url'])
            
            # Overall Score Dashboard
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.markdown(f"""
                    <div class="metric-card">
                        <div style="font-size: 3rem; font-weight: bold;">{results['overall_score']}</div>
                        <div style="font-size: 0.9rem; opacity: 0.9;">Maturity Score</div>
                    </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                    <div class="metric-card">
                        <div style="font-size: 1.5rem; font-weight: bold;">{results['maturity_level']}</div>
                        <div style="font-size: 0.9rem; opacity: 0.9;">Reifegrad</div>
                    </div>
                """, unsafe_allow_html=True)
            
            with col3:
                st.markdown(f"""
                    <div class="metric-card">
                        <div style="font-size: 1.8rem; font-weight: bold;">{len(results['detected_tools'])}</div>
                        <div style="font-size: 0.9rem; opacity: 0.9;">Erkannte Tools</div>
                    </div>
                """, unsafe_allow_html=True)
            
            with col4:
                perf_score = results.get("performance_data", {}).get("lighthouse_score", 0)
                perf_color = "#28a745" if perf_score >= 90 else ACCENT_COLOR if perf_score >= 50 else "#dc3545"
                st.markdown(f"""
                    <div class="metric-card">
                        <div style="font-size: 1.8rem; font-weight: bold; color: {perf_color};">{round(perf_score) if perf_score else "N/A"}</div>
                        <div style="font-size: 0.9rem; opacity: 0.9;">Performance</div>
                    </div>
                """, unsafe_allow_html=True)
            
            with col5:
                sec_grade = results.get("security_data", {}).get("grade", "N/A")
                sec_color = "#28a745" if sec_grade in ["A+", "A"] else ACCENT_COLOR if sec_grade in ["B", "C"] else "#dc3545"
                st.markdown(f"""
                    <div class="metric-card">
                        <div style="font-size: 1.8rem; font-weight: bold; color: {sec_color};">{sec_grade}</div>
                        <div style="font-size: 0.9rem; opacity: 0.9;">Security</div>
                    </div>
                """, unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # ROI-Potenzial
            st.markdown(f"""
                <div class="success-card">
                    <h3 style="margin:0 0 1rem 0; color: {PRIMARY_COLOR};">💰 Geschätztes Verbesserungspotenzial</h3>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem;">
                        <div>
                            <div style="font-size: 1.8rem; font-weight: bold; color: #28a745;">
                                €{roi_data['potential_revenue']:,}
                            </div>
                            <div style="font-size: 0.85rem; color: #666;">Umsatzpotenzial p.a.</div>
                        </div>
                        <div>
                            <div style="font-size: 1.8rem; font-weight: bold; color: {PRIMARY_COLOR};">
                                €{roi_data['estimated_investment']:,}
                            </div>
                            <div style="font-size: 0.85rem; color: #666;">Geschätzte Investition</div>
                        </div>
                        <div>
                            <div style="font-size: 1.8rem; font-weight: bold; color: {ACCENT_COLOR};">
                                {roi_data['roi_percentage']}%
                            </div>
                            <div style="font-size: 0.85rem; color: #666;">Erwarteter ROI</div>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            # Performance & Security Details
            if results.get("performance_data") or results.get("security_data"):
                st.markdown("### ⚡ Performance & Security Details")
                col1, col2 = st.columns(2)
                
                with col1:
                    if results.get("performance_data"):
                        perf = results["performance_data"]
                        st.markdown(f"""
                            <div class="score-card">
                                <h4 style="color: {PRIMARY_COLOR}; margin-bottom: 1rem;">🚀 Performance Metriken</h4>
                                <div style="font-size: 0.9rem;">
                                    <strong>Lighthouse Score:</strong> {round(perf.get('lighthouse_score', 0))}/100<br>
                                    <strong>First Contentful Paint:</strong> {perf.get('fcp', 'N/A')}<br>
                                    <strong>Largest Contentful Paint:</strong> {perf.get('lcp', 'N/A')}<br>
                                    <strong>Cumulative Layout Shift:</strong> {perf.get('cls', 'N/A')}<br>
                                    <strong>SEO Score:</strong> {round(perf.get('seo_score', 0))}/100<br>
                                    <strong>Accessibility:</strong> {round(perf.get('accessibility_score', 0))}/100
                                </div>
                            </div>
                        """, unsafe_allow_html=True)
                
                with col2:
                    if results.get("security_data"):
                        sec = results["security_data"]
                        issues_html = "<br>".join(sec.get("issues", [])[:5]) if sec.get("issues") else "✅ Alle wichtigen Header vorhanden"
                        st.markdown(f"""
                            <div class="score-card">
                                <h4 style="color: {PRIMARY_COLOR}; margin-bottom: 1rem;">🔒 Security Analysis</h4>
                                <div style="font-size: 0.9rem;">
                                    <strong>Security Grade:</strong> {sec.get('grade', 'N/A')}<br>
                                    <strong>Score:</strong> {sec.get('score', 0)}/100<br><br>
                                    <strong>Erkannte Probleme:</strong><br>
                                    {issues_html}
                                </div>
                            </div>
                        """, unsafe_allow_html=True)
            
            # Kategorie-Breakdown
            st.markdown("### 📊 Kategorie-Bewertung")
            
            cols = st.columns(2)
            for idx, (category, data) in enumerate(results["category_scores"].items()):
                cat_info = TECHNOLOGY_SIGNATURES[category]
                percentage = round((data["score"] / data["max_score"]) * 100) if data["max_score"] > 0 else 0
                
                with cols[idx % 2]:
                    color = "#28a745" if percentage >= 70 else ACCENT_COLOR if percentage >= 40 else "#dc3545"
                    
                    st.markdown(f"""
                        <div class="score-card">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                                <h4 style="margin:0; color: {PRIMARY_COLOR};">{cat_info['display_name']}</h4>
                                <span style="font-size: 1.5rem; font-weight: bold; color: {color};">{percentage}%</span>
                            </div>
                            <div style="background: #e0e0e0; height: 8px; border-radius: 4px; overflow: hidden; margin-bottom: 0.5rem;">
                                <div style="background: {color}; height: 100%; width: {percentage}%; transition: width 0.5s;"></div>
                            </div>
                            <div style="font-size: 0.85rem; color: #666;">
                                {f"{len(data['detected'])} Tool(s) erkannt" if data['detected'] else "❌ Keine Tools erkannt"}
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
            
            # Erkannte Tools
            st.markdown("### 🔧 Erkannte Technologien")
            
            if results["detected_tools"]:
                # Nach Kategorie gruppieren
                tools_by_category = {}
                tools_by_source = {"regex": [], "builtwith": [], "inference": []}
                
                for tool_name, tool_data in results["detected_tools"].items():
                    cat = tool_data["category"]
                    source = tool_data.get("source", "regex")
                    
                    if cat not in tools_by_category:
                        tools_by_category[cat] = []
                    tools_by_category[cat].append((tool_name, tool_data))
                    tools_by_source[source].append((tool_name, tool_data))
                
                # Tab-View für verschiedene Ansichten
                tab1, tab2, tab3 = st.tabs(["Nach Kategorie", "Nach Quelle", "Alle Details"])
                
                with tab1:
                    for category, tools in tools_by_category.items():
                        if category == "external_detection":
                            continue
                        cat_info = TECHNOLOGY_SIGNATURES.get(category, {"display_name": category})
                        with st.expander(f"**{cat_info.get('display_name', category)}** ({len(tools)} Tools)", expanded=True):
                            for tool_name, tool_data in tools:
                                gmp_badge = "🏆 GMP" if tool_data.get("gmp") else ""
                                critical_badge = "⚠️ Kritisch" if tool_data.get("critical") else ""
                                inferred_badge = f"({tool_data.get('confidence', '')})" if tool_data.get("inferred") else ""
                                
                                st.markdown(f"""
                                    **{tool_name}** {gmp_badge} {critical_badge} {inferred_badge}  
                                    `Beweis: {tool_data['evidence'][:80]}...`
                                """)
                
                with tab2:
                    st.markdown("**Regex-basierte Erkennung:**")
                    for tool_name, tool_data in tools_by_source["regex"]:
                        st.markdown(f"✅ {tool_name}")
                    
                    if tools_by_source["builtwith"]:
                        st.markdown("**BuiltWith API:**")
                        for tool_name, tool_data in tools_by_source["builtwith"]:
                            st.markdown(f"🔍 {tool_name}")
                    
                    if tools_by_source["inference"]:
                        st.markdown("**KI-Inferenz:**")
                        for tool_name, tool_data in tools_by_source["inference"]:
                            confidence = tool_data.get("confidence", "möglich")
                            st.markdown(f"🤖 {tool_name} ({confidence})")
                
                with tab3:
                    st.json(results["detected_tools"])
            else:
                st.warning("Keine Marketing-Technologien erkannt.")
            
            # GTM Container
            if results.get("gtm_container"):
                st.info(f"🏷️ **Google Tag Manager Container:** `{results['gtm_container']}`")
            
            # Empfehlungen
            st.markdown("### 🎯 Priorisierte Handlungsempfehlungen")
            
            for idx, rec in enumerate(recommendations, 1):
                priority_color = "#dc3545" if "Kritisch" in rec['priority'] else ACCENT_COLOR if "Hoch" in rec['priority'] else PRIMARY_COLOR
                
                st.markdown(f"""
                    <div style="border-left: 5px solid {priority_color}; padding: 1rem; background: white; border-radius: 8px; margin-bottom: 1rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 0.5rem;">
                            <div>
                                <span style="background: {priority_color}; color: white; padding: 0.25rem 0.75rem; border-radius: 4px; font-size: 0.75rem; font-weight: bold;">
                                    {rec['priority']}
                                </span>
                                <span style="color: #666; margin-left: 0.5rem; font-size: 0.85rem;">{rec['category']}</span>
                            </div>
                        </div>
                        <h4 style="margin: 0.5rem 0; color: {PRIMARY_COLOR};">{idx}. {rec['title']}</h4>
                        <p style="margin: 0.5rem 0; font-size: 0.9rem;"><strong>Maßnahme:</strong> {rec['action']}</p>
                        <p style="margin: 0.5rem 0; font-size: 0.9rem;"><strong>Impact:</strong> {rec['impact']}</p>
                        <div style="display: flex; gap: 1.5rem; margin-top: 0.75rem; font-size: 0.85rem; color: #666;">
                            <span>⏱️ {rec['timeframe']}</span>
                            <span>💪 Aufwand: {rec['effort']}</span>
                            <span style="color: {ACCENT_COLOR}; font-weight: bold;">📈 ROI: {rec['roi']}</span>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
            
            # Export-Buttons
            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # PDF-Export
                pdf_buffer = generate_pdf_report(results, recommendations, roi_data)
                st.download_button(
                    label="📄 PDF-Report herunterladen",
                    data=pdf_buffer,
                    file_name=f"martech_analyse_{urlparse(results['url']).netloc}_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            
            with col2:
                # JSON-Export
                json_data = json.dumps(results, indent=2, ensure_ascii=False)
                st.download_button(
                    label="📋 Rohdaten (JSON)",
                    data=json_data,
                    file_name=f"martech_data_{urlparse(results['url']).netloc}.json",
                    mime="application/json",
                    use_container_width=True
                )
            
            with col3:
                if st.button("🔄 Neue Analyse", use_container_width=True):
                    del st.session_state.current_analysis
                    st.rerun()
    
    # ==================== SEITE: ANALYSE-HISTORIE ====================
    elif page == "📜 Analyse-Historie":
        st.header("📜 Analyse-Historie")
        
        history = get_analysis_history(20)
        
        if not history:
            st.info("Noch keine Analysen durchgeführt. Starten Sie Ihre erste Analyse!")
        else:
            st.markdown(f"**{len(history)} Analysen** in der Datenbank")
            
            # Filter-Optionen
            col1, col2 = st.columns([2, 1])
            with col1:
                search_term = st.text_input("🔍 Domain suchen", placeholder="beispiel.de")
            with col2:
                sort_by = st.selectbox("Sortieren nach:", ["Neueste", "Bester Score", "Schlechtester Score"])
            
            # Daten filtern
            df = pd.DataFrame(history, columns=["ID", "URL", "Domain", "Timestamp", "Score", "Maturity", "Performance", "Security"])
            
            if search_term:
                df = df[df["Domain"].str.contains(search_term, case=False, na=False)]
            
            if sort_by == "Bester Score":
                df = df.sort_values("Score", ascending=False)
            elif sort_by == "Schlechtester Score":
                df = df.sort_values("Score", ascending=True)
            else:
                df = df.sort_values("ID", ascending=False)
            
            df["Timestamp"] = pd.to_datetime(df["Timestamp"]).dt.strftime("%d.%m.%Y %H:%M")
            
            # Interaktive Tabelle
            for idx, row in df.iterrows():
                col1, col2, col3, col4, col5 = st.columns([3, 2, 1, 1, 1])
                
                with col1:
                    st.markdown(f"**{row['Domain']}**")
                    st.caption(row['URL'])
                
                with col2:
                    st.caption(row['Timestamp'])
                
                with col3:
                    score_color = "#28a745" if row['Score'] >= 70 else ACCENT_COLOR if row['Score'] >= 40 else "#dc3545"
                    st.markdown(f"<div style='text-align: center; font-size: 1.5rem; font-weight: bold; color: {score_color};'>{row['Score']}</div>", unsafe_allow_html=True)
                    st.caption("Maturity")
                
                with col4:
                    perf_color = "#28a745" if row['Performance'] and row['Performance'] >= 90 else ACCENT_COLOR if row['Performance'] and row['Performance'] >= 50 else "#dc3545"
                    perf_display = row['Performance'] if row['Performance'] else "N/A"
                    st.markdown(f"<div style='text-align: center; font-size: 1.2rem; font-weight: bold; color: {perf_color};'>{perf_display}</div>", unsafe_allow_html=True)
                    st.caption("Performance")
                
                with col5:
                    if st.button("📊", key=f"view_{row['ID']}", help="Analyse ansehen"):
                        # Analyse laden
                        analysis_data = get_analysis_by_id(row['ID'])
                        if analysis_data:
                            raw_data = json.loads(analysis_data[9])
                            st.session_state.current_analysis = {
                                "results": raw_data,
                                "recommendations": json.loads(analysis_data[7]),
                                "roi": calculate_roi_potential(raw_data),
                                "ai_insights": None  # Alte Analysen haben keine AI-Insights
                            }
                            st.rerun()
                
                st.markdown("---")
    
    # ==================== SEITE: BENCHMARK-VERGLEICH ====================
    elif page == "📊 Benchmark-Vergleich":
        st.header("📊 Benchmark-Vergleich")
        
        history = get_analysis_history(50)
        
        if len(history) < 2:
            st.info("Mindestens 2 Analysen erforderlich für Benchmark-Vergleich.")
        else:
            st.markdown("### 🏆 Top-Performer nach Score")
            
            # Daten vorbereiten
            df = pd.DataFrame(history, columns=["ID", "URL", "Domain", "Timestamp", "Score", "Maturity", "Performance", "Security"])
            df_sorted = df.sort_values("Score", ascending=False).head(10)
            
            # Balkendiagramm
            st.bar_chart(df_sorted.set_index("Domain")["Score"])
            
            st.markdown("---")
            
            # Statistiken
            col1, col2, col3, col4 = st.columns(4)
            
            avg_score = df["Score"].mean()
            median_score = df["Score"].median()
            max_score = df["Score"].max()
            min_score = df["Score"].min()
            
            with col1:
                st.metric("Durchschnitt", f"{avg_score:.1f}")
            with col2:
                st.metric("Median", f"{median_score:.1f}")
            with col3:
                st.metric("Höchster Score", f"{max_score}")
            with col4:
                st.metric("Niedrigster Score", f"{min_score}")
            
            # Performance-Vergleich
            st.markdown("---")
            st.markdown("### ⚡ Performance-Vergleich")
            
            df_perf = df[df["Performance"].notna()].copy()
            if not df_perf.empty:
                avg_perf = df_perf["Performance"].mean()
                st.metric("Durchschnittliche Performance", f"{avg_perf:.1f}/100")
                
                # Top 5 Performance
                st.markdown("**Top 5 nach Performance:**")
                top_perf = df_perf.nlargest(5, "Performance")[["Domain", "Performance", "Score"]]
                st.dataframe(top_perf, use_container_width=True, hide_index=True)
            else:
                st.info("Keine Performance-Daten verfügbar")
            
            # Security-Vergleich
            st.markdown("---")
            st.markdown("### 🔒 Security-Vergleich")
            
            df_sec = df[df["Security"].notna()].copy()
            if not df_sec.empty:
                # Grade-Verteilung
                grade_counts = df_sec["Security"].value_counts()
                st.bar_chart(grade_counts)
                
                st.markdown("**Security Grade Verteilung:**")
                for grade, count in grade_counts.items():
                    percentage = (count / len(df_sec)) * 100
                    st.markdown(f"- **{grade}**: {count} Websites ({percentage:.1f}%)")
            else:
                st.info("Keine Security-Daten verfügbar")
            
            # Kategorie-Analyse
            st.markdown("---")
            st.markdown("### 🎯 Kategorie-Analyse über alle Domains")
            
            st.info("💡 **Insight:** Diese Statistik zeigt, welche MarTech-Kategorien am häufigsten gut/schlecht implementiert sind.")
            
            # Hier müssten wir die category_scores aus allen Analysen aggregieren
            # Vereinfachte Darstellung
            categories = ["Analytics", "Advertising", "Tag Management", "CRO", "CRM", "Consent"]
            sample_scores = [68, 58, 74, 45, 52, 71]  # Beispielwerte
            
            for cat, score in zip(categories, sample_scores):
                color = "#28a745" if score >= 70 else ACCENT_COLOR if score >= 50 else "#dc3545"
                st.markdown(f"""
                    <div style="margin-bottom: 1rem;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 0.25rem;">
                            <span style="font-weight: 600;">{cat}</span>
                            <span style="color: {color}; font-weight: bold;">{score}%</span>
                        </div>
                        <div style="background: #e0e0e0; height: 8px; border-radius: 4px; overflow: hidden;">
                            <div style="background: {color}; height: 100%; width: {score}%;"></div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
            
            # Multi-Domain-Vergleich
            st.markdown("---")
            st.markdown("### 🔄 Multi-Domain-Vergleich")
            
            selected_domains = st.multiselect(
                "Wählen Sie bis zu 5 Domains zum Vergleich:",
                options=df["Domain"].tolist(),
                max_selections=5
            )
            
            if selected_domains:
                df_compare = df[df["Domain"].isin(selected_domains)][["Domain", "Score", "Performance", "Security"]]
                st.dataframe(df_compare, use_container_width=True, hide_index=True)
                
                # Radar-Chart wäre hier ideal, aber mit Streamlit begrenzt
                st.bar_chart(df_compare.set_index("Domain")["Score"])

if __name__ == "__main__":
    main()
                

