import json
import os
import html
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
import streamlit as st

from detector import (
    STATUS_COLORS,
    analyze_text,
    build_reports,
    check_bifrost,
    get_settings,
    summarize,
)
from security import ROLE_ADMIN, SecurityConfig, concurrency_gate, limiter, role_for_token


load_dotenv(dotenv_path=Path(__file__).with_name(".env"), override=True)

st.set_page_config(page_title="StaleBot · Stale-Answer Detector", page_icon="🛡️", layout="wide", initial_sidebar_state="expanded")

PRESETS = {
    "Outdated Technology Stack": "Python 3.9 is the latest stable release of Python. React 17 is the latest major release of React. Node.js 18 is currently an Active LTS release.",
    "Historic AI API Pricing": "GPT-4 Turbo is the latest model in the GPT-4 family. GPT-4 Turbo API pricing is $10 per million input tokens and $30 per million output tokens.",
    "Mixed Claims to Verify (2026)": "Python 3.14 was released in 2025. React 17 is the latest major release of React. Node.js 24 is an Active LTS release. GPT-4 Turbo API pricing is $10 per million input tokens and $30 per million output tokens.",
    "Custom Analysis": "",
}
PRESET_NOTES = {
    "Outdated Technology Stack": "Version and lifecycle claims; verify each one live.",
    "Historic AI API Pricing": "Historical claims, not assumed current.",
    "Mixed Claims to Verify (2026)": "Mixed candidates; none are pre-verified.",
    "Custom Analysis": "Enter your own text.",
}
st.session_state.setdefault("theme", "Dark")
if st.session_state["theme"] not in {"Dark", "Light"}:
    st.session_state["theme"] = "Dark"


def set_theme(theme_name):
    st.session_state["theme"] = theme_name


def set_active_view(view_name):
    st.session_state["active_view"] = view_name


ICONS = {
    "shield": '<path d="M12 3 19 6v5c0 4.5-2.8 7.6-7 10-4.2-2.4-7-5.5-7-10V6l7-3Z"/><path d="m9 12 2 2 4-4"/>',
    "dashboard": '<rect x="3" y="3" width="8" height="8" rx="2"/><rect x="13" y="3" width="8" height="5" rx="2"/><rect x="13" y="10" width="8" height="11" rx="2"/><rect x="3" y="13" width="8" height="8" rx="2"/>',
    "analytics": '<path d="M4 19V5"/><path d="M4 19h17"/><rect x="7" y="11" width="3" height="5" rx="1"/><rect x="13" y="7" width="3" height="9" rx="1"/><rect x="19" y="4" width="2" height="12" rx="1"/>',
    "presets": '<path d="m12 3 1.4 5.6L19 10l-5.6 1.4L12 17l-1.4-5.6L5 10l5.6-1.4L12 3Z"/><path d="m19 15 .7 2.3L22 18l-2.3.7L19 21l-.7-2.3L16 18l2.3-.7L19 15Z"/>',
    "bolt": '<path d="m13 2-3 9h7L9 22l3-9H5l8-11Z"/>',
    "model": '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M9 9h6v6H9zM9 1v3m6-3v3M9 20v3m6-3v3M1 9h3m-3 6h3m16-6h3m-3 6h3"/>',
    "search": '<path d="M10.5 18a7.5 7.5 0 1 1 0-15 7.5 7.5 0 0 1 0 15Z"/><path d="m16 16 5 5"/><path d="m10.5 7 .8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8.8-2.2Z"/>',
    "wand": '<path d="m15 4 5 5M3 21l12-12M6 3l.8 2.2L9 6l-2.2.8L6 9l-.8-2.2L3 6l2.2-.8L6 3Zm12 10 .8 2.2L21 16l-2.2.8L18 19l-.8-2.2L15 16l2.2-.8L18 13Z"/>',
}


