"""StaleBot — Streamlit UI.

Run locally:  python -m streamlit run app.py
On Streamlit Community Cloud, put the keys from .env.example into the app's Secrets.
"""
import html
import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
import streamlit as st

from detector import (
    ERR_NOT_CONFIGURED,
    ERR_OFFLINE,
    analyze_text,
    build_reports,
    check_service,
    get_settings,
    llm_routes,
    summarize,
)
from security import ROLE_ADMIN, SecurityConfig, concurrency_gate, limiter, role_for_token

load_dotenv(dotenv_path=Path(__file__).with_name(".env"), override=True)

# "auto" = sidebar open on desktop, collapsed on phones.
st.set_page_config(
    page_title="StaleBot · Stale-Answer Detector", page_icon="🛡️", layout="wide",
    initial_sidebar_state="auto",
)


def load_streamlit_secrets():
    """Streamlit Cloud keeps keys in st.secrets; copy top-level values into the environment so the
    shared detector/security code (which reads os.environ) sees them. Real env vars win."""
    try:
        items = dict(st.secrets)
    except Exception:  # no secrets file locally
        return
    for key, value in items.items():
        if isinstance(value, (str, int, float, bool)) and not os.environ.get(key):
            os.environ[key] = str(value)


load_streamlit_secrets()

