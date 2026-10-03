import os
import json
import html
from pathlib import Path

import requests
import pandas as pd
import altair as alt
import streamlit as st

API = os.environ.get("UPAY_API", "http://127.0.0.1:8000")
ROOT = Path(__file__).resolve().parent.parent

st.set_page_config(page_title="upay সুরক্ষা+", page_icon="🛡️", layout="wide",
                   initial_sidebar_state="collapsed")

# ===================================================================== THEME
# Brand: Yellow = primary / header / key CTA, Blue = secondary / nav / text-buttons,
# White = cards, Dark = text. Green / Amber / Red are used ONLY for LOW / MEDIUM / HIGH risk.
Y, Y2, B, B2 = "#FFC400", "#FFD84D", "#0B3F8F", "#082B63"
INK, MUT, LINE = "#0F1B33", "#47557A", "#E2E8F3"
GREEN, AMBER, RED = "#1E8E3E", "#F59E0B", "#D93025"
LV_COLOR = {"LOW": GREEN, "MEDIUM": AMBER, "HIGH": RED}
FONT = "Plus Jakarta Sans, Hind Siliguri, sans-serif"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Hind+Siliguri:wght@400;500;600;700&display=swap');
:root{
  --y:#FFC400; --y2:#FFD84D; --ysoft:#FFF6D6; --b:#0B3F8F; --b2:#082B63; --bsoft:#E9F0FC;
  --ink:#0F1B33; --mut:#47557A; --line:#E2E8F3; --bg:#F6F8FC; --card:#FFFFFF;
  --g:#1E8E3E; --gs:#E6F4EA; --a:#F59E0B; --as:#FFF4DE; --r:#D93025; --rs:#FDEBE9;
  --sh:0 8px 28px rgba(11,63,143,.08); --sh2:0 2px 8px rgba(11,63,143,.06); --rad:18px;
}
html, body, .stApp, [class*="css"], button, input, textarea, select{
  font-family:'Plus Jakarta Sans','Hind Siliguri',system-ui,-apple-system,'Segoe UI',sans-serif;
}
.stApp{background:var(--bg); color:var(--ink);}
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"]{display:none!important;}
header[data-testid="stHeader"]{background:transparent; height:0;}
.block-container{max-width:1240px; padding:1.1rem 1.2rem 3rem;}
.stMarkdown p{margin-bottom:.4rem;}

/* ---------- top brand bar ---------- */
.topbar{display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; margin:0 0 14px;}
.brand{display:flex; align-items:center; gap:12px;}
.logo{width:46px; height:46px; border-radius:14px; background:var(--y); display:grid; place-items:center;
  box-shadow:0 6px 16px rgba(255,196,0,.45);}