def icon_svg(name):
    return f'<svg viewBox="0 0 24 24" aria-hidden="true">{ICONS[name]}</svg>'

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root{--page:#070B18;--sidebar:#0B1024;--panel:#10172B;--raised:#151D35;--blue:#2563EB;--electric:#3B82F6;--violet:#7C3AED;--cyan:#22D3EE;--green:#10B981;--rose:#EF4444;--amber:#F59E0B;--text:#F8FAFC;--muted:#94A3B8;--line:rgba(99,130,255,.18)}
html,body,[class*="css"]{font-family:'Inter',sans-serif;letter-spacing:0}
[data-testid="stAppViewContainer"],[data-testid="stApp"]{color:var(--text)!important;background:radial-gradient(760px 420px at 82% -8%,rgba(37,99,235,.16),transparent 65%),radial-gradient(620px 360px at 50% 12%,rgba(124,58,237,.07),transparent 68%),var(--page)!important}
[data-testid="stHeader"]{background:transparent}[data-testid="stSidebar"]{min-width:286px;max-width:286px;background:var(--sidebar);border-right:1px solid var(--line)}
[data-testid="stMainMenu"]{display:none!important}
.block-container{max-width:1420px;padding-top:1.8rem;padding-bottom:4rem}h1,h2,h3{font-family:'Inter',sans-serif;letter-spacing:0}
h1{font-size:2.05rem!important;line-height:1.2!important;font-weight:800!important}h2{font-size:1.22rem!important;font-weight:700!important}p,label{color:var(--muted)}
.hero{padding:.3rem 0 1.2rem}.hero-kicker,.section-kicker{color:#9BBEFF;font-size:.73rem;font-weight:700;text-transform:uppercase;letter-spacing:1px}.hero h1{margin:.55rem 0 .45rem;color:var(--text)}.hero-copy{max-width:780px;color:var(--muted);font-size:1rem;line-height:1.65}
.status-chip{display:flex;align-items:center;gap:.55rem;min-height:43px;padding:.6rem .75rem;border:1px solid var(--line);border-radius:10px;background:rgba(21,30,48,.76);color:var(--muted);font-size:.78rem}.status-dot{width:7px;height:7px;border-radius:50%;flex:0 0 7px;background:#64748B}.status-dot.ok{background:var(--green)}.status-dot.warn{background:var(--amber)}.status-dot.bad{background:var(--rose)}.status-chip strong{color:var(--text);font-weight:600}
.kpi-card{height:128px;padding:1rem;border:1px solid var(--line);border-radius:12px;background:linear-gradient(145deg,rgba(25,36,58,.92),rgba(21,30,48,.88));box-shadow:0 12px 30px rgba(0,0,0,.14);transition:border-color .18s ease,transform .18s ease}.kpi-card:hover{border-color:rgba(96,165,250,.38);transform:translateY(-2px)}.kpi-label{color:var(--muted);font-size:.78rem;font-weight:600}.kpi-value{margin-top:.5rem;color:var(--text);font-family:'Space Grotesk',sans-serif;font-size:1.9rem;font-weight:700}.kpi-meta{margin-top:.4rem;color:#8292AA;font-size:.72rem}
.section-heading{display:flex;align-items:end;justify-content:space-between;gap:1rem;margin:1.7rem 0 .8rem}.section-heading h2{margin:0;color:var(--text)}.status-badge{display:inline-block;padding:.28rem .58rem;border-radius:999px;font-size:.68rem;font-weight:700;letter-spacing:.45px}.status-fresh{color:#9AF0D1;background:rgba(52,211,153,.12);border:1px solid rgba(52,211,153,.25)}.status-stale{color:#FFB1BE;background:rgba(251,113,133,.12);border:1px solid rgba(251,113,133,.25)}.status-unverified{color:#FCD58A;background:rgba(245,158,11,.12);border:1px solid rgba(245,158,11,.25)}
.evidence-label{margin:.8rem 0 .2rem;color:#CBD5E1;font-size:.74rem;font-weight:700;text-transform:uppercase;letter-spacing:.45px}.empty-state{padding:1.4rem;border:1px dashed rgba(148,163,184,.25);border-radius:12px;background:rgba(21,30,48,.45)}.empty-mark{width:34px;height:34px;display:grid;place-items:center;margin-bottom:.8rem;border-radius:9px;color:#A8C8FF;background:rgba(59,130,246,.13)}
hr{border-color:var(--line)!important}.stButton>button,[data-testid="stFormSubmitButton"]>button{min-height:2.55rem;border:1px solid var(--line);border-radius:9px;color:var(--text);background:var(--raised);font-weight:650;transition:filter .16s ease,transform .16s ease,background .16s ease}.stButton>button:hover,[data-testid="stFormSubmitButton"]>button:hover{filter:brightness(1.12);transform:translateY(-1px)}
button[kind*="primary"],button[data-testid*="primary"]{color:#FFFFFF!important;background:linear-gradient(100deg,var(--blue),var(--violet))!important}
button[kind*="primary"] *,button[data-testid*="primary"] *{color:#FFFFFF!important}
.st-key-theme_dark_button button[kind="primary"],.st-key-theme_light_button button[kind="primary"]{color:#FFFFFF!important;background:linear-gradient(100deg,#2563EB,#3B82F6)!important;border-color:rgba(96,165,250,.55)!important}
.st-key-theme_dark_button button[kind="secondary"],.st-key-theme_light_button button[kind="secondary"]{color:var(--muted)!important;background:var(--panel)!important;border-color:var(--line)!important}
[data-testid="stTextArea"] textarea,[data-testid="stSelectbox"] div[data-baseweb="select"]>div{color:var(--text);background:var(--panel);border-color:var(--line);border-radius:9px}[data-testid="stVerticalBlockBorderWrapper"]{border-color:var(--line)!important;border-radius:14px!important;background:var(--panel)}[data-testid="stExpander"]{border-color:var(--line);border-radius:9px;background:var(--panel)}[data-testid="stProgressBar"]>div>div{background:linear-gradient(90deg,var(--blue),var(--violet))}
[data-testid="stAlert"]{box-sizing:border-box!important;height:auto!important;min-height:0!important;max-height:none!important;overflow:visible!important;padding:16px!important;border:1px solid var(--line)!important;border-radius:12px!important;color:var(--text)!important;background:var(--raised)!important}
[data-testid="stAlert"]>div,[data-testid="stAlert"] [data-testid="stMarkdownContainer"]{box-sizing:border-box!important;height:auto!important;min-height:0!important;max-height:none!important;overflow:visible!important;color:var(--text)!important}
[data-testid="stAlert"] p{margin:0!important;color:inherit!important;line-height:1.55!important;white-space:normal!important;overflow-wrap:anywhere}
.brand-lockup{display:flex;align-items:center;gap:11px;margin:0 0 1.5rem}.brand-mark{width:38px;height:38px;display:grid;place-items:center;border:1px solid rgba(59,130,246,.32);border-radius:12px;color:#93C5FD;background:linear-gradient(145deg,rgba(37,99,235,.24),rgba(124,58,237,.16));box-shadow:0 0 22px rgba(37,99,235,.13)}.brand-mark svg,.nav-item svg,.hero-art svg,.status-icon svg,.input-title svg{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}.brand-name{color:var(--text);font-size:.91rem;font-weight:750}.brand-tagline{margin-top:2px;color:var(--muted);font-size:.68rem}
.sidebar-label{margin:1.25rem 0 .55rem;color:#64748B;font-size:.67rem;font-weight:700;text-transform:uppercase;letter-spacing:1px}.nav-item{display:flex;align-items:center;gap:11px;padding:.7rem .78rem;border:1px solid transparent;border-radius:9px;color:var(--muted);font-size:.82rem;font-weight:600}.nav-item.active{color:#fff;background:linear-gradient(105deg,rgba(37,99,235,.95),rgba(124,58,237,.88));box-shadow:0 8px 24px rgba(37,99,235,.2)}
.step-row{display:flex;gap:.7rem;margin:.75rem 0;padding-bottom:.7rem;border-bottom:1px solid var(--line)}.step-row:last-child{border-bottom:0}.step-num{width:27px;height:27px;display:grid;place-items:center;flex:0 0 27px;border:1px solid rgba(59,130,246,.26);border-radius:8px;color:#93C5FD;background:rgba(37,99,235,.1);font-size:.68rem;font-weight:750}.step-copy{color:var(--muted);font-size:.72rem;line-height:1.5}.step-copy strong{display:block;margin-bottom:2px;color:#E2E8F0;font-size:.75rem}
.st-key-theme_dark_button button[kind="primary"],.st-key-theme_light_button button[kind="primary"]{color:#fff!important;background:linear-gradient(100deg,var(--blue),var(--violet))!important;border-color:rgba(99,130,255,.48)!important}
.st-key-theme_dark_button button[kind="secondary"],.st-key-theme_light_button button[kind="secondary"]{color:var(--muted)!important;background:var(--panel)!important;border-color:var(--line)!important}
.st-key-nav_dashboard button[kind="primary"],.st-key-nav_analytics button[kind="primary"],.st-key-nav_presets button[kind="primary"]{color:#fff!important;background:linear-gradient(105deg,rgba(37,99,235,.95),rgba(124,58,237,.88))!important;border-color:rgba(99,130,255,.28)!important;box-shadow:0 8px 24px rgba(37,99,235,.2)}
.hero-shell{position:relative;overflow:hidden;padding:1.3rem 1.45rem;border:1px solid var(--line);border-radius:16px;background:linear-gradient(115deg,rgba(16,23,43,.96),rgba(21,29,53,.8));box-shadow:0 18px 48px rgba(0,0,0,.18)}.hero-shell:after{position:absolute;right:-60px;top:-150px;width:340px;height:300px;border-radius:50%;background:radial-gradient(circle,rgba(59,130,246,.19),transparent 68%);content:"";pointer-events:none}.hero-title{margin:.45rem 0;color:var(--text);font-size:2rem;font-weight:800;line-height:1.15}.hero-title span{color:#93C5FD;background:linear-gradient(90deg,#60A5FA,#A78BFA,#22D3EE);background-clip:text;-webkit-text-fill-color:transparent}.hero-copy{max-width:690px;color:var(--muted);font-size:.87rem;line-height:1.65}.hero-art{position:relative;z-index:1;width:90px;height:90px;display:grid;place-items:center;margin:auto;border:1px solid rgba(59,130,246,.3);border-radius:26px;color:#BFDBFE;background:linear-gradient(145deg,rgba(37,99,235,.25),rgba(124,58,237,.16));box-shadow:0 0 48px rgba(37,99,235,.18)}.hero-art svg{width:46px;height:46px}
.status-card{display:flex;align-items:center;gap:12px;min-height:78px;padding:.9rem 1rem;border:1px solid var(--line);border-radius:12px;background:linear-gradient(145deg,var(--panel),rgba(21,29,53,.76));transition:transform .18s ease,border-color .18s ease}.status-card:hover{transform:translateY(-2px);border-color:rgba(59,130,246,.38)}.status-icon{width:38px;height:38px;display:grid;place-items:center;flex:0 0 38px;border:1px solid var(--line);border-radius:11px;color:#93C5FD;background:rgba(59,130,246,.1)}.status-title{color:var(--muted);font-size:.68rem}.status-value{overflow:hidden;margin-top:3px;color:var(--text);font-size:.78rem;font-weight:650;text-overflow:ellipsis;white-space:nowrap}.status-led{width:7px;height:7px;display:inline-block;margin-right:6px;border-radius:50%;background:var(--green)}
.analysis-shell{padding:1.15rem 1.2rem;border:1px solid rgba(99,130,255,.22);border-radius:15px;background:linear-gradient(150deg,rgba(16,23,43,.96),rgba(21,29,53,.88));box-shadow:0 18px 42px rgba(0,0,0,.18)}.input-title{display:flex;align-items:center;gap:9px;color:var(--text);font-size:.96rem;font-weight:700}.input-title svg{color:#93C5FD}.analysis-shell [data-testid="stTextArea"] textarea{min-height:150px;padding:14px 15px;border-color:rgba(59,130,246,.35);background:rgba(7,11,24,.55);font-size:.88rem;line-height:1.6}.analysis-shell [data-testid="stTextArea"] textarea:focus{border-color:#3B82F6;box-shadow:0 0 0 2px rgba(59,130,246,.16)}.analysis-shell [data-testid="stFormSubmitButton"] button{min-height:47px;border:0;background:linear-gradient(100deg,#2563EB,#7C3AED,#0891B2);box-shadow:0 8px 22px rgba(37,99,235,.19);font-weight:700}.section-title{display:flex;align-items:center;gap:8px;margin:1.5rem 0 .7rem;color:var(--text);font-size:.96rem;font-weight:700}.section-title svg{width:17px;height:17px;fill:none;stroke:#60A5FA;stroke-width:1.8}
.empty-state{display:flex;align-items:center;gap:15px;padding:1.15rem 1.25rem;border-style:solid}.empty-wave{width:46px;height:46px;display:grid;place-items:center;flex:0 0 46px;border:1px solid rgba(59,130,246,.24);border-radius:14px;color:#93C5FD;background:rgba(37,99,235,.1)}.empty-copy{color:var(--muted);font-size:.8rem;line-height:1.55}.empty-copy strong{display:block;margin-bottom:3px;color:var(--text);font-size:.88rem}
.st-key-nav_dashboard button,.st-key-nav_analytics button,.st-key-nav_presets button{width:100%;text-align:left;border-radius:9px}.st-key-nav_dashboard button[kind="secondary"],.st-key-nav_analytics button[kind="secondary"],.st-key-nav_presets button[kind="secondary"]{color:var(--muted)!important;background:transparent!important;border-color:transparent!important;box-shadow:none!important}
.nav-icon{width:34px;height:34px;display:grid;place-items:center;margin:auto;color:var(--muted);border-radius:9px}.nav-icon svg{width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}.nav-icon.active{color:#fff}
.st-key-navrow_dashboard_active,.st-key-navrow_analytics_active,.st-key-navrow_presets_active{border:1px solid rgba(99,130,255,.22);border-radius:10px;background:linear-gradient(100deg,rgba(37,99,235,.16),rgba(124,58,237,.11));box-shadow:0 6px 20px rgba(37,99,235,.08)}
.st-key-analysis_card{margin:.85rem 0 1.1rem!important;padding:1.05rem 1.15rem!important;border:1px solid rgba(99,130,255,.24)!important;border-radius:15px!important;background:linear-gradient(145deg,var(--panel),var(--raised))!important;box-shadow:0 18px 45px rgba(0,0,0,.14)}
.input-hint{margin:.3rem 0 .85rem;color:var(--muted);font-size:.76rem}.live-flag{display:flex;justify-content:flex-end;align-items:center;gap:7px;color:var(--muted);font-size:.64rem;font-weight:700;letter-spacing:.6px}.live-flag span{width:6px;height:6px;border-radius:50%;background:var(--green);box-shadow:0 0 10px rgba(16,185,129,.45)}
.status-led.ok{background:var(--green);box-shadow:0 0 9px rgba(16,185,129,.4)}.status-led.warn{background:var(--amber)}.status-led.bad{background:var(--rose)}
.st-key-analysis_card [data-testid="stTextArea"] textarea{background:rgba(7,11,24,.55)!important;color:var(--text)!important}
@media(max-width:760px){[data-testid="stSidebar"]{min-width:0;max-width:none}.block-container{padding:1rem .85rem 2.5rem}h1{font-size:1.7rem!important}.hero-shell{padding:1rem}.hero-title{font-size:1.65rem}.hero-art{width:64px;height:64px;border-radius:19px}.hero-art svg{width:34px;height:34px}.status-card{min-height:72px;padding:.65rem}.status-value{font-size:.68rem}.kpi-card{height:116px}}
</style>
""", unsafe_allow_html=True)

if st.session_state["theme"] == "Light":
    st.markdown("""
    <style>
    :root{--page:#F8FAFC;--sidebar:#FFFFFF;--panel:#FFFFFF;--raised:#F1F5F9;--text:#0F172A;--muted:#64748B;--line:#E2E8F0}
    [data-testid="stAppViewContainer"],[data-testid="stApp"]{color:var(--text)!important;background:var(--page)!important}
    body,[data-testid="stSidebar"],[data-testid="stSidebar"]>div:first-child{color:var(--text)!important;background:var(--sidebar)!important}
    h1,h2,h3,.hero h1,.section-heading h2{color:var(--text)}
    p,label,.hero-copy,.kpi-label,.status-chip,.step-copy,.step-copy strong{color:var(--muted)}
    .hero-kicker,.section-kicker,.step-num{color:#1D4ED8}
    .status-fresh{color:#047857;background:rgba(52,211,153,.1);border-color:rgba(4,120,87,.24)}
    .status-stale{color:#BE123C;background:rgba(251,113,133,.1);border-color:rgba(190,18,60,.22)}
    .status-unverified{color:#B45309;background:rgba(245,158,11,.1);border-color:rgba(180,83,9,.22)}
    [data-testid="stAlert"]{height:auto!important;min-height:0!important;max-height:none!important;overflow:visible!important;padding:16px!important;color:#0F172A!important;background:#FFFFFF!important;border-color:#E2E8F0!important}
    [data-testid="stAlert"]>div,[data-testid="stAlert"] [data-testid="stMarkdownContainer"],[data-testid="stAlert"] p{height:auto!important;min-height:0!important;max-height:none!important;overflow:visible!important;color:#0F172A!important}
    .status-chip,.status-card,.kpi-card,.empty-state,.hero-shell,.analysis-shell,.st-key-analysis_card,[data-testid="stVerticalBlockBorderWrapper"],[data-testid="stExpander"]{background:#FFFFFF}
    .kpi-card{box-shadow:0 10px 24px rgba(15,23,42,.05)}
    .kpi-meta{color:#64748B}
    .status-chip strong,.step-copy strong{color:var(--text)}
    .evidence-label,.sidebar-label{color:#334155}
    [data-testid="stTextArea"] textarea,[data-testid="stSelectbox"] div[data-baseweb="select"]>div,.st-key-analysis_card [data-testid="stTextArea"] textarea{color:var(--text)!important;background:#FFFFFF!important;border-color:var(--line)}
    .stButton>button{color:var(--text);background:#FFFFFF;border-color:var(--line)}
    button[kind*="primary"],button[data-testid*="primary"]{color:#FFFFFF!important;background:linear-gradient(100deg,#2563EB,#7C3AED)!important}
    button[kind*="primary"] *,button[data-testid*="primary"] *{color:#FFFFFF!important}
    .status-value,.brand-name,.hero-title,.input-title,.section-title,.empty-copy strong{color:var(--text)}
    .status-card{background:#FFFFFF}.status-icon{color:#2563EB;background:#EFF6FF;border-color:#DBEAFE}
    .st-key-analysis_card{border-color:#CBD5E1!important;box-shadow:0 14px 36px rgba(15,23,42,.06)}
    .st-key-analysis_card [data-testid="stFormSubmitButton"] button{color:#FFFFFF;background:linear-gradient(100deg,#2563EB,#7C3AED,#0891B2)}
    .st-key-navrow_dashboard_active,.st-key-navrow_analytics_active,.st-key-navrow_presets_active{background:linear-gradient(100deg,rgba(37,99,235,.11),rgba(124,58,237,.08));border-color:#DBEAFE}
    [data-testid="stExpander"]{border-color:var(--line)}
    </style>
    """, unsafe_allow_html=True)

SAMPLE_TEXT = PRESETS["Outdated Technology Stack"]



def render_status_card(label, value, state, icon_name):
    state_class = "ok" if state == "ok" else "warn" if state == "warn" else "bad"
    st.markdown(
        f'<div class="status-card"><div class="status-icon">{icon_svg(icon_name)}</div>'
        f'<div style="min-width:0;flex:1"><div class="status-title">{html.escape(label)}</div>'
        f'<div class="status-value"><span class="status-led {state_class}"></span>'
        f'{html.escape(value)}</div></div></div>',
        unsafe_allow_html=True,
    )


def render_nav_item(label, key, icon_name):
    active = st.session_state["active_view"] == label
    with st.container(key=f"navrow_{key}_{'active' if active else 'idle'}"):
        columns = st.columns([0.32, 1], gap="small", vertical_alignment="center")
        with columns[0]:
            st.markdown(
                f'<div class="nav-icon {"active" if active else ""}">{icon_svg(icon_name)}</div>',
                unsafe_allow_html=True,
            )
        with columns[1]:
            st.button(
                label,
                key=f"nav_{key}",
                type="primary" if active else "secondary",
                on_click=set_active_view,
                args=(label,),
                use_container_width=True,
            )


def render_kpi(label, value, note, accent):
    st.markdown(
        f'<div class="kpi-card" style="border-top:2px solid {accent}">'
        f'<div class="kpi-label">{html.escape(label)}</div>'
        f'<div class="kpi-value">{html.escape(str(value))}</div>'
        f'<div class="kpi-meta">{html.escape(note)}</div></div>',
        unsafe_allow_html=True,
    )


def render_sources(sources):
    with st.expander(f"Live sources · {len(sources)}", expanded=False):
        if not sources:
            st.caption("No source evidence was returned for this claim.")
        for source in sources:
            url = source.get("url", "")
            domain = urlparse(url).hostname if url else None
            columns = st.columns([4, 1])
            with columns[0]:
                st.write(f"**{source.get('title') or 'Untitled source'}**")
                if domain:
                    date = source.get("published_date")
                    st.caption(domain + (f" · {date}" if date else ""))
            with columns[1]:
                if urlparse(url).scheme in {"http", "https"} and domain:
                    st.link_button("Open source", url, use_container_width=True)
            st.write(source.get("content") or "No supporting excerpt was provided by the search result.")
            st.divider()


def render_downloads(analysis):
    st.markdown('<div class="section-heading"><h2>Export audit</h2></div>', unsafe_allow_html=True)
    full_report, corrected_summary = build_reports(analysis)
    downloads = st.columns(2)
    with downloads[0]:
        st.download_button(
            "Download full audit report", full_report, "stale-answer-audit.md",
            "text/markdown", use_container_width=True,
        )
    with downloads[1]:
        st.download_button(
            "Download corrected summary", corrected_summary, "corrected-summary.md",
            "text/markdown", use_container_width=True,
        )


def render_analysis(analysis):
    results = analysis["results"]
    if analysis.get("claims_truncated"):
        st.info(
            f"{analysis['claims_truncated']} more claim(s) were found but not checked: each check is "
            f"limited to {len(results)} claims. Split long texts into smaller parts."
        )
    if not results:
        st.markdown(
            '<div class="empty-state"><div class="empty-mark">i</div>'
            "<strong>No verifiable claims found</strong><br>"
            "Bifrost did not identify a factual claim to check in this text.</div>",
            unsafe_allow_html=True,
        )
        render_downloads(analysis)
        return

    counts, score, trust = summarize(results)
    st.markdown('<div class="section-heading"><h2>Audit overview</h2></div>', unsafe_allow_html=True)
    cards = st.columns(4, gap="small")
    values = [
        ("Overall freshness", f"{score}/100", trust, "#3B82F6"),
        ("Claims audited", len(results), "Extracted and analyzed", "#8B5CF6"),
        ("Stale claims", counts["Stale"], "Contradicted by newer evidence", "#FB7185"),
        ("Verified fresh", counts["Fresh"], "Supported by current evidence", "#34D399"),
    ]
    for column, args in zip(cards, values):
        with column:
            render_kpi(*args)
    st.markdown('<div class="section-heading"><h2>Reliability</h2></div>', unsafe_allow_html=True)
    st.progress(score, text=f"{trust} · {score} / 100")
    st.caption(
        "Rounded mean of claim scores. Unverified claims receive a neutral 41-69 score and "
        "are tracked separately; missing evidence is not treated as stale."
    )
    st.markdown('<div class="section-heading"><h2>Executive summary</h2></div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.write(
            f"This audit reviewed **{len(results)} claims**: **{counts['Fresh']} fresh**, "
            f"**{counts['Stale']} stale**, and **{counts['Unverified']} unverified**. "
            "Unverified means evidence was insufficient or conflicting; it does not mean the claim is false."
        )
        if analysis["search_failures"]:
            st.warning(f"{analysis['search_failures']} live search request(s) failed. Those claims remain unverified, not stale.")

    st.markdown('<div class="section-heading"><h2>Claim findings</h2></div>', unsafe_allow_html=True)
    for index, item in enumerate(results, start=1):
        with st.container(border=True):
            top = st.columns([4, 1])
            with top[0]:
                st.caption(f"CLAIM {index:02d}")
                st.markdown(f"**{item['claim']}**")
            with top[1]:
                status_class = item["status"].lower()
                st.markdown(
                    f'<div style="text-align:right"><span class="status-badge status-{status_class}">'
                    f'{html.escape(item["status"].upper())}</span><br>'
                    f'<span style="color:#F8FAFC;font-size:1.25rem;font-weight:700">{item["freshness_score"]}'
                    '<span style="color:#94A3B8;font-size:.75rem"> / 100</span></span></div>',
                    unsafe_allow_html=True,
                )
            st.markdown('<div class="evidence-label">Current information</div>', unsafe_allow_html=True)
            st.write(item["updated_fact"])
            columns = st.columns(2)
            with columns[0]:
                st.markdown('<div class="evidence-label">Assessment</div>', unsafe_allow_html=True)
                st.write(item["explanation"])
            with columns[1]:
                st.markdown('<div class="evidence-label">Evidence analysis</div>', unsafe_allow_html=True)
                st.write(item["evidence_analysis"])
            st.markdown('<div class="evidence-label">Recommended correction</div>', unsafe_allow_html=True)
            st.write(item["recommended_correction"])
            render_sources(item["sources"])

    render_downloads(analysis)


security_cfg = SecurityConfig.from_env()


def visitor_key():
    """Caller IP when Streamlit exposes it, otherwise a per-browser-session id."""
    ip = getattr(st.context, "ip_address", None)
    if ip:
        return ip
    st.session_state.setdefault("visitor_id", os.urandom(8).hex())
    return "session:" + st.session_state["visitor_id"]


# Private deployments (ACCESS_TOKEN set) ask for a key before showing anything.
if "access_role" not in st.session_state:
    st.session_state["access_role"] = role_for_token(security_cfg, "")
if st.session_state["access_role"] is None:
    st.markdown('<div class="hero-shell"><div class="hero-kicker">PRIVATE WORKSPACE</div>'
                '<div class="hero-title">Stale<span>Bot</span></div>'
                '<div class="hero-copy">Enter the access key you were given to continue.</div></div>',
                unsafe_allow_html=True)
    with st.form("access_form"):
        supplied = st.text_input("Access key", type="password")
        unlock = st.form_submit_button("Unlock", type="primary")
    if unlock:
        wait = limiter.hit([(f"st-login:{visitor_key()}", 10, 600)])
        role = None if wait else role_for_token(security_cfg, supplied.strip())
        if wait:
            st.error(f"Too many attempts. Try again in {wait}s.")
        elif role:
            st.session_state["access_role"] = role
            st.rerun()
        else:
            st.error("That key was not accepted.")
    st.stop()

st.session_state.setdefault("answer_text", SAMPLE_TEXT)
st.session_state.setdefault("selected_preset", "Outdated Technology Stack")
st.session_state.setdefault("analysis", None)
st.session_state.setdefault("active_view", "Dashboard")
settings = get_settings()
# The gateway check is a (small) paid model call, so it runs only on request, not on page load.
st.session_state.setdefault("bifrost_probe", {"state": "unchecked", "model_available": None})

with st.sidebar:
    st.markdown(
        '<div class="brand-lockup"><div class="brand-mark">'
        f'{icon_svg("shield")}</div><div><div class="brand-name">StaleBot</div>'
        '<div class="brand-tagline">Detect. Verify. Trust.</div></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="sidebar-label">Workspace</div>', unsafe_allow_html=True)
    render_nav_item("Dashboard", "dashboard", "dashboard")
    render_nav_item("Analytics", "analytics", "analytics")
    render_nav_item("Quick Presets", "presets", "presets")
    st.divider()
    st.markdown('<div class="sidebar-label">Theme</div>', unsafe_allow_html=True)
    theme_buttons = st.columns(2, gap="small")
    with theme_buttons[0]:
        st.button(
            "Dark",
            key="theme_dark_button",
            type="primary" if st.session_state["theme"] == "Dark" else "secondary",
            on_click=set_theme,
            args=("Dark",),
            use_container_width=True,
        )
    with theme_buttons[1]:
        st.button(
            "Light",
            key="theme_light_button",
            type="primary" if st.session_state["theme"] == "Light" else "secondary",
            on_click=set_theme,
            args=("Light",),
            use_container_width=True,
        )
    st.markdown('<div class="sidebar-label">Quick presets</div>', unsafe_allow_html=True)
    selected = st.selectbox(
        "Choose a starting point", list(PRESETS), key="selected_preset", label_visibility="collapsed"
    )
    st.caption(PRESET_NOTES[selected])
    if st.button("Load selected preset", type="primary", use_container_width=True):
        st.session_state["answer_text"] = PRESETS[selected]
        st.session_state["analysis"] = None
        st.session_state.pop("analysis_error", None)
    st.divider()
    st.markdown('<div class="sidebar-label">Gateway</div>', unsafe_allow_html=True)
    if st.button("Check gateway connection", use_container_width=True):
        wait = limiter.hit([(f"st-probe:{visitor_key()}", 1, max(1, security_cfg.probe_cooldown_s))])
        if wait and st.session_state["access_role"] != ROLE_ADMIN:
            st.toast(f"Checked recently. Try again in {wait}s.")
        else:
            with st.spinner("Checking gateway…"):
                st.session_state["bifrost_probe"] = check_bifrost(settings)
            st.rerun()
    st.divider()
    st.markdown('<div class="sidebar-label">How it works</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="step-row"><span class="step-num">01</span><div class="step-copy"><strong>Claim detection</strong>Extract independently verifiable facts.</div></div>'
        '<div class="step-row"><span class="step-num">02</span><div class="step-copy"><strong>Live web verification</strong>Verify claims against current web sources.</div></div>'
        '<div class="step-row"><span class="step-num">03</span><div class="step-copy"><strong>Freshness scoring</strong>Evaluate evidence, recency, and confidence.</div></div>',
        unsafe_allow_html=True,
    )

hero_columns = st.columns([5, 1.15], vertical_alignment="center")
with hero_columns[0]:
    st.markdown(
        '<div class="hero-shell"><div class="hero-kicker">REAL-TIME CLAIM INTELLIGENCE</div>'
        '<div class="hero-title">Stale<span>Bot</span></div>'
        '<div class="hero-copy">An intelligent verification platform that detects outdated AI claims using real-time web intelligence.</div></div>',
        unsafe_allow_html=True,
    )
with hero_columns[1]:
    st.markdown(f'<div class="hero-art">{icon_svg("shield")}</div>', unsafe_allow_html=True)

status_columns = st.columns(3, gap="small")
probe = st.session_state["bifrost_probe"]
gateway_value = {
    "connected": "Connected", "unavailable": "Unavailable", "missing": "Not configured",
}.get(probe["state"], "Not checked yet")
gateway_state = {"connected": "ok", "unavailable": "bad"}.get(probe["state"], "warn")
with status_columns[0]:
    render_status_card("Bifrost Gateway", gateway_value, gateway_state, "bolt")
if probe["model_available"] is True:
    model_value, model_state = settings["model"], "ok"
elif probe["model_available"] is False:
    model_value, model_state = "Unavailable · " + settings["model"], "bad"
else:
    model_value, model_state = settings["model"] or "Not configured", "warn"
with status_columns[1]:
    render_status_card("Current AI Model", model_value, model_state, "model")
tavily_state = st.session_state.get(
    "tavily_state", "configured" if settings["tavily_api_key"] else "missing"
)
tavily_value = {
    "active": "Live search active",
    "failed": "Search unavailable",
    "configured": "Configured · not yet tested",
    "missing": "Not configured",
}[tavily_state]
with status_columns[2]:
    render_status_card(
        "Tavily live search", tavily_value,
        "ok" if tavily_state == "active" else "bad" if tavily_state in {"failed", "missing"} else "warn",
        "search",
    )

analysis = st.session_state.get("analysis")
submitted = False

if st.session_state["active_view"] == "Analytics":
    st.markdown('<div class="section-title">Audit analytics</div>', unsafe_allow_html=True)
    if analysis and analysis["results"]:
        counts, score, trust = summarize(analysis["results"])
        st.caption(f"Latest audit · {analysis['created_at']} · {trust} at {score}/100")
        st.bar_chart(
            {"Fresh": [counts["Fresh"]], "Stale": [counts["Stale"]], "Unverified": [counts["Unverified"]]},
            horizontal=True,
        )
        render_analysis(analysis)
    else:
        st.markdown(
            '<div class="empty-state"><div class="empty-wave">'
            f'{icon_svg("analytics")}</div><div class="empty-copy">'
            '<strong>No audit metrics yet</strong>Run a live analysis to see claim counts and freshness distribution. No historical metrics are fabricated.</div></div>',
            unsafe_allow_html=True,
        )
else:
    if st.session_state["active_view"] == "Quick Presets":
        st.markdown(
            '<div class="section-title">Quick Presets</div>'
            f'<div class="empty-copy">{html.escape(selected)} — {html.escape(PRESET_NOTES[selected])}</div>',
            unsafe_allow_html=True,
        )

    with st.container(key="analysis_card", border=True):
        heading_columns = st.columns([1.5, 1], vertical_alignment="center")
        with heading_columns[0]:
            st.markdown(
                f'<div class="input-title">{icon_svg("wand")}Analyze an Answer</div>'
                '<div class="input-hint">Paste / Type your claim or fact.</div>',
                unsafe_allow_html=True,
            )
        with heading_columns[1]:
            st.markdown('<div class="live-flag"><span></span>LIVE SOURCES — NO MOCK DATA</div>', unsafe_allow_html=True)
        with st.form("audit_form", clear_on_submit=False):
            st.text_area(
                "Paste / Type your claim or fact", key="answer_text", height=170, max_chars=8000,
                placeholder="Example: Node.js 18 is the current Active LTS release…",
                label_visibility="collapsed",
            )
            submitted = st.form_submit_button(
                "Analyze Claim", type="primary", use_container_width=True,
                icon=":material/search:",
            )

    if submitted:
        st.session_state["analysis"] = None
        st.session_state.pop("analysis_error", None)
        if probe["state"] == "connected" and probe["model_available"] is False:
            st.session_state["analysis_error"] = (
                "The configured model is not listed by Bifrost for this gateway. "
                "Check MODEL_NAME and model permissions."
            )
        elif not st.session_state["answer_text"].strip():
            st.session_state["analysis_error"] = "Enter text or load a preset before running an audit."
        else:
            wait = 0
            if st.session_state["access_role"] != ROLE_ADMIN:
                who = visitor_key()
                wait = limiter.hit([
                    (f"st-analyze-min:{who}", security_cfg.analyze_limit_per_minute, 60),
                    (f"st-analyze-hour:{who}", security_cfg.analyze_limit_per_hour, 3600),
                ])
            gate = concurrency_gate("streamlit-analyses", security_cfg.max_concurrent_analyses)
            if wait:
                result, error = None, f"Analysis limit reached. Try again in {wait}s."
            elif not gate.acquire(blocking=False):
                result, error = None, "StaleBot is busy with other analyses. Please try again shortly."
            else:
                try:
                    with st.spinner("Extracting claims and checking live sources…"):
                        result, error = analyze_text(st.session_state["answer_text"], settings)
                finally:
                    gate.release()
            if error:
                st.session_state["analysis_error"] = error
            else:
                st.session_state["analysis"] = result
                if result["search_successes"]:
                    st.session_state["tavily_state"] = "active" if not result["search_failures"] else "failed"
                elif result["results"]:
                    st.session_state["tavily_state"] = "failed"
                st.session_state["bifrost_probe"] = {"state": "connected", "model_available": True}
                st.rerun()

    if st.session_state.get("analysis_error"):
        st.error(st.session_state["analysis_error"])
    elif st.session_state.get("analysis") is not None:
        render_analysis(st.session_state["analysis"])
    else:
        st.markdown(
            '<div class="empty-state"><div class="empty-wave">'
            f'{icon_svg("search")}</div><div class="empty-copy">'
            '<strong>Your audit workspace is ready.</strong>'
            'Paste a claim above and click Analyze Claim to get real-time verification results.</div></div>',
            unsafe_allow_html=True,
        )