# ---------------------------------------------------------------------------- styles
# Injected first, before any widget, so nothing renders unstyled.
st.session_state.setdefault("theme", "Dark")
LIGHT = st.session_state["theme"] == "Light"

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root{--page:#070B18;--sidebar:#0B1024;--panel:#10172B;--raised:#151D35;--input:#0A1022;--blue:#2563EB;--violet:#7C3AED;--cyan:#22D3EE;--green:#10B981;--rose:#EF4444;--amber:#F59E0B;--text:#F8FAFC;--muted:#94A3B8;--line:rgba(99,130,255,.2);
--v-verified:#34D399;--v-partial:#FBBF24;--v-stale:#C084FC;--v-false:#FB7185;--v-unclear:#94A3B8}
/* Text font only: icon fonts (Material Symbols) keep their own family. */
html,body,.stApp,.stMarkdown,p,label,input,textarea,button,h1,h2,h3,h4{font-family:'Inter',sans-serif;letter-spacing:0}
[data-testid="stAppViewContainer"],[data-testid="stApp"]{color:var(--text);background:radial-gradient(760px 420px at 82% -8%,rgba(37,99,235,.16),transparent 65%),radial-gradient(620px 360px at 50% 12%,rgba(124,58,237,.07),transparent 68%),var(--page)!important}
[data-testid="stHeader"]{background:transparent}
[data-testid="stSidebar"]{background:var(--sidebar);border-right:1px solid var(--line)}
[data-testid="stMainMenu"]{display:none!important}
.block-container{max-width:1240px;padding-top:1.8rem;padding-bottom:3rem}
p,label{color:var(--muted)}
hr{border-color:var(--line)!important}

/* All inline SVG icons */
.ico{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round;flex:0 0 auto}

/* Inputs: dark surfaces, readable text, visible focus */
[data-baseweb="textarea"],[data-baseweb="base-input"],[data-baseweb="input"]{background:var(--input)!important;border-color:var(--line)!important;border-radius:10px!important}
[data-testid="stTextArea"] textarea,[data-testid="stTextInput"] input{color:var(--text)!important;background:var(--input)!important;caret-color:var(--text);font-size:.92rem;line-height:1.6}
[data-testid="stTextArea"] textarea::placeholder{color:var(--muted)!important;opacity:1}
[data-baseweb="textarea"]:focus-within{border-color:#8B5CF6!important;box-shadow:0 0 0 2px rgba(139,92,246,.22)}
[data-testid="stSelectbox"] div[data-baseweb="select"]>div{color:var(--text);background:var(--input);border-color:var(--line);border-radius:10px}
/* Dropdown menus render in a portal, outside the sidebar, so style them globally */
[data-baseweb="popover"] ul[role="listbox"],[data-baseweb="popover"] [data-baseweb="menu"]{background:var(--panel)!important;border:1px solid var(--line)!important}
[data-baseweb="popover"] li[role="option"]{color:var(--text)!important;background:transparent!important}
[data-baseweb="popover"] li[role="option"]:hover,[data-baseweb="popover"] li[aria-selected="true"]{background:rgba(124,58,237,.22)!important}

/* Buttons */
.stButton>button,[data-testid="stFormSubmitButton"]>button,[data-testid="stDownloadButton"]>button{min-height:2.55rem;border:1px solid var(--line);border-radius:10px;color:var(--text);background:var(--raised);font-weight:650;transition:filter .16s ease,transform .16s ease}
.stButton>button:hover:not(:disabled),[data-testid="stFormSubmitButton"]>button:hover:not(:disabled){filter:brightness(1.12);transform:translateY(-1px)}
button[kind*="primary"],button[data-testid*="primary"]{color:#FFFFFF!important;background:linear-gradient(100deg,var(--blue),var(--violet))!important;border:0!important}
button[kind*="primary"] *,button[data-testid*="primary"] *{color:#FFFFFF!important}
button:disabled{opacity:.5!important;cursor:not-allowed!important;transform:none!important}

[data-testid="stVerticalBlockBorderWrapper"]{border-color:var(--line)!important;border-radius:14px!important;background:var(--panel)}
[data-testid="stExpander"]{border-color:var(--line);border-radius:10px;background:var(--panel)}
[data-testid="stProgressBar"]>div>div{background:linear-gradient(90deg,var(--blue),var(--violet))}
[data-testid="stAlert"] p{margin:0!important;line-height:1.55!important;overflow-wrap:anywhere}

/* Sidebar: compact */
[data-testid="stSidebar"] .block-container,[data-testid="stSidebarContent"]{padding-top:1rem}
.brand-lockup{display:flex;align-items:center;gap:11px;margin:0 0 .6rem}
.brand-mark{width:38px;height:38px;display:grid;place-items:center;border:1px solid rgba(59,130,246,.32);border-radius:12px;color:#93C5FD;background:linear-gradient(145deg,rgba(37,99,235,.24),rgba(124,58,237,.16))}
.brand-name{color:var(--text);font-size:1rem;font-weight:800}.brand-tagline{margin-top:2px;color:var(--muted);font-size:.7rem}
.sidebar-label{margin:1rem 0 .4rem;color:#64748B;font-size:.66rem;font-weight:700;text-transform:uppercase;letter-spacing:1px}
.step-row{display:flex;gap:.65rem;margin:.55rem 0}.step-num{width:24px;height:24px;display:grid;place-items:center;flex:0 0 24px;border:1px solid rgba(59,130,246,.26);border-radius:7px;color:#93C5FD;background:rgba(37,99,235,.1);font-size:.66rem;font-weight:750}.step-copy{color:var(--muted);font-size:.72rem;line-height:1.45}.step-copy strong{display:block;color:#E2E8F0;font-size:.74rem}

/* Hero */
.hero-shell{position:relative;overflow:hidden;display:flex;align-items:center;gap:1.2rem;padding:1.3rem 1.45rem;border:1px solid var(--line);border-radius:16px;background:linear-gradient(115deg,rgba(16,23,43,.96),rgba(21,29,53,.8))}
.hero-text{flex:1;min-width:0}
.hero-kicker{color:#9BBEFF;font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:1px}
.hero-title{margin:.35rem 0;color:var(--text);font-size:2rem;font-weight:800;line-height:1.15}
.hero-title span{background:linear-gradient(90deg,#60A5FA,#A78BFA,#22D3EE);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
.hero-copy{max-width:640px;color:var(--muted);font-size:.9rem;line-height:1.6}
.hero-art{width:84px;height:84px;flex:0 0 84px;display:grid;place-items:center;border:1px solid rgba(96,165,250,.35);border-radius:24px;color:#BFDBFE;background:linear-gradient(145deg,rgba(37,99,235,.28),rgba(124,58,237,.2))}
.hero-art .ico{width:44px;height:44px;stroke-width:1.6}

/* Status cards: text wraps instead of being cut off; full text in the tooltip too */
.status-card{display:flex;align-items:center;gap:12px;min-height:76px;height:100%;padding:.8rem .95rem;border:1px solid var(--line);border-radius:12px;background:linear-gradient(145deg,var(--panel),rgba(21,29,53,.76))}
.status-icon{width:38px;height:38px;display:grid;place-items:center;flex:0 0 38px;border:1px solid var(--line);border-radius:11px;color:#93C5FD;background:rgba(59,130,246,.1)}
.status-title{color:var(--muted);font-size:.7rem}
.status-value{margin-top:3px;color:var(--text);font-size:.82rem;font-weight:650;line-height:1.35;overflow-wrap:anywhere}
.status-led{width:7px;height:7px;display:inline-block;margin-right:6px;border-radius:50%;vertical-align:middle}
.status-led.ok{background:var(--green);box-shadow:0 0 9px rgba(16,185,129,.45)}.status-led.warn{background:var(--amber)}.status-led.bad{background:var(--rose)}

/* Offline banner */
.offline-banner{display:flex;gap:12px;align-items:flex-start;padding:.9rem 1rem;border:1px solid rgba(239,68,68,.35);border-radius:12px;background:rgba(239,68,68,.08);color:var(--text)}
.offline-banner.warn{border-color:rgba(245,158,11,.4);background:rgba(245,158,11,.08)}
.offline-banner .ico{color:#F87171;margin-top:2px}.offline-banner.warn .ico{color:#FBBF24}
.offline-banner strong{display:block;margin-bottom:2px}.offline-banner span{color:var(--muted);font-size:.84rem}

/* Analyze card */
.st-key-analysis_card{padding:1.05rem 1.15rem!important;border:1px solid rgba(124,58,237,.35)!important;border-radius:15px!important;background:linear-gradient(145deg,var(--panel),var(--raised))!important}
.input-title{display:flex;align-items:center;gap:9px;color:var(--text);font-size:1rem;font-weight:700}.input-title .ico{color:#A78BFA}
.input-hint{margin:.25rem 0 .7rem;color:var(--muted);font-size:.8rem}
.live-flag{display:flex;justify-content:flex-end;align-items:center;gap:7px;color:var(--muted);font-size:.66rem;font-weight:700;letter-spacing:.6px}
.live-flag span{width:6px;height:6px;border-radius:50%;background:var(--green);box-shadow:0 0 10px rgba(16,185,129,.45)}

/* Results */
.section-heading{margin:1.5rem 0 .7rem}.section-heading h2{margin:0;color:var(--text);font-size:1.15rem!important;font-weight:750!important}
.kpi-card{height:118px;padding:1rem;border:1px solid var(--line);border-radius:12px;background:linear-gradient(145deg,rgba(25,36,58,.92),rgba(21,30,48,.88))}
.kpi-label{color:var(--muted);font-size:.76rem;font-weight:600}.kpi-value{margin-top:.45rem;color:var(--text);font-size:1.8rem;font-weight:800}.kpi-meta{margin-top:.35rem;color:#8292AA;font-size:.72rem}
.claim-card{padding:1rem 1.1rem;margin:.7rem 0;border:1px solid var(--line);border-left:4px solid var(--vc);border-radius:12px;background:var(--panel)}
.claim-head{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.vbadge{display:inline-block;padding:.24rem .6rem;border-radius:999px;font-size:.7rem;font-weight:800;letter-spacing:.5px;color:var(--vc);background:color-mix(in srgb,var(--vc) 14%,transparent);border:1px solid color-mix(in srgb,var(--vc) 40%,transparent)}
.claim-score{margin-left:auto;color:var(--muted);font-size:.78rem}.claim-score b{color:var(--text);font-size:1.05rem}
.claim-text{margin:.55rem 0 .2rem;color:var(--text);font-weight:650;font-size:.98rem;line-height:1.45}
.claim-now{color:var(--text);font-size:.9rem;line-height:1.5}.claim-now em{font-style:normal;color:var(--vc);font-weight:700}
.v-verified{--vc:var(--v-verified)}.v-partial{--vc:var(--v-partial)}.v-stale{--vc:var(--v-stale)}.v-false{--vc:var(--v-false)}.v-unclear{--vc:var(--v-unclear)}
.src-list{margin:.7rem 0 0;padding:0;list-style:none;display:grid;gap:.45rem}
.src-list li{padding:.55rem .7rem;border:1px solid var(--line);border-radius:9px;font-size:.82rem}
.src-list a{color:var(--text);font-weight:650;text-decoration:none}.src-list a:hover{color:#A78BFA;text-decoration:underline}
.src-meta{display:block;margin-top:2px;color:var(--muted);font-size:.74rem}
.src-none{color:var(--muted);font-size:.8rem;margin-top:.5rem}
.example-tag{display:inline-block;margin-bottom:.4rem;padding:.2rem .55rem;border-radius:6px;font-size:.66rem;font-weight:800;letter-spacing:.7px;color:#C4B5FD;background:rgba(124,58,237,.16);border:1px solid rgba(167,139,250,.35)}
.empty-state{display:flex;align-items:center;gap:15px;padding:1.05rem 1.2rem;border:1px solid var(--line);border-radius:12px;background:rgba(21,30,48,.45)}
.empty-wave{width:46px;height:46px;display:grid;place-items:center;flex:0 0 46px;border:1px solid rgba(59,130,246,.24);border-radius:14px;color:#93C5FD;background:rgba(37,99,235,.1)}
.empty-copy{color:var(--muted);font-size:.84rem;line-height:1.55}.empty-copy strong{display:block;margin-bottom:3px;color:var(--text);font-size:.9rem}

/* Footer */
.footer{margin-top:2.5rem;padding:1.1rem 0 .5rem;border-top:1px solid var(--line);color:var(--muted);font-size:.8rem;line-height:1.7}
.footer strong{color:var(--text)}.footer a{color:#A78BFA;text-decoration:none}.footer a:hover{text-decoration:underline}
.stack-chip{display:inline-block;margin:0 .3rem .3rem 0;padding:.1rem .5rem;border:1px solid var(--line);border-radius:999px;font-size:.72rem;color:var(--text)}

@media(max-width:760px){
 .block-container{padding:1rem .85rem 2.5rem}
 .hero-shell{padding:1rem}.hero-title{font-size:1.6rem}.hero-art{width:60px;height:60px;flex-basis:60px;border-radius:18px}.hero-art .ico{width:32px;height:32px}
 .kpi-card{height:auto}
 .claim-score{margin-left:0;width:100%}
}
</style>
""", unsafe_allow_html=True)

if LIGHT:
    st.markdown("""
    <style>
    :root{--page:#F8FAFC;--sidebar:#FFFFFF;--panel:#FFFFFF;--raised:#F1F5F9;--input:#FFFFFF;--text:#0F172A;--muted:#5B6478;--line:#DCE3EE;
    --v-verified:#047857;--v-partial:#B45309;--v-stale:#7E22CE;--v-false:#BE123C;--v-unclear:#475569}
    [data-testid="stAppViewContainer"],[data-testid="stApp"]{color:var(--text);background:var(--page)!important}
    [data-testid="stSidebar"],[data-testid="stSidebar"]>div:first-child{background:var(--sidebar)!important}
    [data-testid="stSidebar"] *,[data-testid="stMarkdownContainer"] p,[data-testid="stCaptionContainer"]{color:var(--text)}
    [data-testid="stHeader"]{background:transparent}
    .hero-shell,.status-card,.kpi-card,.empty-state,.claim-card,.st-key-analysis_card,[data-testid="stVerticalBlockBorderWrapper"],[data-testid="stExpander"]{background:#FFFFFF!important;box-shadow:0 10px 26px rgba(15,23,42,.05)}
    .hero-kicker,.step-num{color:#1D4ED8}.step-copy strong,.brand-name{color:var(--text)}
    .hero-art{color:#4338CA;border-color:#C7D2FE;background:linear-gradient(145deg,#EEF2FF,#F5F3FF)}
    .brand-mark,.status-icon{color:#4338CA;background:#EEF2FF;border-color:#C7D2FE}
    .empty-wave{color:#4338CA;background:#EEF2FF;border-color:#C7D2FE}
    .kpi-meta{color:#64748B}
    .stButton>button,[data-testid="stDownloadButton"]>button{color:var(--text);background:#FFFFFF;border-color:var(--line)}
    [data-baseweb="select"]>div,[data-baseweb="popover"] ul[role="listbox"],[data-baseweb="popover"] [data-baseweb="menu"]{background:#FFFFFF!important;color:var(--text)!important}
    [data-baseweb="popover"] li[role="option"]{color:var(--text)!important}
    [data-baseweb="popover"] li[role="option"]:hover,[data-baseweb="popover"] li[aria-selected="true"]{background:#EEF2FF!important}
    [data-testid="stSelectbox"] div[data-baseweb="select"] *{color:var(--text)!important}
    .example-tag{color:#6D28D9;background:#F5F3FF;border-color:#DDD6FE}
    button[data-testid^="stBaseButton-segmented_control"]{background:#FFFFFF!important;color:var(--text)!important;border-color:var(--line)!important}
    button[data-testid="stBaseButton-segmented_controlActive"]{background:#F5F3FF!important;color:#6D28D9!important;border-color:#A78BFA!important}
    button[data-testid^="stBaseButton-segmented_control"] *{color:inherit!important}
    .offline-banner{background:#FEF2F2}.offline-banner.warn{background:#FFFBEB}
    [data-testid="stAlert"]{background:#FFFFFF!important}
    [data-testid="stAlert"] p{color:var(--text)!important}
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------------------------- content
PRESETS = {
    "Outdated tech stack": "Python 3.9 is the latest stable release of Python. React 17 is the latest major release of React. Node.js 18 is currently an Active LTS release.",
    "AI API pricing (historic)": "GPT-4 Turbo is the latest model in the GPT-4 family. GPT-4 Turbo API pricing is $10 per million input tokens and $30 per million output tokens.",
    "Mixed claims": "Python 3.14 was released in 2025. React 17 is the latest major release of React. Node.js 24 is an Active LTS release.",
    "Write my own": "",
}
PRESET_NOTES = {
    "Outdated tech stack": "Version and lifecycle claims.",
    "AI API pricing (historic)": "Old pricing claims — are they still current?",
    "Mixed claims": "Some current, some not. None are pre-judged.",
    "Write my own": "Clears the box so you can paste your own text.",
}

# Verdict → (CSS class, badge text). "Unverified" is shown to visitors as "Unclear".
VERDICT_STYLE = {
    "Verified": ("v-verified", "VERIFIED · CURRENT"),
    "Partially True": ("v-partial", "PARTIALLY TRUE"),
    "Stale": ("v-stale", "STALE"),
    "False": ("v-false", "FALSE"),
    "Unverified": ("v-unclear", "UNCLEAR"),
}
FALLBACK_VERDICT = {"Fresh": "Verified", "Stale": "Stale", "Unverified": "Unverified"}

# A real result StaleBot produced on 13 Nov 2026 (gpt-oss-20b via Groq + Tavily), shown on the
# landing page so visitors see what a check looks like before running one.
EXAMPLE_CHECKED_ON = "13 Nov 2026"
EXAMPLE_RESULT = {
    "claim": "React 17 is the latest major release of React",
    "status": "Stale", "verdict": "Stale", "freshness_score": 10,
    "updated_fact": "React 19 is the latest major release of React.",
    "explanation": ("The sources show React 18 was released in March 2022 and React 19 in December "
                    "2024, with the latest stable version 19.2.8 as of July 2026. The claim is no "
                    "longer accurate."),
    "evidence_analysis": "endoflife.date lists React 19 (released 05 Dec 2024) as the current major "
                         "line; the React 17 announcement is from 2020.",
    "recommended_correction": "React 19 is the latest major release of React.",
    "sources": [
        {"title": "React | endoflife.date", "url": "https://endoflife.date/react",
         "published_date": "", "stated_date": "2026-07-21"},
        {"title": "React v17.0 – React Blog", "url": "https://legacy.reactjs.org/blog/2020/10/20/react-v17.html",
         "published_date": "", "stated_date": "2020-10-20"},
        {"title": "Versioning Policy – React", "url": "https://react.dev/community/versioning-policy",
         "published_date": "", "stated_date": ""},
    ],
}

ICONS = {
    "shield": '<path d="M12 3 19 6v5c0 4.5-2.8 7.6-7 10-4.2-2.4-7-5.5-7-10V6l7-3Z"/><path d="m9 12 2 2 4-4"/>',
    "bolt": '<path d="m13 2-3 9h7L9 22l3-9H5l8-11Z"/>',
    "model": '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M9 9h6v6H9zM9 1v3m6-3v3M9 20v3m6-3v3M1 9h3m-3 6h3m16-6h3m-3 6h3"/>',
    "search": '<circle cx="11" cy="11" r="7.5"/><path d="m21 21-4.3-4.3"/>',
    "wand": '<path d="m15 4 5 5M3 21l12-12M6 3l.8 2.2L9 6l-2.2.8L6 9l-.8-2.2L3 6l2.2-.8L6 3Zm12 10 .8 2.2L21 16l-2.2.8L18 19l-.8-2.2L15 16l2.2-.8L18 13Z"/>',
    "alert": '<circle cx="12" cy="12" r="10"/><path d="M12 7v6M12 17h.01"/>',
    "plug": '<path d="M9 2v6M15 2v6M6 8h12v4a6 6 0 0 1-12 0V8ZM12 18v4"/>',
}


def icon_svg(name):
    return f'<svg class="ico" viewBox="0 0 24 24" aria-hidden="true">{ICONS[name]}</svg>'


def esc(value):
    return html.escape(str(value or ""))


def safe_url(url):
    parsed = urlparse(url or "")
    return url if parsed.scheme in {"http", "https"} and parsed.hostname else None


def render_status_card(label, value, state, icon_name, detail=""):
    state_class = state if state in {"ok", "warn", "bad"} else "warn"
    tip = esc(f"{label}: {value}" + (f" — {detail}" if detail else ""))
    st.markdown(
        f'<div class="status-card" title="{tip}"><div class="status-icon">{icon_svg(icon_name)}</div>'
        f'<div style="min-width:0;flex:1"><div class="status-title">{esc(label)}</div>'
        f'<div class="status-value"><span class="status-led {state_class}"></span>{esc(value)}</div>'
        "</div></div>",
        unsafe_allow_html=True,
    )


def render_kpi(label, value, note, accent):
    st.markdown(
        f'<div class="kpi-card" style="border-top:2px solid {accent}"><div class="kpi-label">{esc(label)}</div>'
        f'<div class="kpi-value">{esc(value)}</div><div class="kpi-meta">{esc(note)}</div></div>',
        unsafe_allow_html=True,
    )


def source_date_text(source):
    if source.get("published_date"):
        return f"Published {source['published_date'][:10]}"
    if source.get("stated_date"):
        return f"Dated {source['stated_date']} (from the page)"
    return "No date given by the source"


def render_claim(item, index=None, example=False):
    verdict = item.get("verdict") or FALLBACK_VERDICT.get(item.get("status"), "Unverified")
    css, badge = VERDICT_STYLE.get(verdict, VERDICT_STYLE["Unverified"])
    sources = item.get("sources") or []
    items = []
    for source in sources:
        url = safe_url(source.get("url"))
        title = esc(source.get("title") or (urlparse(url).hostname if url else "Source"))
        host = esc(urlparse(url).hostname.removeprefix("www.")) if url else ""
        link = f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{title} ↗</a>' if url else f"<b>{title}</b>"
        items.append(f'<li>{link}<span class="src-meta">{host}{" · " if host else ""}{esc(source_date_text(source))}</span></li>')
    sources_html = (f'<ul class="src-list">{"".join(items)}</ul>' if items
                    else '<div class="src-none">No live sources were returned for this claim.</div>')
    if verdict in {"Stale", "False"}:
        now = f'<div class="claim-now"><em>Now:</em> {esc(item.get("updated_fact"))}</div>'
    elif verdict == "Unverified":
        now = f'<div class="claim-now"><em>Why unclear:</em> {esc(item.get("explanation"))}</div>'
    else:
        now = f'<div class="claim-now"><em>Confirmed:</em> {esc(item.get("updated_fact"))}</div>'
    label = "EXAMPLE" if example else (f"CLAIM {index:02d}" if index else "")
    st.markdown(
        f'<div class="claim-card {css}"><div class="claim-head">'
        + (f'<span class="example-tag">{label}</span>' if example else f'<span class="status-title">{label}</span>')
        + f'<span class="vbadge">{badge}</span>'
        f'<span class="claim-score"><b>{int(item.get("freshness_score", 0))}</b>/100 freshness</span></div>'
        f'<div class="claim-text">{esc(item.get("claim"))}</div>{now}{sources_html}</div>',
        unsafe_allow_html=True,
    )
    with st.expander("Full assessment", expanded=False):
        st.markdown(f"**Assessment.** {item.get('explanation', '')}")
        st.markdown(f"**Evidence.** {item.get('evidence_analysis', '')}")
        st.markdown(f"**Suggested correction.** {item.get('recommended_correction', '')}")


def render_downloads(analysis):
    full_report, corrected_summary = build_reports(analysis)
    downloads = st.columns(2)
    with downloads[0]:
        st.download_button("Download full audit (.md)", full_report, "stalebot-audit.md",
                           "text/markdown", use_container_width=True)
    with downloads[1]:
        st.download_button("Download corrected summary (.md)", corrected_summary,
                           "stalebot-corrected-summary.md", "text/markdown", use_container_width=True)


def render_analysis(analysis):
    results = analysis["results"]
    if analysis.get("claims_truncated"):
        st.info(f"{analysis['claims_truncated']} more claim(s) were found but not checked: each check is "
                f"limited to {len(results)} claims. Split long texts into smaller parts.")
    if not results:
        st.markdown(
            f'<div class="empty-state"><div class="empty-wave">{icon_svg("search")}</div><div class="empty-copy">'
            "<strong>No checkable claims found</strong>StaleBot looks for facts that can go out of date — "
            "versions, prices, release dates, rules. Try text that states one.</div></div>",
            unsafe_allow_html=True,
        )
        return

    counts, score, trust = summarize(results)
    verdicts = [r.get("verdict") or FALLBACK_VERDICT.get(r["status"], "Unverified") for r in results]
    stale = sum(v in {"Stale", "False"} for v in verdicts)
    st.markdown('<div class="section-heading"><h2>Results</h2></div>', unsafe_allow_html=True)
    cards = st.columns(4, gap="small")
    values = [
        ("Overall freshness", f"{score}/100", trust, "#3B82F6"),
        ("Claims checked", len(results), f"via {analysis.get('provider_label') or 'AI model'}", "#8B5CF6"),
        ("Stale or false", stale, "Contradicted by newer evidence", "#C084FC"),
        ("Unclear", counts["Unverified"], "Not enough evidence either way", "#94A3B8"),
    ]
    for column, args in zip(cards, values):
        with column:
            render_kpi(*args)
    if analysis["search_failures"]:
        st.warning(f"{analysis['search_failures']} live search(es) failed. Those claims are marked unclear, not stale.")
    for index, item in enumerate(results, start=1):
        render_claim(item, index=index)
    st.markdown('<div class="section-heading"><h2>Export</h2></div>', unsafe_allow_html=True)
    render_downloads(analysis)


# ---------------------------------------------------------------------------- access
security_cfg = SecurityConfig.from_env()


def visitor_key():
    """Caller IP when Streamlit exposes it, otherwise a per-browser-session id."""
    ip = getattr(st.context, "ip_address", None)
    if ip:
        return ip
    st.session_state.setdefault("visitor_id", os.urandom(8).hex())
    return "session:" + st.session_state["visitor_id"]


if "access_role" not in st.session_state:
    st.session_state["access_role"] = role_for_token(security_cfg, "")
if st.session_state["access_role"] is None:
    st.markdown('<div class="hero-shell"><div class="hero-text"><div class="hero-kicker">Private workspace</div>'
                '<div class="hero-title">Stale<span>Bot</span></div>'
                '<div class="hero-copy">Enter the access key you were given to continue.</div></div></div>',
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

# ---------------------------------------------------------------------------- service status
settings = get_settings()
st.session_state.setdefault("answer_text", PRESETS["Outdated tech stack"])
st.session_state.setdefault("analysis", None)


@st.cache_data(ttl=60, show_spinner=False)
def shared_service_check(route_signature):
    """One tiny model call per minute at most, shared by every visitor (args are only a cache key)."""
    return check_service(get_settings())


def route_signature():
    return tuple((r["name"], r["base_url"], r["model"]) for r in llm_routes(settings))


if "service" not in st.session_state:
    st.session_state["service"] = shared_service_check(route_signature())


def recheck_service():
    wait = limiter.hit([(f"st-probe:{visitor_key()}", 1, max(1, security_cfg.probe_cooldown_s))])
    if wait and st.session_state["access_role"] != ROLE_ADMIN:
        st.toast(f"Checked a moment ago. Try again in {wait}s.")
        return
    shared_service_check.clear()
    with st.spinner("Checking the analysis service…"):
        st.session_state["service"] = shared_service_check(route_signature())
    st.session_state.pop("analysis_error", None)


service = st.session_state["service"]
service_state = service.get("state")
SERVICE_DOWN = service_state in {"unavailable", "missing"} or (
    service_state == "connected" and service.get("model_available") is False)

# ---------------------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown(
        f'<div class="brand-lockup"><div class="brand-mark">{icon_svg("shield")}</div><div>'
        '<div class="brand-name">StaleBot</div><div class="brand-tagline">Detect. Verify. Trust.</div></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="sidebar-label">Theme</div>', unsafe_allow_html=True)
    chosen = st.segmented_control("Theme", ["Dark", "Light"], default=st.session_state["theme"],
                                  key="theme_picker", label_visibility="collapsed")
    if chosen and chosen != st.session_state["theme"]:
        st.session_state["theme"] = chosen
        st.rerun()

    st.markdown('<div class="sidebar-label">Try an example</div>', unsafe_allow_html=True)
    selected = st.selectbox("Example text", list(PRESETS), key="selected_preset", label_visibility="collapsed")
    st.caption(PRESET_NOTES[selected])
    if st.button("Use this example", use_container_width=True):
        st.session_state["answer_text"] = PRESETS[selected]
        st.session_state["analysis"] = None
        st.session_state.pop("analysis_error", None)
        st.rerun()

    st.markdown('<div class="sidebar-label">How it works</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="step-row"><span class="step-num">1</span><div class="step-copy"><strong>Extract</strong>Find facts that can go out of date.</div></div>'
        '<div class="step-row"><span class="step-num">2</span><div class="step-copy"><strong>Search</strong>Look each one up on the live web.</div></div>'
        '<div class="step-row"><span class="step-num">3</span><div class="step-copy"><strong>Score</strong>Compare with current evidence and rate freshness.</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="sidebar-label">Service</div>', unsafe_allow_html=True)
    if st.button("Re-check connection", use_container_width=True, key="sidebar_recheck"):
        recheck_service()
        st.rerun()

# ---------------------------------------------------------------------------- main
st.markdown(
    '<div class="hero-shell"><div class="hero-text"><div class="hero-kicker">Real-time claim checking</div>'
    '<div class="hero-title">Stale<span>Bot</span></div>'
    '<div class="hero-copy">Paste an AI answer, headline or claim. StaleBot finds the facts that can '
    'go out of date, checks each one against live web sources, and tells you which are still true.</div></div>'
    f'<div class="hero-art">{icon_svg("shield")}</div></div>',
    unsafe_allow_html=True,
)

status_columns = st.columns(3, gap="small")
provider = service.get("provider")
service_value, service_level, service_detail = {
    "connected": ("Online" + (" · Groq direct" if provider == "groq" else ""), "ok",
                  "Gateway offline; using the direct Groq fallback" if provider == "groq" else "AI model is responding"),
    "unavailable": ("Offline", "bad", "The AI model can't be reached right now"),
    "missing": ("Not set up", "warn", "Model keys are missing"),
}.get(service_state, ("Checking…", "warn", ""))
if service_state == "connected" and service.get("model_available") is False:
    service_value, service_level, service_detail = "Model unavailable", "bad", "The model rejected the request"
with status_columns[0]:
    render_status_card("AI service", service_value, service_level, "bolt", service_detail)
model_id = service.get("model") or settings["model"]
with status_columns[1]:
    model_level = ("bad" if service.get("model_available") is False
                   else "ok" if service_state == "connected" else "warn")
    render_status_card("AI model", model_id.split("/")[-1], model_level, "model", model_id)
tavily_state = st.session_state.get("tavily_state", "configured" if settings["tavily_api_key"] else "missing")
tavily_value = {"active": "Active", "failed": "Failing", "configured": "Ready",
                "missing": "Not set up"}[tavily_state]
with status_columns[2]:
    render_status_card("Live web search (Tavily)", tavily_value,
                       {"active": "ok", "configured": "ok", "failed": "bad"}.get(tavily_state, "warn"), "search",
                       "Each claim is searched on the live web")

if SERVICE_DOWN:
    st.write("")
    banner_cols = st.columns([5, 1.2], vertical_alignment="center")
    with banner_cols[0]:
        if service_state == "missing":
            st.markdown(f'<div class="offline-banner warn">{icon_svg("plug")}<div><strong>StaleBot isn\'t set up yet</strong>'
                        "<span>The site owner still needs to add the service keys. Analysis is paused until then.</span></div></div>",
                        unsafe_allow_html=True)
        elif service.get("model_available") is False:
            # The model endpoint answered but refused: a key or model-name problem, not an outage.
            fix = {"key": "Check GROQ_API_KEY (or BIFROST_VIRTUAL_KEY) in the app's secrets.",
                   "model": "Set GROQ_MODEL (or MODEL_NAME) to a model the provider currently lists."}.get(
                service.get("reason"), "Check the app's model settings and logs.")
            st.markdown(f'<div class="offline-banner warn">{icon_svg("plug")}<div><strong>The AI model refused the request</strong>'
                        f'<span>{esc(service.get("reason_detail") or "The model endpoint refused the request.")} '
                        f'Provider: {esc(service.get("provider_label") or "unknown")} · model: {esc(service.get("model") or "?")}. '
                        f"Site owner: {esc(fix)}</span></div></div>",
                        unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="offline-banner">{icon_svg("alert")}<div><strong>The analysis service is offline right now</strong>'
                        "<span>Analyzing is paused until it's back. This is usually temporary — try again in a minute.</span></div></div>",
                        unsafe_allow_html=True)
    with banner_cols[1]:
        if service_state != "missing" and st.button("Retry", type="primary", use_container_width=True, key="banner_retry"):
            recheck_service()
            st.rerun()

st.write("")
submitted = False
with st.container(key="analysis_card", border=True):
    heading_columns = st.columns([1.5, 1], vertical_alignment="center")
    with heading_columns[0]:
        st.markdown(f'<div class="input-title">{icon_svg("wand")}Check a claim or AI answer</div>'
                    '<div class="input-hint">Paste text below — StaleBot checks every time-sensitive fact in it.</div>',
                    unsafe_allow_html=True)
    with heading_columns[1]:
        st.markdown('<div class="live-flag"><span></span>LIVE SOURCES — NO MOCK DATA</div>', unsafe_allow_html=True)
    with st.form("audit_form", clear_on_submit=False, border=False):
        st.text_area("Text to check", key="answer_text", height=150, max_chars=8000,
                     placeholder="Example: Node.js 18 is the current Active LTS release…",
                     label_visibility="collapsed")
        submitted = st.form_submit_button(
            ("AI model unavailable — analysis paused" if service.get("model_available") is False
             else "Service offline — analysis paused") if SERVICE_DOWN else "Analyze claim",
            type="primary", use_container_width=True, disabled=SERVICE_DOWN,
        )

if submitted and not SERVICE_DOWN:
    st.session_state["analysis"] = None
    st.session_state.pop("analysis_error", None)
    text = st.session_state["answer_text"].strip()
    if not text:
        st.session_state["analysis_error"] = "Type or paste some text first, or pick an example in the sidebar."
    else:
        wait = 0
        if st.session_state["access_role"] != ROLE_ADMIN:
            who = visitor_key()
            wait = limiter.hit([
                (f"st-analyze-min:{who}", security_cfg.analyze_limit_per_minute, 60),
                (f"st-analyze-hour:{who}", security_cfg.analyze_limit_per_hour, 3600),
            ])
        gate = concurrency_gate("streamlit-analyses", security_cfg.max_concurrent_analyses)
        result, error = None, None
        if wait:
            error = f"You've reached the analysis limit. Try again in {wait}s."
        elif not gate.acquire(blocking=False):
            error = "StaleBot is busy with other checks. Please try again in a few seconds."
        else:
            try:
                with st.status("Step 1 of 3 · Extracting claims…", expanded=True) as progress_box:
                    def on_progress(stage, index=None, total=None, claim=None):
                        if stage == "extract":
                            st.write("🔍 **Extracting** the facts that can go out of date…")
                        elif stage == "search":
                            progress_box.update(label=f"Step 2 of 3 · Searching live sources ({index}/{total})…")
                            st.write(f"🌐 **Searching** the web: _{claim}_")
                        elif stage == "score":
                            progress_box.update(label=f"Step 3 of 3 · Scoring freshness ({index}/{total})…")
                            st.write(f"⚖️ **Scoring** against current evidence ({index}/{total})")
                    result, error = analyze_text(text, settings, progress=on_progress)
                    progress_box.update(label="Check complete" if not error else "Check failed",
                                        state="complete" if not error else "error", expanded=False)
            finally:
                gate.release()
        if error:
            st.session_state["analysis_error"] = error
            if error == ERR_OFFLINE:
                shared_service_check.clear()
                st.session_state["service"] = {"state": "unavailable", "model_available": None, "provider": None}
            elif error == ERR_NOT_CONFIGURED:
                st.session_state["service"] = {"state": "missing", "model_available": None, "provider": None}
            st.rerun()
        else:
            st.session_state["analysis"] = result
            if result["search_successes"]:
                st.session_state["tavily_state"] = "active" if not result["search_failures"] else "failed"
            elif result["results"]:
                st.session_state["tavily_state"] = "failed"
            st.session_state["service"] = {"state": "connected", "model_available": True,
                                           "provider": result.get("provider"), "model": result.get("model_used")}
            st.rerun()

if st.session_state.get("analysis_error"):
    st.error(st.session_state["analysis_error"])
if st.session_state.get("analysis") is not None:
    render_analysis(st.session_state["analysis"])
else:
    st.markdown('<div class="section-heading"><h2>What a result looks like</h2></div>', unsafe_allow_html=True)
    st.caption(f"A real check StaleBot ran on {EXAMPLE_CHECKED_ON}. Your own results appear here after you click Analyze.")
    render_claim(EXAMPLE_RESULT, example=True)

# ---------------------------------------------------------------------------- footer
author = os.getenv("STALEBOT_AUTHOR", "").strip()
repo = safe_url(os.getenv("STALEBOT_GITHUB_URL", "").strip())
credits = []
if author:
    credits.append(f"Built by <strong>{esc(author)}</strong>")
if repo:
    credits.append(f'<a href="{esc(repo)}" target="_blank" rel="noopener noreferrer">Source on GitHub ↗</a>')
st.markdown(
    '<div class="footer"><strong>About StaleBot.</strong> Checks AI answers and claims for outdated '
    "information using live web sources. Results are AI-assessed: always open the sources before relying on them."
    + (f"<br>{' · '.join(credits)}" if credits else "")
    + '<br><span class="stack-chip">Groq · LLM</span><span class="stack-chip">Tavily · live search</span>'
    '<span class="stack-chip">Bifrost · AI gateway</span><span class="stack-chip">Streamlit · UI</span></div>',
    unsafe_allow_html=True,
)