.brand-n{font-size:1.45rem; font-weight:800; color:var(--b); letter-spacing:-.02em; line-height:1;}
.brand-n span{color:var(--ink);}
.brand-s{font-size:.78rem; color:var(--mut); font-weight:600; margin-top:3px;}
.pill{display:inline-flex; align-items:center; gap:6px; padding:6px 12px; border-radius:999px; font-size:.76rem;
  font-weight:700; background:#fff; border:1px solid var(--line); color:var(--b); box-shadow:var(--sh2);}
.pill .dot{width:8px; height:8px; border-radius:50%; background:var(--y);}

/* ---------- tabs = nav bar ---------- */
.stTabs [data-baseweb="tab-list"]{gap:6px; background:#fff; border:1px solid var(--line); border-radius:18px; padding:6px;
  box-shadow:var(--sh); overflow-x:auto; position:sticky; top:8px; z-index:60; scrollbar-width:none;}
.stTabs [data-baseweb="tab-list"]::-webkit-scrollbar{display:none;}
.stTabs [data-baseweb="tab"]{height:46px; border-radius:13px; padding:0 18px; background:transparent; white-space:nowrap;}
.stTabs [data-baseweb="tab"] p{font-weight:700; font-size:.92rem; color:var(--mut);}
.stTabs [data-baseweb="tab"]:hover p{color:var(--b);}
.stTabs [aria-selected="true"]{background:var(--b)!important; box-shadow:inset 0 -4px 0 var(--y);}
.stTabs [aria-selected="true"] p{color:#fff!important;}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"]{display:none!important;}
.stTabs [data-baseweb="tab-panel"]{padding-top:1.1rem;}

/* ---------- hero ---------- */
.hero{display:grid; grid-template-columns:1.35fr 1fr; gap:22px; align-items:center; padding:34px 36px; border-radius:26px;
  background:linear-gradient(135deg,#FFD84D 0%,#FFC400 55%,#FFB800 100%); color:var(--ink); position:relative; overflow:hidden;
  box-shadow:0 18px 46px rgba(255,196,0,.35);}
.hero:before{content:""; position:absolute; right:-90px; top:-90px; width:320px; height:320px; border-radius:50%;
  background:rgba(11,63,143,.10);}
.hero:after{content:""; position:absolute; left:-60px; bottom:-110px; width:260px; height:260px; border-radius:50%;
  background:rgba(255,255,255,.28);}
.hero > *{position:relative; z-index:1;}
.eyebrow{display:inline-block; font-size:.72rem; font-weight:800; letter-spacing:.12em; text-transform:uppercase;
  background:var(--b); color:#fff; padding:6px 12px; border-radius:999px;}
.hero-t{font-size:2.55rem; line-height:1.08; font-weight:800; letter-spacing:-.03em; margin:14px 0 10px; color:var(--ink);}
.hero-t b{color:var(--b);}
.hero-d{font-size:1.04rem; line-height:1.6; color:#1F2B47; max-width:560px;}
.hero-chips{display:flex; flex-wrap:wrap; gap:8px; margin:16px 0 4px;}
.hchip{background:#fff; color:var(--b); font-weight:700; font-size:.82rem; padding:8px 13px; border-radius:12px; box-shadow:var(--sh2);}
.hero-stats{display:flex; flex-wrap:wrap; gap:22px; margin-top:20px; padding-top:16px; border-top:1.5px dashed rgba(15,27,51,.25);}
.hs b{display:block; font-size:1.5rem; font-weight:800; color:var(--b2); letter-spacing:-.02em;}
.hs span{font-size:.76rem; font-weight:700; color:#26324F;}

/* phone mockup */
.phone-wrap{display:flex; justify-content:center;}
.phone{width:290px; max-width:100%; background:#fff; border-radius:34px; padding:12px; border:7px solid var(--b2);
  box-shadow:0 24px 50px rgba(8,43,99,.35); transform:rotate(2deg);}
.ph-top{background:var(--b); color:#fff; border-radius:20px 20px 8px 8px; padding:12px 14px; display:flex; justify-content:space-between; align-items:center;}
.ph-top b{font-size:.95rem;} .ph-top span{font-size:.7rem; opacity:.85;}
.ph-body{padding:12px 4px 4px;}
.ph-row{display:flex; justify-content:space-between; font-size:.78rem; padding:8px 0; border-bottom:1px solid var(--line);}
.ph-row span{color:var(--mut); font-weight:600;} .ph-row b{color:var(--ink);}
.ph-alert{margin-top:10px; background:var(--rs); border:1.5px solid #F4B8B2; border-radius:14px; padding:10px 12px;}
.ph-alert .t{color:var(--r); font-weight:800; font-size:.86rem;}
.ph-alert .s{font-size:.72rem; color:#6b2b26; margin-top:3px; line-height:1.4;}
.ph-btn{margin-top:10px; background:var(--y); color:var(--ink); font-weight:800; text-align:center; padding:10px; border-radius:12px; font-size:.82rem;}
.ph-btn.alt{background:#fff; border:1.5px solid var(--b); color:var(--b); margin-top:6px;}

/* ---------- section headers ---------- */
.sec{margin:2.4rem 0 1rem;}
.sec .eyebrow{background:var(--ysoft); color:var(--b2);}
.sec-t{font-size:1.7rem; font-weight:800; letter-spacing:-.02em; color:var(--ink); margin:.5rem 0 .2rem;}
.sec-s{color:var(--mut); font-size:.98rem; max-width:760px; line-height:1.55;}
.sub-t{font-size:1.02rem; font-weight:800; color:var(--b); margin:1.2rem 0 .5rem; display:flex; align-items:center; gap:8px;}
.sub-t:before{content:""; width:8px; height:22px; border-radius:4px; background:var(--y);}

/* ---------- generic grid + cards ---------- */
.grid{display:grid; grid-template-columns:repeat(auto-fit,minmax(var(--min,230px),1fr)); gap:16px;}
.card{background:var(--card); border:1px solid var(--line); border-radius:var(--rad); padding:20px; box-shadow:var(--sh);
  transition:transform .18s ease, box-shadow .18s ease;}
.card:hover{transform:translateY(-3px); box-shadow:0 14px 34px rgba(11,63,143,.14);}
.ic{width:46px; height:46px; border-radius:14px; display:grid; place-items:center; font-size:1.4rem; background:var(--ysoft); margin-bottom:12px;}
.ic.b{background:var(--bsoft);}
.card-t{font-size:1.12rem; font-weight:800; color:var(--ink); margin-bottom:2px;}
.card-k{font-size:.74rem; font-weight:800; letter-spacing:.06em; text-transform:uppercase; color:var(--b); margin-bottom:8px;}
.card p, .card-p{font-size:.92rem; color:var(--mut); line-height:1.55; margin:0;}
.ps{display:grid; gap:10px; margin-top:10px;}
.ps div{font-size:.9rem; line-height:1.5; color:var(--ink); padding:10px 12px; border-radius:12px;}
.ps .p{background:var(--rs);} .ps .s{background:var(--bsoft);}
.ps b{display:block; font-size:.68rem; letter-spacing:.1em; text-transform:uppercase; margin-bottom:2px;}
.ps .p b{color:var(--r);} .ps .s b{color:var(--b);}
.tag{display:inline-block; font-size:.72rem; font-weight:800; padding:4px 10px; border-radius:999px; background:var(--y); color:var(--ink); margin-top:12px;}
.tag.soft{background:var(--bsoft); color:var(--b);}
.checks{list-style:none; padding:0; margin:10px 0 0;}
.checks li{font-size:.9rem; color:var(--ink); padding:7px 0 7px 28px; position:relative; line-height:1.45;}
.checks li:before{content:"✓"; position:absolute; left:0; top:7px; width:20px; height:20px; border-radius:50%; background:var(--y);
  color:var(--ink); font-weight:900; font-size:.72rem; display:grid; place-items:center;}

/* ---------- KPI cards ---------- */
.kpi{background:#fff; border:1px solid var(--line); border-left:5px solid var(--y); border-radius:16px; padding:14px 16px; box-shadow:var(--sh2);}
.kpi.b{border-left-color:var(--b);} .kpi.LOW{border-left-color:var(--g);} .kpi.MEDIUM{border-left-color:var(--a);} .kpi.HIGH{border-left-color:var(--r);}
.kpi-l{font-size:.74rem; font-weight:800; letter-spacing:.05em; text-transform:uppercase; color:var(--mut);}
.kpi-v{font-size:1.65rem; font-weight:800; color:var(--ink); letter-spacing:-.02em; margin-top:2px; line-height:1.15;}
.kpi-v.LOW{color:var(--g);} .kpi-v.MEDIUM{color:#B7791F;} .kpi-v.HIGH{color:var(--r);}
.kpi-s{font-size:.78rem; color:var(--mut); margin-top:3px; line-height:1.4;}

/* ---------- stepper / flow ---------- */
.steps{display:grid; grid-template-columns:repeat(auto-fit,minmax(138px,1fr)); gap:14px; margin:8px 0 6px;}
.step{background:#fff; border:1px solid var(--line); border-radius:16px; padding:14px 12px 12px; position:relative; box-shadow:var(--sh2);}
.step .n{width:30px; height:30px; border-radius:50%; background:var(--b); color:#fff; font-weight:800; font-size:.85rem;
  display:grid; place-items:center; margin-bottom:8px;}
.step.done .n{background:var(--y); color:var(--ink);} .step.done{border-color:var(--y); background:#FFFBEA;}
.step b{display:block; font-size:.88rem; color:var(--ink); line-height:1.25;}
.step span{display:block; font-size:.74rem; color:var(--mut); margin-top:3px; line-height:1.35;}
.step:not(:last-child):after{content:"➜"; position:absolute; right:-14px; top:50%; transform:translateY(-50%); font-size:.9rem;
  color:var(--b); z-index:2; background:var(--bg); border-radius:50%; width:16px; text-align:center;}

/* ---------- risk visuals ---------- */
.result{display:flex; gap:20px; align-items:center; flex-wrap:wrap; background:#fff; border:1px solid var(--line); border-radius:22px;
  padding:18px 22px; box-shadow:var(--sh); border-top:6px solid var(--g);}
.result.MEDIUM{border-top-color:var(--a);} .result.HIGH{border-top-color:var(--r);}
.gauge{width:210px; max-width:100%; flex:0 0 auto;}
.res-txt{flex:1; min-width:200px;}
.badge{display:inline-flex; align-items:center; gap:8px; font-weight:800; font-size:.95rem; color:#fff; padding:8px 16px; border-radius:999px; background:var(--g);}
.badge.MEDIUM{background:var(--a); color:#3b2a00;} .badge.HIGH{background:var(--r);}
.res-h{font-size:1.35rem; font-weight:800; margin:10px 0 4px; color:var(--ink); letter-spacing:-.01em;}
.res-s{font-size:.9rem; color:var(--mut); line-height:1.5;}
.callout{display:flex; gap:12px; align-items:flex-start; padding:14px 16px; border-radius:16px; border:1.5px solid; margin:10px 0;}
.callout .ci{font-size:1.3rem; line-height:1.2;} .callout .ct{font-weight:800; font-size:.92rem;} .callout .cb{font-size:.9rem; line-height:1.55; margin-top:2px;}
.callout.ok{background:var(--gs); border-color:#B7DFC2; color:#14532d;} .callout.warn{background:var(--as); border-color:#F6D79B; color:#6b4300;}
.callout.bad{background:var(--rs); border-color:#F4B8B2; color:#7a1d16;} .callout.info{background:var(--bsoft); border-color:#C6D8F5; color:var(--b2);}
.callout.tip{background:var(--ysoft); border-color:#F3DE8E; color:#4a3a00;}
.callout.bn .cb{font-family:'Hind Siliguri','Plus Jakarta Sans',sans-serif; font-size:1rem;}
.reasons{display:grid; gap:8px; margin:6px 0 4px;}
.reason{display:flex; gap:10px; align-items:flex-start; background:#fff; border:1px solid var(--line); border-radius:12px; padding:10px 12px; font-size:.9rem; line-height:1.45;}
.reason i{flex:0 0 auto; width:10px; height:10px; border-radius:50%; margin-top:6px; background:var(--g);}
.reason.MEDIUM i{background:var(--a);} .reason.HIGH i{background:var(--r);}
.bar-row{display:grid; grid-template-columns:minmax(120px,34%) 1fr minmax(100px,28%); align-items:center; gap:10px; margin:9px 0; font-size:.86rem;}
.bar-label{font-weight:600; color:var(--ink); line-height:1.3;}
.bar-track{background:#EAEFF7; border-radius:8px; height:14px; overflow:hidden;}
.bar-fill{height:14px; border-radius:8px;}
.bar-val{font-size:.76rem; color:var(--mut); font-weight:600;}
.note{font-size:.78rem; color:var(--mut); line-height:1.5; margin-top:8px;}
.panel{background:#fff; border:1px solid var(--line); border-radius:20px; padding:18px 20px; box-shadow:var(--sh);}
.panel-t{font-size:1rem; font-weight:800; color:var(--b); margin-bottom:6px; display:flex; align-items:center; gap:8px;}
.empty{text-align:center; padding:34px 18px; background:#fff; border:2px dashed #C9D6EE; border-radius:22px; color:var(--mut);}
.empty .e{font-size:2.4rem;} .empty b{display:block; color:var(--ink); font-size:1.05rem; margin:6px 0 4px;}

/* receipt (transaction summary) */
.rcpt{background:#fff; border:1px solid var(--line); border-radius:22px; padding:6px 18px 14px; box-shadow:var(--sh);}
.rcpt-h{display:flex; align-items:center; justify-content:space-between; padding:12px 0; border-bottom:1.5px dashed var(--line); margin-bottom:4px;}
.rcpt-h b{color:var(--b); font-size:1rem;} .rcpt-h span{font-size:.72rem; color:var(--mut); font-weight:700;}
.amt{font-size:2.1rem; font-weight:800; color:var(--ink); letter-spacing:-.02em; padding:8px 0 2px;}
.amt small{display:block; font-size:.74rem; font-weight:700; color:var(--mut); letter-spacing:.05em; text-transform:uppercase;}
.rrow{display:flex; justify-content:space-between; gap:12px; padding:9px 0; border-bottom:1px solid #F0F3F9; font-size:.88rem;}
.rrow:last-child{border-bottom:0;}
.rrow span{color:var(--mut); font-weight:600;} .rrow b{color:var(--ink); text-align:right;}
.yes{color:var(--r);} .no{color:var(--g);}

/* agent: meter + day cards */
.meter{position:relative; height:20px; border-radius:12px; background:#EAEFF7; margin:34px 0 36px;}
.meter .fill{height:20px; border-radius:12px;}
.meter .tick{position:absolute; top:-8px; bottom:-8px; width:0; border-left:2px dashed var(--mut);}
.meter .tick em{position:absolute; top:-20px; left:-30px; width:60px; text-align:center; font-style:normal; font-size:.68rem; font-weight:800; color:var(--mut);}
.meter .tick.d em{top:auto; bottom:-20px;}
.days{display:grid; grid-template-columns:repeat(auto-fit,minmax(104px,1fr)); gap:10px;}
.day{background:#fff; border:1px solid var(--line); border-top:5px solid var(--g); border-radius:14px; padding:10px 10px 12px; text-align:center; box-shadow:var(--sh2);}
.day.MEDIUM{border-top-color:var(--a);} .day.HIGH{border-top-color:var(--r); background:var(--rs);}
.day .d{font-size:.74rem; font-weight:800; color:var(--mut); text-transform:uppercase; letter-spacing:.04em;}
.day .v{font-size:1.05rem; font-weight:800; color:var(--ink); margin:3px 0 2px;}
.day .r{font-size:.7rem; font-weight:700; color:var(--mut);}

/* chart cards (container marker) */
div[data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .cc-mark),
div[data-testid="stVerticalBlock"]:has(> .element-container .cc-mark){
  background:#fff; border:1px solid var(--line); border-radius:20px; padding:16px 18px 10px; box-shadow:var(--sh); gap:.2rem;}
.cc-t{font-weight:800; font-size:.98rem; color:var(--ink);} .cc-s{font-size:.78rem; color:var(--mut); margin-bottom:4px;}

/* ---------- Streamlit widget polish ---------- */
.stButton > button, .stDownloadButton > button{border-radius:13px; font-weight:800; padding:.62rem 1.1rem; border:1.5px solid var(--b);
  color:var(--b); background:#fff; transition:all .15s ease;}
.stButton > button:hover{background:var(--bsoft); border-color:var(--b); color:var(--b2); transform:translateY(-1px);}
.stButton > button[kind="primary"], .stButton > button[data-testid="stBaseButton-primary"]{background:var(--y); color:var(--ink); border-color:var(--y);
  box-shadow:0 8px 20px rgba(255,196,0,.45); width:100%;}
.stButton > button[kind="primary"]:hover, .stButton > button[data-testid="stBaseButton-primary"]:hover{background:var(--y2); border-color:var(--y2); color:var(--ink);}
[data-baseweb="select"] > div, .stNumberInput input, .stTextInput input{border-radius:12px!important; border-color:var(--line)!important; background:#fff!important;}
.stSelectbox label, .stNumberInput label, .stTextInput label, .stRadio > label, .stCheckbox label{font-weight:700!important; color:var(--ink)!important; font-size:.86rem!important;}
[data-testid="stExpander"]{border:1px solid var(--line)!important; border-radius:16px!important; background:#fff; box-shadow:var(--sh2);}
[data-testid="stExpander"] summary{font-weight:700; color:var(--b);}
[data-testid="stDataFrame"]{border:1px solid var(--line); border-radius:14px; overflow:hidden;}
.stRadio [role="radiogroup"]{gap:.5rem;}
.stCaption, [data-testid="stCaptionContainer"]{color:var(--mut)!important;}

.foot{margin-top:2.4rem; padding:18px 20px; border-radius:18px; background:var(--b2); color:#DCE6F8; font-size:.84rem; line-height:1.6;}
.foot b{color:var(--y);}

/* ================= SHAP bigger text ================= */
.bar-row{grid-template-columns:minmax(130px,34%) 1fr minmax(120px,30%); gap:12px; margin:12px 0; font-size:1.05rem;}
.bar-label{font-size:1.05rem; font-weight:700;}
.bar-track{height:18px; border-radius:10px;}
.bar-fill{height:18px; border-radius:10px;}
.bar-val{font-size:.95rem; font-weight:700;}
.note{font-size:.92rem;}

/* ================= slightly brighter (more visible) light text ================= */
.stCaption, [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p{color:var(--mut)!important; opacity:1!important;}

/* ---------- NAV BAR (tabs): same text size, interactive look ---------- */
.stTabs [data-baseweb="tab-list"]{gap:8px; padding:8px; border-radius:22px;}
.stTabs [data-baseweb="tab"]{flex:1 1 auto; justify-content:center; height:50px; padding:0 20px; border-radius:15px;
  border:1.5px solid transparent; background:var(--bg); transition:transform .18s ease, box-shadow .18s ease, background .18s ease, border-color .18s ease;}
.stTabs [data-baseweb="tab"] p{color:var(--ink); transition:color .18s ease;}
.stTabs [data-baseweb="tab"]:hover{background:var(--ysoft); border-color:var(--y); transform:translateY(-3px); box-shadow:0 10px 22px rgba(255,196,0,.40);}
.stTabs [data-baseweb="tab"]:hover p{color:var(--b2);}
.stTabs [data-baseweb="tab"]:active{transform:translateY(0) scale(.98);}
.stTabs [aria-selected="true"]{background:linear-gradient(135deg,var(--b) 0%,var(--b2) 100%)!important; border-color:var(--b2)!important;
  box-shadow:inset 0 -5px 0 var(--y), 0 10px 24px rgba(11,63,143,.40)!important; transform:translateY(-2px);}
.stTabs [aria-selected="true"] p{color:#fff!important;}

/* ---------- BUTTONS: same text size, dynamic look ---------- */
.stButton > button{border-radius:15px; border:2px solid var(--b); position:relative; overflow:hidden;
  transition:transform .16s ease, box-shadow .16s ease, background .16s ease;}
.stButton > button:hover{transform:translateY(-3px); box-shadow:0 12px 24px rgba(11,63,143,.28); background:var(--b); color:#fff;}
.stButton > button:hover p{color:#fff!important;}
.stButton > button:active{transform:translateY(0) scale(.97); box-shadow:none;}
.stButton > button[kind="primary"], .stButton > button[data-testid="stBaseButton-primary"]{
  background:linear-gradient(135deg,#FFD84D 0%,#FFC400 100%); border-color:#E6B000; animation:pulseY 2.4s ease-in-out infinite;}
.stButton > button[kind="primary"] p, .stButton > button[data-testid="stBaseButton-primary"] p{color:var(--ink)!important;}
.stButton > button[kind="primary"]:hover, .stButton > button[data-testid="stBaseButton-primary"]:hover{background:linear-gradient(135deg,#FFE27A 0%,#FFCF2E 100%);
  color:var(--ink); border-color:#E6B000; box-shadow:0 14px 28px rgba(255,196,0,.60);}
.stButton > button[kind="primary"]:hover p, .stButton > button[data-testid="stBaseButton-primary"]:hover p{color:var(--ink)!important;}
@keyframes pulseY{0%,100%{box-shadow:0 8px 20px rgba(255,196,0,.45);} 50%{box-shadow:0 8px 30px rgba(255,196,0,.85);}}
.hchip{border:2px solid transparent; transition:all .18s ease;}
.hchip:hover{transform:translateY(-3px); border-color:var(--b); box-shadow:0 10px 22px rgba(11,63,143,.25);}

/* ---------- responsive ---------- */
@media (max-width: 900px){
  .hero{grid-template-columns:1fr; padding:26px 22px;}
  .hero-t{font-size:2rem;}
  .phone{transform:none; margin-top:6px;}
  .step:not(:last-child):after{display:none;}
}
@media (max-width: 640px){
  .block-container{padding:.7rem .7rem 2.5rem;}
  .sec-t{font-size:1.35rem;}
  .hero-t{font-size:1.7rem;}
  .stTabs [data-baseweb="tab"]{flex:0 0 auto; padding:0 12px; height:44px;}
  .hero-stats{gap:16px;}
  .gauge{margin:0 auto;}
  .result{padding:16px;}
  .bar-row{grid-template-columns:1fr; gap:4px;}
  .kpi-v{font-size:1.35rem;}
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ===================================================================== HELPERS
def put(s: str):
    """Render HTML. Every line is stripped so Markdown never turns indentation into a code block."""
    st.markdown(" ".join(line.strip() for line in s.strip().splitlines()), unsafe_allow_html=True)


def esc(x) -> str:
    return html.escape(str(x))


def stretch(fn, *args, **kwargs):
    """width='stretch' on new Streamlit, use_container_width on older ones."""
    try:
        return fn(*args, width="stretch", **kwargs)
    except TypeError:
        return fn(*args, use_container_width=True, **kwargs)


def api_get(path, timeout=60):
    r = requests.get(f"{API}{path}", timeout=timeout)
    r.raise_for_status()
    return r.json()


def api_post(path, payload=None, timeout=30):
    r = requests.post(f"{API}{path}", json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()


def api_error(e):
    st.error(f"Could not reach the backend at {API}. Start it with: "
             f"`uvicorn api.main:app --port 8000`  (details: {e})")


def section(eyebrow, title, sub=""):
    sub_html = f'<div class="sec-s">{sub}</div>' if sub else ""
    put(f'<div class="sec"><span class="eyebrow">{esc(eyebrow)}</span><div class="sec-t">{title}</div>{sub_html}</div>')


def subtitle(text):
    put(f'<div class="sub-t">{esc(text)}</div>')


def kpi(label, value, sub="", tone=""):
    s = f'<div class="kpi-s">{sub}</div>' if sub else ""
    return (f'<div class="kpi {tone}"><div class="kpi-l">{esc(label)}</div>'
            f'<div class="kpi-v {tone}">{value}</div>{s}</div>')


def kpi_grid(cards, min_w=190):
    put(f'<div class="grid" style="--min:{min_w}px">{"".join(cards)}</div>')


def stepper(steps, done=0):
    """steps = [(title, small description)]; first `done` steps are highlighted."""
    items = ""
    for i, (t, d) in enumerate(steps):
        cls = "step done" if i < done else "step"
        items += f'<div class="{cls}"><div class="n">{i + 1}</div><b>{esc(t)}</b><span>{esc(d)}</span></div>'
    put(f'<div class="steps">{items}</div>')


def callout(kind, title, body, icon=None, extra=""):
    ic = icon or {"ok": "✅", "warn": "⚠️", "bad": "🔐", "info": "ℹ️", "tip": "💡"}[kind]
    put(f'<div class="callout {kind} {extra}"><div class="ci">{ic}</div>'
        f'<div><div class="ct">{esc(title)}</div><div class="cb">{esc(body)}</div></div></div>')


def taka(v):
    return f"৳{v:,.0f}"


def gauge_svg(score, level):
    """Semi-circle risk gauge. Fill = score (0-100%), colour = risk level, ticks = MEDIUM / HIGH thresholds."""
    import math
    col = LV_COLOR[level]
    pct = max(0.0, min(score, 1.0)) * 100

    def pt(frac, r):
        a = math.pi * (1 - frac)
        return 100 + r * math.cos(a), 100 - r * math.sin(a)

    ticks = ""
    for th in (0.15, 0.30):
        x1, y1 = pt(th, 68)
        x2, y2 = pt(th, 92)
        ticks += f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#8795B3" stroke-width="2" stroke-dasharray="3 2"/>'
    return (f'<svg class="gauge" viewBox="0 0 200 128" xmlns="http://www.w3.org/2000/svg">'
            f'<path d="M 20 100 A 80 80 0 0 1 180 100" pathLength="100" fill="none" stroke="#EAEFF7" stroke-width="16" stroke-linecap="round"/>'
            f'<path d="M 20 100 A 80 80 0 0 1 180 100" pathLength="100" fill="none" stroke="{col}" stroke-width="16" '
            f'stroke-linecap="round" stroke-dasharray="{max(pct, 1.5):.1f} 100"/>{ticks}'
            f'<text x="100" y="92" text-anchor="middle" font-size="34" font-weight="800" fill="{INK}" '
            f'font-family="Plus Jakarta Sans, sans-serif">{pct:.0f}%</text>'
            f'<text x="100" y="114" text-anchor="middle" font-size="11" font-weight="700" fill="{MUT}" '
            f'font-family="Plus Jakarta Sans, sans-serif">RISK SCORE</text>'
            f'<text x="20" y="124" text-anchor="middle" font-size="9" fill="{MUT}">0</text>'
            f'<text x="180" y="124" text-anchor="middle" font-size="9" fill="{MUT}">100</text></svg>')


def shap_bars(drivers):
    if not drivers:
        return
    mx = max(abs(d["shap"]) for d in drivers) or 1
    rows = ""
    for d in drivers:
        up = d["shap"] > 0
        rows += (f'<div class="bar-row"><div class="bar-label">{esc(d["label"])}</div>'
                 f'<div class="bar-track"><div class="bar-fill" style="width:{max(abs(d["shap"]) / mx * 100, 3):.0f}%;'
                 f'background:{RED if up else GREEN}"></div></div>'
                 f'<div class="bar-val">{"▲ raises risk" if up else "▼ lowers risk"} ({d["shap"]:+.2f})</div></div>')
    put(rows)
    put('<div class="note">SHAP contribution of each feature to this score (log-odds). '
        'Red raises the risk score, green lowers it.</div>')


def chart_card(title, sub=""):
    """Returns a container styled as a white card, holding a title + subtitle (chart goes inside it)."""
    box = st.container()
    with box:
        put(f'<span class="cc-mark"></span><div class="cc-t">{esc(title)}</div><div class="cc-s">{esc(sub)}</div>')
    return box


def style_chart(ch, height=250):
    return (ch.properties(height=height, background="transparent")
            .configure_view(strokeWidth=0)
            .configure_axis(labelFont=FONT, titleFont=FONT, labelColor=MUT, titleColor=MUT, labelFontSize=11,
                            titleFontSize=11, gridColor="#EDF1F8", domainColor="#D5DDEC", tickColor="#D5DDEC")
            .configure_legend(labelFont=FONT, titleFont=FONT, labelColor=INK, orient="bottom", title=None))


@st.cache_data(show_spinner=False, ttl=60)
def get_metrics():
    """Metrics from the API; falls back to the local metrics.json so the Overview never looks empty."""
    try:
        return api_get("/metrics", 10)
    except Exception:
        p = ROOT / "models" / "metrics.json"
        return {"scamshield": json.loads(p.read_text(encoding="utf-8")) if p.exists() else None,
                "agent_forecast": None}


@st.cache_data(show_spinner=False)
def load_overview_data():
    """Aggregates of the synthetic dataset, only for the Overview charts (read-only)."""
    p = ROOT / "data" / "transactions.csv"
    if not p.exists():
        return None
    t = pd.read_csv(p, usecols=["customer_id", "tx_type", "amount", "timestamp", "is_scam", "pattern"],
                    parse_dates=["timestamp"])
    pretty = {"rapid_burst": "Rapid transfers (10 min)", "new_recipient_big": "New recipient + big amount",
              "night_tx": "Late-night transfer", "refund_scam": "'Refund' after receiving money"}
    pat = (t[t.is_scam == 1].pattern.map(pretty).value_counts().rename_axis("pattern").reset_index(name="count"))
    hourly = (t.groupby(t.timestamp.dt.hour).is_scam.mean() * 100).rename_axis("hour").reset_index(name="rate")
    co = t[t.tx_type == "cashout"].copy()
    co["dow"] = co.timestamp.dt.dayofweek
    co["date"] = co.timestamp.dt.normalize()
    days_per_dow = co.groupby("dow").date.nunique()
    wk = (co.groupby("dow").amount.sum() / days_per_dow / 1e6).reset_index(name="vol")
    wk["day"] = wk.dow.map(dict(enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])))
    mix = t.tx_type.value_counts().rename_axis("type").reset_index(name="count")
    mix["type"] = mix["type"].map({"send": "Send money", "cashout": "Cash-out", "merchant": "Merchant pay",
                                   "billpay": "Bill pay"})
    return dict(n_tx=len(t), scam_pct=float(t.is_scam.mean() * 100), pat=pat, hourly=hourly, wk=wk, mix=mix)


# ===================================================================== STATIC DATA
ICON = {"LOW": "🟢", "MEDIUM": "🟠", "HIGH": "🔴"}
STATUS = {"pending": "Pending review", "customer_warned": "Customer warned",
          "confirmed_safe": "Confirmed safe", "held_for_review": "Held for review"}
LV_HEAD = {"LOW": "Looks normal — safe to proceed", "MEDIUM": "Unusual pattern — please double-check",
           "HIGH": "Verify before sending — flagged for review"}
WARN, DANGER = 0.8, 1.0   # same demand / cash thresholds as the backend

SCENARIOS = {
    "Normal transaction": dict(recipient="01712-XXXXXX (saved contact)", amount=600, amount_ratio=1.0, hour=14,
                               is_new_recipient=0, tx_last_10min=1, just_received_money=0),
    "Unusual transaction (new recipient, larger amount)": dict(recipient="01811-XXXXXX (new)", amount=2500,
                               amount_ratio=4.0, hour=14, is_new_recipient=1, tx_last_10min=1, just_received_money=0),
    "Scam-like: new recipient + big amount at 3 AM": dict(recipient="01911-XXXXXX (new)", amount=8000,
                               amount_ratio=9.0, hour=3, is_new_recipient=1, tx_last_10min=1, just_received_money=0),
    "Scam-like: 'refund' sent right after receiving money": dict(recipient="01611-XXXXXX (new)", amount=3000,
                               amount_ratio=1.5, hour=15, is_new_recipient=1, tx_last_10min=1, just_received_money=1),
    "Scam-like: 4 rapid transfers in 10 minutes": dict(recipient="01511-XXXXXX (new)", amount=1500,
                               amount_ratio=1.2, hour=14, is_new_recipient=1, tx_last_10min=4, just_received_money=0),
}

SHIELD = ('<svg width="26" height="26" viewBox="0 0 24 24" fill="none"><path d="M12 2l8 3v6c0 5-3.4 9.3-8 11-4.6-1.7-8-6-8-11V5l8-3z" '
          f'fill="{B}"/><path d="M8.2 12.2l2.6 2.6 5-5.4" stroke="{Y}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>')

# ===================================================================== TOP BAR
put(f"""
<div class="topbar">
  <div class="brand">
    <div class="logo">{SHIELD}</div>
    <div><div class="brand-n">upay <span>সুরক্ষা+</span></div>
    <div class="brand-s">Safe for Customers. Smarter for Agents.</div></div>
  </div>
  <div class="pill"><span class="dot"></span>Hackathon prototype · synthetic data only</div>
</div>
""")

tab0, tab1, tab2, tab3, tab4 = st.tabs(
    ["🏠 Overview", "👤 Customer · ScamShield", "🏪 Agent · Copilot", "🔍 Analyst Console", "📊 Model & Responsible AI"])

# ===================================================================== OVERVIEW
with tab0:
    met = get_metrics()
    sm = (met or {}).get("scamshield") or {}
    ov = load_overview_data()

    stats = ""
    if ov:
        stats += f'<div class="hs"><b>{ov["n_tx"] / 1000:,.0f}K</b><span>demo transactions</span></div>'
    if sm:
        stats += f'<div class="hs"><b>{sm["roc_auc"]:.3f}</b><span>ROC-AUC</span></div>'
        stats += f'<div class="hs"><b>{sm["recall"] * 100:.0f}%</b><span>scam-like caught (recall)</span></div>'
    stats += '<div class="hs"><b>3</b><span>AI features · 1 platform</span></div>'

    put(f"""
    <div class="hero">
      <div>
        <span class="eyebrow">AI safety &amp; intelligence layer</span>
        <div class="hero-t">Safe for <b>Customers.</b><br>Smarter for <b>Agents.</b></div>
        <div class="hero-d">upay সুরক্ষা+ stops scam-like transfers <b>before</b> money leaves, explains every warning in plain
        language (Bangla + English), and tells agents <b>when their cash will run short</b> — with a human always making the final call.</div>
        <div class="hero-chips"><span class="hchip">🛡️ ScamShield</span><span class="hchip">🏪 Agent Copilot</span>
        <span class="hchip">💰 Cost Advisor</span><span class="hchip">🔍 Analyst Console</span></div>
        <div class="hero-stats">{stats}</div>
      </div>
      <div class="phone-wrap"><div class="phone">
        <div class="ph-top"><b>Send Money</b><span>upay</span></div>
        <div class="ph-body">
          <div class="ph-row"><span>To</span><b>01911-XXXXXX (new)</b></div>
          <div class="ph-row"><span>Amount</span><b>৳8,000</b></div>
          <div class="ph-row"><span>Time</span><b>03:02 AM</b></div>
          <div class="ph-alert"><div class="t">🔴 HIGH RISK</div>
          <div class="s">New recipient · 9× your usual amount · late-night. Please verify before sending. Never share your PIN or OTP.</div></div>
          <div class="ph-btn">Verify recipient</div><div class="ph-btn alt">Cancel</div>
        </div>
      </div></div>
    </div>
    """)

    # ---- live model KPIs
    if sm:
        subtitle("Model health at a glance")
        cards = [kpi("ROC-AUC", f'{sm["roc_auc"]:.3f}', "How well scam-like vs normal are separated"),
                 kpi("Recall", f'{sm["recall"] * 100:.0f}%', "Share of scam-like transactions caught", "b"),
                 kpi("Precision", f'{sm["precision"] * 100:.0f}%', "Share of flags that are truly scam-like"),
                 kpi("False alarm rate", f'{sm["false_alarm_rate"] * 100:.1f}%', "Normal transactions wrongly flagged", "b")]
        fc = (met or {}).get("agent_forecast")
        if fc:
            cards.append(kpi("Forecast vs baseline", f'+{fc["improvement_pct"]}%', "Lower error than a 7-day average"))
        kpi_grid(cards, 180)

    # ---- problem -> solution
    section("The problem we solve", "Three everyday problems. One AI layer.",
            "Each feature starts from a real pain point for upay customers or agents and ends with a clear, explainable action.")
    put("""
    <div class="grid" style="--min:290px">
      <div class="card"><div class="ic">🛡️</div><div class="card-k">For customers</div><div class="card-t">ScamShield</div>
        <div class="ps"><div class="p"><b>Problem</b>Scam-like transfers (refund tricks, midnight transfers, rapid bursts) look normal until the money is gone.</div>
        <div class="s"><b>Solution</b>Scores every transfer 0–100%, shows <i>why</i> with SHAP, and recommends a safer next step.</div></div>
        <span class="tag">Detect · Explain · Protect</span></div>
      <div class="card"><div class="ic b">🏪</div><div class="card-k">For agents</div><div class="card-t">Agent Copilot</div>
        <div class="ps"><div class="p"><b>Problem</b>Cash runs out on peak days (salary week, Thursdays) and customers get turned away.</div>
        <div class="s"><b>Solution</b>Forecasts 7-day cash-out demand and warns the agent early with a suggested top-up.</div></div>
        <span class="tag">Forecast · Warn · Prepare</span></div>
      <div class="card"><div class="ic">💰</div><div class="card-k">Supporting feature</div><div class="card-t">Cost Advisor</div>
        <div class="ps"><div class="p"><b>Problem</b>Frequent small cash-outs quietly add up in fees.</div>
        <div class="s"><b>Solution</b>Groups customers by behaviour and suggests shifting some small cash-outs to merchant payments.</div></div>
        <span class="tag soft">Analyze · Suggest · Save (assumption-based)</span></div>
    </div>
    """)

    # ---- how it works
    section("How it works", "From a transaction to a decision — step by step",
            "Prediction (model score) and recommendation (policy) are separate, transparent layers.")
    subtitle("🛡️ ScamShield flow")
    stepper([("Customer transaction", "Amount, recipient, time"), ("Behaviour analysis", "Compared with usual habits"),
             ("AI risk engine", "LightGBM model"), ("Risk score", "LOW · MEDIUM · HIGH"),
             ("SHAP explanation", "Top reasons, in plain words"), ("Recommended action", "Warn or verify"),
             ("Human review", "Analyst makes the final call")], done=7)
    subtitle("🏪 Agent Copilot flow")
    stepper([("Historical agent data", "Daily cash-out history"), ("Forecast model", "LightGBM regressor"),
             ("Future demand", "Next 7 days"), ("Liquidity risk", "Demand vs cash on hand"),
             ("Recommendation", "Top-up before the peak day")], done=5)

    # ---- who benefits
    section("Who benefits", "Value for every side of the platform")
    put("""
    <div class="grid" style="--min:260px">
      <div class="card"><div class="ic">👤</div><div class="card-t">Customer</div>
        <ul class="checks"><li>Clear, respectful warnings before sending</li><li>Reasons shown in Bangla and English</li><li>Fewer losses to scam-like transfers</li></ul></div>
      <div class="card"><div class="ic b">🏪</div><div class="card-t">Agent</div>
        <ul class="checks"><li>Early warning before cash shortage</li><li>Exact suggested top-up amount</li><li>Fewer turned-away customers</li></ul></div>
      <div class="card"><div class="ic">🏢</div><div class="card-t">upay</div>
        <ul class="checks"><li>AI-assisted risk monitoring with analyst queue</li><li>Explainable, auditable decisions</li><li>Stronger operational intelligence</li></ul></div>
    </div>
    """)

    # ---- demo guide
    section("Try it yourself", "A 2-minute guided demo", "Follow the tabs at the top in this order.")
    put("""
    <div class="steps">
      <div class="step"><div class="n">1</div><b>Customer · ScamShield</b><span>Pick the “3 AM” scenario and press Analyze.</span></div>
      <div class="step"><div class="n">2</div><b>Analyst Console</b><span>Open the flagged case and confirm safe or hold.</span></div>
      <div class="step"><div class="n">3</div><b>Agent · Copilot</b><span>Choose a high-pressure agent and read the warning.</span></div>
      <div class="step"><div class="n">4</div><b>Model &amp; Responsible AI</b><span>Check metrics and our safety principles.</span></div>
    </div>
    """)

    # ---- data graphs
    if ov:
        section("See it in the data", "What the synthetic data tells us",
                "Aggregated from the demo dataset. Synthetic, not real upay data.")
        g1, g2 = st.columns(2, gap="medium")
        with g1:
            with chart_card("Scam-like patterns in the data", "Number of flagged transactions by pattern"):
                ch = (alt.Chart(ov["pat"]).mark_bar(cornerRadiusEnd=6, color=B, size=22)
                      .encode(y=alt.Y("pattern:N", sort="-x", title=None, axis=alt.Axis(labelLimit=220)),
                              x=alt.X("count:Q", title="Transactions"), tooltip=["pattern", "count"]))
                txt = ch.mark_text(align="left", dx=5, color=INK, fontWeight=700, font=FONT).encode(text="count:Q")
                stretch(st.altair_chart, style_chart(ch + txt, 240))
        with g2:
            with chart_card("Scam-like share by hour of day", "Late-night hours (0–5) carry far more risk"):
                night = alt.Chart(pd.DataFrame({"s": [-0.5], "e": [5.5]})).mark_rect(color=Y, opacity=.28).encode(x="s:Q", x2="e:Q")
                area = (alt.Chart(ov["hourly"]).mark_area(line={"color": RED, "strokeWidth": 3}, color=RED, opacity=.16,
                                                          interpolate="monotone")
                        .encode(x=alt.X("hour:Q", title="Hour of day", scale=alt.Scale(domain=[-0.5, 23.5]),
                                        axis=alt.Axis(values=list(range(0, 24, 3)))),
                                y=alt.Y("rate:Q", title="% scam-like"),
                                tooltip=[alt.Tooltip("hour:Q", title="Hour"), alt.Tooltip("rate:Q", title="% scam-like", format=".1f")]))
                stretch(st.altair_chart, style_chart(night + area, 240))
        g3, g4 = st.columns(2, gap="medium")
        with g3:
            with chart_card("Agent cash-out demand by weekday", "Average cash-out volume per day (৳ million) — Thursday peaks, Friday dips"):
                ch = (alt.Chart(ov["wk"]).mark_bar(cornerRadiusTopLeft=8, cornerRadiusTopRight=8)
                      .encode(x=alt.X("day:N", sort=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], title=None,
                                      axis=alt.Axis(labelAngle=0)),
                              y=alt.Y("vol:Q", title="৳ million / day"),
                              color=alt.condition(alt.datum.day == "Thu", alt.value(Y), alt.value(B)),
                              tooltip=["day", alt.Tooltip("vol:Q", format=".2f", title="৳ million/day")]))
                stretch(st.altair_chart, style_chart(ch, 240))
        with g4:
            with chart_card("Transaction mix", "Share of each transaction type in the demo data"):
                ch = (alt.Chart(ov["mix"]).mark_arc(innerRadius=58, outerRadius=100, stroke="#fff", strokeWidth=2)
                      .encode(theta="count:Q",
                              color=alt.Color("type:N", scale=alt.Scale(domain=["Send money", "Cash-out", "Merchant pay", "Bill pay"],
                                                                         range=[B, Y, "#6C8EC9", "#BFD0EE"])),
                              tooltip=["type", "count"]))
                stretch(st.altair_chart, style_chart(ch, 240))
        st.caption(f"Overall, {ov['scam_pct']:.1f}% of the synthetic transactions are scam-like by construction. "
                   "Results on synthetic data do not predict real-world performance.")

    put('<div class="foot"><b>Prototype notice.</b> Built on synthetic demo data only. Not integrated with, and not using any data from, '
        'real upay systems. The AI supports people; it never blocks accounts or transactions on its own.</div>')

# ===================================================================== CUSTOMER
with tab1:
    section("Customer view", "ScamShield — check a transaction before sending",
            "Choose a demo scenario, tweak the details if you like, then let the AI explain the risk.")
    last = st.session_state.get("last")

    left, right = st.columns([1, 1.25], gap="large")
    with left:
        name = st.selectbox("Demo scenario", list(SCENARIOS))
        idx = list(SCENARIOS).index(name)
        p0 = SCENARIOS[name]
        with st.expander("✏️ Edit transaction details", expanded=False):
            e1, e2 = st.columns(2)
            recipient = e1.text_input("Recipient (demo number)", p0["recipient"], key=f"rc{idx}")
            amount = e2.number_input("Amount (BDT)", min_value=1.0, value=float(p0["amount"]), step=100.0, key=f"am{idx}")
            e3, e4 = st.columns(2)
            ratio = e3.number_input("Amount vs customer's usual (x)", min_value=0.1, value=float(p0["amount_ratio"]),
                                    step=0.5, key=f"ra{idx}")
            hour = e4.number_input("Hour of day (0-23)", 0, 23, int(p0["hour"]), key=f"hr{idx}")
            e5, e6 = st.columns(2)
            burst = e5.number_input("Transactions in last 10 min", 1, 10, int(p0["tx_last_10min"]), key=f"bu{idx}")
            new_rec = e5.checkbox("New recipient", bool(p0["is_new_recipient"]), key=f"nr{idx}")
            jr = e6.checkbox("Just received money", bool(p0["just_received_money"]), key=f"jr{idx}")
        payload = dict(recipient=recipient, amount=amount, amount_ratio=ratio, hour=int(hour),
                       is_new_recipient=int(new_rec), tx_last_10min=int(burst), just_received_money=int(jr))

        nr_html = '<b class="yes">Yes</b>' if payload["is_new_recipient"] else '<b class="no">No</b>'
        jr_html = '<b class="yes">Yes</b>' if payload["just_received_money"] else '<b class="no">No</b>'
        n = payload["tx_last_10min"]
        put(f"""
        <div class="rcpt">
          <div class="rcpt-h"><b>📤 Send Money</b><span>TRANSACTION SUMMARY</span></div>
          <div class="amt"><small>Amount</small>{taka(payload["amount"])}</div>
          <div class="rrow"><span>Recipient</span><b>{esc(payload["recipient"].split(" ")[0])}</b></div>
          <div class="rrow"><span>Time</span><b>{payload["hour"]:02d}:00</b></div>
          <div class="rrow"><span>New recipient</span>{nr_html}</div>
          <div class="rrow"><span>Amount vs usual</span><b>{payload["amount_ratio"]:.1f}×</b></div>
          <div class="rrow"><span>Activity (10 min)</span><b>{n} txn{"" if n == 1 else "s"}</b></div>
          <div class="rrow"><span>Just received money</span>{jr_html}</div>
        </div>
        """)
        st.write("")
        if st.button("🔎 Analyze transaction", type="primary"):
            try:
                st.session_state["last"] = (name, api_post("/score", payload))
                last = st.session_state["last"]
            except Exception as e:
                api_error(e)

    show = bool(last and last[0] == name)
    with right:
        subtitle("Protection journey")
        stepper([("Transaction", "Customer sends money"), ("AI risk score", "0–100% from LightGBM"),
                 ("Explain", "SHAP shows why"), ("Action", "Warn · verify · review")], done=4 if show else 1)
        if not show:
            put('<div class="empty"><div class="e">🛡️</div><b>No analysis yet</b>'
                'Press <b style="display:inline;color:var(--b)">Analyze transaction</b> to see the risk score, reasons and recommended action.</div>')
        else:
            r = last[1]
            lv = r["risk_level"]
            put(f"""
            <div class="result {lv}">
              {gauge_svg(r["risk_score"], lv)}
              <div class="res-txt">
                <span class="badge {lv}">{ICON[lv]} {lv} RISK</span>
                <div class="res-h">{LV_HEAD[lv]}</div>
                <div class="res-s">Ticks on the gauge mark the MEDIUM ({r["thresholds"]["medium"]:.2f}) and HIGH ({r["thresholds"]["high"]:.2f}) policy thresholds.</div>
              </div>
            </div>
            """)
            subtitle("Why was it flagged?" if lv != "LOW" else "Reasons")
            put('<div class="reasons">' + "".join(f'<div class="reason {lv}"><i></i><div>{esc(x)}</div></div>'
                                                  for x in r["reasons"]) + "</div>")
            kind = {"LOW": "ok", "MEDIUM": "warn", "HIGH": "bad"}[lv]
            callout(kind, "Recommended action", r["recommended_action"])
            callout("info", "বাংলা বার্তা", r["message_bn"], icon="💬", extra="bn")
            if r["needs_human_review"]:
                callout("tip", "Sent to the analyst queue",
                        "Nothing is blocked automatically or permanently; a human makes the final decision.", icon="🔍")

    if show:
        r = last[1]
        subtitle("Why did the AI flag this transaction?")
        put('<div class="panel">')
        shap_bars(r["drivers"])
        put('</div>')
        t = r["thresholds"]
        st.caption(f"Model prediction = risk score. Recommendation = policy on that score "
                   f"(MEDIUM ≥ {t['medium']:.2f}, HIGH ≥ {t['high']:.2f}). The score is a model output, "
                   f"not a calibrated probability, and it describes the transaction, not the person.")

    # ---- Cost Advisor
    st.write("")
    with st.expander("💰 Cost Advisor (supporting feature)"):
        st.caption("Prototype / assumption-based estimate on synthetic data. It is not the official upay fee schedule.")
        try:
            ids = api_get("/demo_customers", 30)
            cid = st.selectbox("Choose a customer", ids)
            s = api_get(f"/customer/{cid}/savings", 30)
            if s.get("found"):
                callout("info", "Personal tip", s["message_bn"], icon="💡", extra="bn")
                kpi_grid([kpi("Cash-outs / month", s["monthly_count"], "Average count"),
                          kpi("Estimated possible saving", f"৳{s['saving']}", "Per month, assumption-based", "b"),
                          kpi("Segment", esc(s["segment"]), "Behaviour group (K-Means)")], 200)
                st.caption(f"Assumptions: fee rate {s['fee_rate_assumed'] * 100:.1f}%, "
                           f"{s['shift_share_assumed'] * 100:.0f}% of cash-outs under ৳{s['small_limit']:,} "
                           f"moved to merchant payments. Average estimated saving across all customers: "
                           f"৳{s['avg_saving_all']}/month.")
        except Exception as e:
            api_error(e)

# ===================================================================== AGENT
with tab2:
    section("Agent view", "Agent Copilot — 7-day liquidity forecast",
            "See whether an agent's cash will cover the expected cash-out demand, and what to do about it.")
    try:
        ids = api_get("/demo_agents")
        aid = st.selectbox("Choose an agent (demo agents with the highest forecast pressure)", ids)
        r = api_get(f"/agent/{aid}/float")
        if r.get("found"):
            lvl = r["level"].upper()
            cash, peak = r["cash_on_hand"], r["peak_demand"]
            ratio = peak / cash if cash else 0
            col = LV_COLOR[lvl]

            put(f"""
            <div class="result {lvl}">
              <div class="res-txt">
                <span class="badge {lvl}">{ICON[lvl]} {lvl} LIQUIDITY RISK</span>
                <div class="res-h">Agent {esc(aid)} — peak demand is {ratio * 100:.0f}% of estimated cash</div>
                <div class="res-s">Peak expected on <b>{esc(r["peak_date"])}</b>. Warning starts at {WARN * 100:.0f}% of cash, shortage at {DANGER * 100:.0f}%.</div>
              </div>
            </div>
            """)
            st.write("")
            kpi_grid([kpi("Estimated cash on hand", taka(cash), "Assumed share of float capacity", "b"),
                      kpi("Expected demand (7-day peak)", taka(peak), f"Peak on {esc(r['peak_date'])}"),
                      kpi("Liquidity risk", lvl, "Demand ÷ cash on hand", lvl)], 210)

            smax = max(1.3, ratio * 1.1)
            put(f"""
            <div class="panel" style="margin-top:14px">
              <div class="panel-t">⛽ Cash coverage meter</div>
              <div class="meter">
                <div class="fill" style="width:{min(ratio / smax * 100, 100):.1f}%; background:{col}"></div>
                <div class="tick" style="left:{WARN / smax * 100:.1f}%"><em>80% warn</em></div>
                <div class="tick d" style="left:{DANGER / smax * 100:.1f}%"><em>100% cash</em></div>
              </div>
              <div class="note">Bar = forecast peak demand relative to estimated cash on hand.</div>
            </div>
            """)
            callout({"LOW": "ok", "MEDIUM": "warn", "HIGH": "bad"}[lvl], "Recommendation", r["recommendation"], icon="💡")
            callout("info", "বাংলা বার্তা", r["message_bn"], icon="💬", extra="bn")

            subtitle("Next 7 days at a glance")
            cards = ""
            for x in r["forecast"]:
                rt = x["demand"] / cash if cash else 0
                dl = "HIGH" if rt >= DANGER else "MEDIUM" if rt >= WARN else "LOW"
                dd = pd.to_datetime(x["date"])
                cards += (f'<div class="day {dl}"><div class="d">{dd.strftime("%a %d %b")}</div>'
                          f'<div class="v">{taka(x["demand"])}</div><div class="r">{rt * 100:.0f}% of cash</div></div>')
            put(f'<div class="days">{cards}</div>')

            h = pd.DataFrame({"date": pd.to_datetime([x["date"] for x in r["history"]]),
                              "demand": [x["demand"] for x in r["history"]], "series": "Actual (last 14 days)"})
            f = pd.DataFrame({"date": pd.to_datetime([x["date"] for x in r["forecast"]]),
                              "demand": [x["demand"] for x in r["forecast"]], "series": "Forecast (next 7 days)"})
            bridge = pd.concat([h.tail(1).assign(series="Forecast (next 7 days)"), f])
            full = pd.concat([h, bridge])
            xmin = full.date.min()
            lines = (alt.Chart(full).mark_line(point=alt.OverlayMarkDef(filled=True, size=55), strokeWidth=3)
                     .encode(x=alt.X("date:T", title=None, axis=alt.Axis(format="%d %b")),
                             y=alt.Y("demand:Q", title="Cash-out demand (৳ / day)", axis=alt.Axis(format="~s"),
                                     scale=alt.Scale(domain=[0, max(full.demand.max(), cash) * 1.15])),
                             color=alt.Color("series:N", scale=alt.Scale(
                                 domain=["Actual (last 14 days)", "Forecast (next 7 days)"], range=[B, "#F2B100"])),
                             strokeDash=alt.condition(alt.datum.series == "Forecast (next 7 days)",
                                                      alt.value([6, 4]), alt.value([0])),
                             tooltip=[alt.Tooltip("date:T", title="Date", format="%a %d %b"),
                                      alt.Tooltip("demand:Q", title="Demand ৳", format=",.0f"), "series"]))
            rule = alt.Chart(pd.DataFrame({"y": [cash]})).mark_rule(color=RED, strokeDash=[7, 4], strokeWidth=2).encode(y="y:Q")
            lbl = (alt.Chart(pd.DataFrame({"x": [xmin], "y": [cash], "t": ["Estimated cash on hand"]}))
                   .mark_text(align="left", dy=-8, dx=4, color=RED, fontWeight=700, font=FONT)
                   .encode(x="x:T", y="y:Q", text="t:N"))
            with chart_card("Demand history and forecast", "Actual vs forecast cash-out demand, against estimated cash on hand"):
                stretch(st.altair_chart, style_chart(lines + rule + lbl, 300))
            st.caption(f"Cash-out demand forecast from the LightGBM model on synthetic data. Cash on hand is an "
                       f"assumption ({r['cash_share_assumed'] * 100:.0f}% of the agent's float capacity), "
                       f"since the demo data has no real cash balances.")

            subtitle("Agent Copilot flow")
            stepper([("Historical agent data", "Daily cash-out history"), ("Forecast model", "LightGBM regressor"),
                     ("Future demand", "Next 7 days"), ("Liquidity risk", "Demand vs cash"),
                     ("Recommendation", "Top-up before the peak")], done=5)
    except Exception as e:
        api_error(e)

# ===================================================================== ANALYST
with tab3:
    section("Analyst view", "Analyst Console — human review of flagged transactions",
            "The AI supports the analyst; it does not decide.")
    b1, b2, _ = st.columns([1, 1.5, 3])
    b1.button("🔄 Refresh")
    if b2.button("➕ Load demo alerts"):
        try:
            for nm in list(SCENARIOS)[1:]:
                api_post("/score", SCENARIOS[nm])
        except Exception as e:
            api_error(e)
    try:
        cases = api_get("/cases", 30)
        resolved = sum(c["status"] in ("confirmed_safe", "held_for_review") for c in cases)
        kpi_grid([kpi("Total alerts", len(cases), "Medium + high risk"),
                  kpi("High risk", sum(c["risk_level"] == "HIGH" for c in cases), "Need human review", "HIGH"),
                  kpi("Pending review", sum(c["status"] == "pending" for c in cases), "Waiting for a decision", "MEDIUM"),
                  kpi("Resolved", resolved, "Confirmed safe or held", "LOW")], 170)
        subtitle("Review workflow")
        stepper([("AI flags", "Score ≥ policy threshold"), ("Analyst opens case", "Reasons + SHAP"),
                 ("Decision", "Confirm safe or hold"), ("Audit trail", "Status recorded")], done=4)
        if not cases:
            put('<div class="empty"><div class="e">📭</div><b>No alerts yet</b>'
                "Analyze a transaction in the Customer tab or click “Load demo alerts”.</div>")
        else:
            flt = st.radio("Show", ["Pending / high-risk first", "Pending only", "All"], horizontal=True)
            view = sorted(cases, key=lambda c: (c["status"] != "pending", -c["score"]))
            if flt == "Pending only":
                view = [c for c in view if c["status"] == "pending"]
            if view:
                subtitle("Alert queue")
                stretch(st.dataframe, pd.DataFrame([{
                    "Case ID": f"#{c['id']}", "Risk Score": f"{c['score'] * 100:.0f}%",
                    "Amount": f"৳{c['amount']:,.0f}", "Risk Level": f"{ICON[c['risk_level']]} {c['risk_level']}",
                    "Main Reasons": "; ".join(c["reasons"][:2]),
                    "Recommended Action": c["recommended_action"],
                    "Status": STATUS.get(c["status"], c["status"])} for c in view]), hide_index=True)

                subtitle("Open a case")
                by_id = {c["id"]: c for c in view}
                cid = st.selectbox("Case", list(by_id), format_func=lambda i: f"#{i} — {by_id[i]['risk_level']} — "
                                   f"৳{by_id[i]['amount']:,.0f} — {STATUS.get(by_id[i]['status'])}")
                c = by_id[cid]
                lv = c["risk_level"]
                d1, d2 = st.columns([1, 1], gap="large")
                with d1:
                    put(f"""
                    <div class="result {lv}">
                      {gauge_svg(c["score"], lv)}
                      <div class="res-txt"><span class="badge {lv}">{ICON[lv]} {lv}</span>
                      <div class="res-h">Case #{c["id"]}</div>
                      <div class="res-s">{esc(STATUS.get(c["status"], c["status"]))}</div></div>
                    </div>
                    <div class="rcpt" style="margin-top:12px">
                      <div class="rrow"><span>Recipient</span><b>{esc(c.get("recipient") or "n/a")}</b></div>
                      <div class="rrow"><span>Amount</span><b>{taka(c["amount"])}</b></div>
                      <div class="rrow"><span>Time</span><b>{c["tx"]["hour"]:02d}:00</b></div>
                      <div class="rrow"><span>Created</span><b>{esc(c["created"])}</b></div>
                    </div>
                    """)
                    subtitle("Reasons")
                    put('<div class="reasons">' + "".join(f'<div class="reason {lv}"><i></i><div>{esc(x)}</div></div>'
                                                          for x in c["reasons"]) + "</div>")
                    callout({"LOW": "ok", "MEDIUM": "warn", "HIGH": "bad"}[lv], "Recommended action", c["recommended_action"])
                with d2:
                    subtitle("Model explanation (SHAP)")
                    put('<div class="panel">')
                    shap_bars(c["drivers"])
                    put('</div>')
                if c["status"] == "pending":
                    a, b = st.columns(2)
                    if a.button("✅ Confirm Safe / Allow", key=f"a{cid}"):
                        api_post(f"/cases/{cid}/allow")
                        st.rerun()
                    if b.button("🚩 Hold / Escalate for Review", key=f"e{cid}"):
                        api_post(f"/cases/{cid}/escalate")
                        st.rerun()
                else:
                    callout("ok", "Decision recorded", STATUS.get(c["status"], c["status"]))
                st.caption("The AI supports the analyst; it does not decide. Holding a transaction is a temporary "
                           "step for review, not a permanent block or a judgement about the customer.")
    except Exception as e:
        api_error(e)

# ===================================================================== MODEL & RAI
with tab4:
    section("Under the hood", "Model performance (held-out test split, synthetic data)",
            "Plain-language meaning is shown under every number.")
    try:
        m = api_get("/metrics", 30)
        s = m.get("scamshield")
        if s:
            kpi_grid([kpi("Precision", f"{s['precision'] * 100:.1f}%", "Of all flags, how many were truly scam-like"),
                      kpi("Recall", f"{s['recall'] * 100:.1f}%", "Of all scam-like, how many we caught", "b"),
                      kpi("F1", f"{s['f1']:.3f}", "Balance of precision and recall"),
                      kpi("ROC-AUC", f"{s['roc_auc']:.3f}", "Separation of scam-like vs normal", "b"),
                      kpi("False alarm rate", f"{s['false_alarm_rate'] * 100:.2f}%", "Normal transactions wrongly flagged")], 190)
            st.caption(f"ScamShield (LightGBM) on {s['test_transactions']:,} synthetic test transactions "
                       f"({s['test_scam_transactions']:,} scam-like). Decision threshold {s['threshold']}.")
        else:
            st.info("ScamShield metrics not found. Run `python src/train_model.py` once to generate them.")
        a = m["agent_forecast"]
        subtitle("Agent forecast accuracy")
        k1, k2 = st.columns([1, 1.2], gap="large")
        with k1:
            kpi_grid([kpi("Model MAE", taka(a["mae_model"]), "Average daily error of our forecast", "b"),
                      kpi("Baseline MAE", taka(a["mae_baseline"]), "Error of a simple 7-day average"),
                      kpi("Improvement", f"{a['improvement_pct']}%", "Lower error than the baseline", "LOW")], 200)
        with k2:
            with chart_card("Forecast error (lower is better)", "Mean absolute error per agent-day, last 14 days"):
                df = pd.DataFrame({"model": ["7-day average (baseline)", "LightGBM forecast"],
                                   "mae": [a["mae_baseline"], a["mae_model"]]})
                ch = (alt.Chart(df).mark_bar(cornerRadiusEnd=8, size=30)
                      .encode(y=alt.Y("model:N", title=None, sort=None, axis=alt.Axis(labelLimit=200)),
                              x=alt.X("mae:Q", title="MAE (৳)", axis=alt.Axis(format="~s")),
                              color=alt.Color("model:N", legend=None, scale=alt.Scale(
                                  domain=["7-day average (baseline)", "LightGBM forecast"], range=["#BFD0EE", B])),
                              tooltip=["model", alt.Tooltip("mae:Q", format=",.0f")]))
                txt = ch.mark_text(align="left", dx=5, fontWeight=700, color=INK, font=FONT).encode(
                    text=alt.Text("mae:Q", format=",.0f"))
                stretch(st.altair_chart, style_chart(ch + txt, 150))
        st.caption("Agent forecast error measured on the last 14 days of synthetic data. "
                   "Results on synthetic data do not predict real-world performance.")
    except Exception as e:
        api_error(e)

    section("Trust by design", "🤝 Responsible AI", "Seven principles built into the product, not added afterwards.")
    rai = [("🔎", "Explainable", "Every score comes with SHAP feature contributions, not a hidden rule."),
           ("🧑‍⚖️", "Human oversight", "HIGH-risk cases go to an analyst, who confirms safe or holds for review."),
           ("🚫", "No autonomous consequences", "No automatic or permanent blocking of accounts or transactions."),
           ("🧭", "Prediction ≠ recommendation", "The model outputs a score; the action is a separate, transparent policy."),
           ("🤲", "Respectful wording", "We describe a transaction as high-risk or needing verification, never a person as fraudulent."),
           ("🔐", "Data minimisation", "Synthetic/demo data only; no real customer or upay data, no sensitive personal attributes in the model."),
           ("⚙️", "Works without an LLM", "All risk decisions come from the ML model and simple rules.")]
    put('<div class="grid" style="--min:250px">' + "".join(
        f'<div class="card"><div class="ic {"b" if i % 2 else ""}">{ic}</div><div class="card-t">{esc(t)}</div><p>{esc(d)}</p></div>'
        for i, (ic, t, d) in enumerate(rai)) + "</div>")
    put('<div class="foot"><b>upay সুরক্ষা+</b> · Safe for Customers. Smarter for Agents. · Prototype on synthetic data.</div>')
