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

try:
    import whois
    WHOIS_AVAILABLE = True
except ImportError:
    WHOIS_AVAILABLE = False

# ==================== MODERN CONFIG ====================
st.set_page_config(page_title="MarTech Analyzer Pro", page_icon="🎯", layout="wide")

# Glassmorphism Modern Design
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
        border-radius: 16px;
        padding: 2rem;
        border: 1px solid rgba(255, 255, 255, 0.3);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        margin-bottom: 1.5rem;
    }
    
    .metric-modern {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 16px;
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
        height: 12px;
        border-radius: 10px;
        overflow: hidden;
        margin: 1rem 0;
    }
    
    .progress-bar {
        height: 100%;
        border-radius: 10px;
        transition: width 0.5s ease;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    }
    
    .tool-item {
        background: #f3f4f6;
        padding: 0.75rem 1.25rem;
        border-radius: 10px;
        margin: 0.5rem 0;
        border-left: 4px solid #667eea;
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
        box-shadow: 0 10px 40px rgba(102, 126, 234, 0.4);
    }
</style>
""", unsafe_allow_html=True)

# ==================== DATABASE ====================
def init_db():
    conn = sqlite3.connect('martech_v5.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS analyses (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT, domain TEXT, 
                 timestamp TEXT, overall_score INTEGER, raw_data TEXT)''')
    conn.commit()
    conn.close()

#==================== PRECISE GTM ANALYSIS ====================
@st.cache_data(ttl=3600)
def precise_gtm_analysis(html_content):
    """Ultra-präzise GTM & DataLayer Analyse"""
    gtm_data = {
        "containers": [],
        "datalayer": {
            "found": False,
            "events": [],
            "variables": {},
            "ecommerce_data": {}
        },
        "tags_in_container": {},
        "implementation_score": 0,
        "critical_issues": [],
        "recommendations": []
    }
    
    # 1. ALLE GTM Container finden
    gtm_matches = re.findall(r'GTM-[A-Z0-9]{6,}', html_content)
    gtm_data["containers"] = list(set(gtm_matches))
    
    # 2. DataLayer PRÄZISE extrahieren
    # Finde dataLayer = [...] Deklaration
    dl_declaration = re.search(r'dataLayer\s*=\s*\[(.*?)\];', html_content, re.DOTALL)
    if dl_declaration or re.search(r'window\.dataLayer', html_content):
        gtm_data["datalayer"]["found"] = True
        
        # Extrahiere ALLE dataLayer.push() Calls
        push_pattern = r'dataLayer\.push\s*\(\s*({[^}]+})\s*\)'
        pushes = re.findall(push_pattern, html_content)
        
        for push_str in pushes:
            try:
                # Parse Event-Name
                event_match = re.search(r"['\"]event['\"]:\s*['\"]([^'\"]+)['\"]", push_str)
                if event_match:
                    event_name = event_match.group(1)
                    if event_name not in gtm_data["datalayer"]["events"]:
                        gtm_data["datalayer"]["events"].append(event_name)
                
                # Parse alle Key-Value Pairs
                kv_pattern = r"['\"]([a-zA-Z_][a-zA-Z0-9_]*)['\"]:\s*(?:['\"]([^'\"]*)['\"]|(\d+\.?\d*)|({[^}]*})|(\[[^\]]*\]))"
                for match in re.finditer(kv_pattern, push_str):
                    key = match.group(1)
                    value = match.group(2) or match.group(3) or match.group(4) or match.group(5) or "complex"
                    
                    if key != 'event' and key not in gtm_data["datalayer"]["variables"]:
                        gtm_data["datalayer"]["variables"][key] = str(value)[:100]
                
                # E-Commerce Daten erkennen
                if 'ecommerce' in push_str or 'purchase' in push_str or 'transaction' in push_str:
                    gtm_data["datalayer"]["ecommerce_data"]["found"] = True
                    if 'purchase' in push_str:
                        gtm_data["datalayer"]["ecommerce_data"]["purchase_tracking"] = True
                    if 'add_to_cart' in push_str or 'addToCart' in push_str:
                        gtm_data["datalayer"]["ecommerce_data"]["cart_tracking"] = True
                        
            except:
                continue
    
    # 3. Für jeden Container: gtm.js laden und analysieren
    for container_id in gtm_data["containers"]:
        try:
            gtm_url = f"https://www.googletagmanager.com/gtm.js?id={container_id}"
            resp = requests.get(gtm_url, timeout=10)
            if resp.status_code == 200:
                gtm_js = resp.text
                
                # Tags im Container erkennen
                tag_patterns = {
                    "Google Analytics 4": [r"google-analytics\.com/g/collect", r"gtag.*config.*
