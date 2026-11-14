"""StaleBot — the localhost:8000 dashboard, rebuilt as a single Streamlit app.

Run:   python -m streamlit run streamlit_dashboard.py
Needs: detector.py and security.py from this project; keys from .env (or Streamlit secrets).

Pages: Dashboard · Analytics · Claim Projects · Historical Data · Settings.
History is stored in DATA_DIR/store.json (default ./data), the same format server.py uses.
"""
import html
import json
import os
import threading
import time
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import altair as alt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from detector import (
    ERR_NOT_CONFIGURED, ERR_OFFLINE, analyze_text, build_reports, check_service, get_settings, llm_routes,
)
from security import ROLE_ADMIN, SecurityConfig, concurrency_gate, limiter, role_for_token

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env", override=True)

st.set_page_config(page_title="StaleBot · Dashboard", page_icon="🛡️", layout="wide",
                   initial_sidebar_state="auto")


def load_streamlit_secrets():
    """On Streamlit Cloud, copy top-level secrets into the environment (real env vars win)."""
    try:
        items = dict(st.secrets)
    except Exception:
        return
    for key, value in items.items():
        if isinstance(value, (str, int, float, bool)) and not os.environ.get(key):
            os.environ[key] = str(value)


load_streamlit_secrets()

# ============================================================================ constants
VERDICTS = ["Verified", "Partially True", "Stale", "False", "Unverified"]
VERDICT_FROM_STATUS = {"Fresh": "Verified", "Stale": "Stale", "Unverified": "Unverified"}
VERDICT_META = {  # css class, label, icon (svg key), colour
    "Verified": ("v-verified", "Verified · Current", "check", "#22C55E"),
    "Partially True": ("v-partial", "Partially True", "alert", "#EAB308"),
    "Stale": ("v-stale", "Stale / Outdated", "hourglass", "#F97316"),
    "False": ("v-false", "False", "x", "#EF4444"),
    "Unverified": ("v-unverified", "Unverified", "help", "#7C86A8"),
}
SHORT = {"Verified": "Verified", "Partially True": "Partially True", "Stale": "Stale",
         "False": "False", "Unverified": "Unverified"}
EXAMPLES = {
    "Tech versions": "Python 3.9 is the latest stable release of Python. React 17 is the latest major release of React. Node.js 18 is currently an Active LTS release.",
    "AI API pricing": "GPT-4 Turbo is the latest model in the GPT-4 family. GPT-4 Turbo API pricing is $10 per million input tokens and $30 per million output tokens.",
    "Mixed 2026 claims": "Python 3.14 was released in 2025. React 17 is the latest major release of React. Node.js 24 is an Active LTS release.",
}
VIEWS = {
    "Dashboard": (":material/dashboard:", "Track, analyze and verify claims. Catch stale answers before they ship."),
    "Analytics": (":material/bar_chart:", "Freshness trends, verdict mix and model usage across every analysis."),
    "Claim Projects": (":material/folder:", "Group related audits — a docs page, a release note, a pricing table."),
    "Historical Data": (":material/history:", "Every claim ever checked, searchable and exportable."),
    "Settings": (":material/settings:", "Gateway, model, live search, profile and data."),
}
DEFAULT_MODELS = [("openai/gpt-4o", "GPT-4o"), ("anthropic/claude-3-5-sonnet-20241022", "Claude 3.5 Sonnet"),
                  ("gemini/gemini-1.5-pro", "Gemini 1.5 Pro")]
MAX_INPUT_CHARS = 8000

ICONS = {
    "pulse": '<path d="M2 12h4l3-8 4 16 3-8h6"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "alert": '<path d="M12 7v6M12 17h.01"/>',
    "x": '<path d="M18 6 6 18M6 6l12 12"/>',
    "hourglass": '<path d="M5 22h14M5 2h14M17 22v-4.17a2 2 0 0 0-.59-1.42L12 12l-4.41 4.41A2 2 0 0 0 7 17.83V22M7 2v4.17a2 2 0 0 0 .59 1.42L12 12l4.41-4.41A2 2 0 0 0 17 6.17V2"/>',
    "help": '<path d="M9.1 9a3 3 0 0 1 5.82 1c0 2-3 3-3 3M12 17h.01"/>',
    "shield": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
    "cpu": '<rect width="16" height="16" x="4" y="4" rx="2"/><rect width="6" height="6" x="9" y="9" rx="1"/><path d="M15 2v2M15 20v2M2 15h2M2 9h2M20 15h2M20 9h2M9 2v2M9 20v2"/>',
    "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "chart": '<path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
    "pie": '<path d="M21.21 15.89A10 10 0 1 1 8 2.83"/><path d="M22 12A10 10 0 0 0 12 2v10z"/>',
    "activity": '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    "zap": '<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/>',
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "gauge": '<path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/>',
    "chevron": '<path d="m9 18 6-6-6-6"/>',
    "globe": '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20M2 12h20"/>',
    "folder": '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
    "trend": '<path d="m22 7-8.5 8.5-5-5L2 17"/><path d="M16 7h6v6"/>',
}


def svg(name, cls="ico"):
    return f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden="true">{ICONS[name]}</svg>'


def esc(value):
    return html.escape(str(value if value is not None else ""))


def safe_url(url):
    parsed = urlparse(url or "")
    return url if parsed.scheme in {"http", "https"} and parsed.hostname else None


# ============================================================================ storage
DATA_DIR = Path(os.getenv("DATA_DIR", "").strip() or ROOT / "data")
STORE_PATH = DATA_DIR / "store.json"
_store_lock = threading.Lock()


def empty_store():
    return {"runs": [], "projects": [], "sessions": {}, "settings": {}}


def load_store():
    """Re-read on every script run so several sessions (and server.py) see each other's changes."""
    try:
        return {**empty_store(), **json.loads(STORE_PATH.read_text(encoding="utf-8"))}
    except FileNotFoundError:
        return empty_store()
    except (OSError, json.JSONDecodeError):
        return empty_store()


def update_store(mutate):
    """Read-modify-write under a process lock with an atomic file replace."""
    with _store_lock:
        data = load_store()
        mutate(data)
        STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = STORE_PATH.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
        tmp.replace(STORE_PATH)
        return data


def utcnow():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_iso(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def time_ago(value):
    seconds = max(0, (utcnow() - parse_iso(value)).total_seconds())
    if seconds < 45:
        return "just now"
    if seconds < 3600:
        return f"{round(seconds / 60)}m ago"
    if seconds < 86400:
        return f"{round(seconds / 3600)}h ago"
    if seconds < 86400 * 7:
        return f"{round(seconds / 86400)}d ago"
    return parse_iso(value).strftime("%d %b %Y")


def fmt_num(n):
    if n is None:
        return "—"
    if n >= 1_000_000:
        return f"{n / 1e6:.1f}".rstrip("0").rstrip(".") + "M"
    if n >= 10_000:
        return f"{n / 1e3:.1f}".rstrip("0").rstrip(".") + "K"
    return f"{n:,}"


def verdict_of(item):
    return item.get("verdict") or VERDICT_FROM_STATUS.get(item.get("status"), "Unverified")


def claim_rows(runs):
    for run in runs:
        for index, item in enumerate(run.get("results", [])):
            yield run, index, item


def compute_stats(data):
    """Same numbers the localhost:8000 dashboard shows."""
    now, runs, sessions = utcnow(), data["runs"], data["sessions"]
    rows = list(claim_rows(runs))
    counts = Counter(verdict_of(i) for _, _, i in rows)
    total = len(rows)

    def claims_between(start, end):
        return sum(len(r.get("results", [])) for r in runs if start <= parse_iso(r["created_at"]) < end)

    last24 = claims_between(now - timedelta(hours=24), now + timedelta(seconds=1))
    prev24 = claims_between(now - timedelta(hours=48), now - timedelta(hours=24))
    durations = [r["duration_ms"] for r in runs if r.get("duration_ms")]
    recent_d, older_d = durations[:10], durations[10:20]
    avg_response = round(sum(recent_d) / len(recent_d) / 1000, 1) if recent_d else None
    active = sum(parse_iso(v) > now - timedelta(hours=24) for v in sessions.values())
    active_prev = sum(now - timedelta(hours=48) < parse_iso(v) <= now - timedelta(hours=24) for v in sessions.values())

    start_hour = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=23)
    hourly = [{"slot": h, "hour": start_hour + timedelta(hours=h), "searches": 0, "failures": 0, "claims": 0}
              for h in range(24)]
    for r in runs:
        slot = int((parse_iso(r["created_at"]) - start_hour).total_seconds() // 3600)
        if 0 <= slot < 24:
            hourly[slot]["searches"] += r.get("search_successes", 0)
            hourly[slot]["failures"] += r.get("search_failures", 0)
            hourly[slot]["claims"] += len(r.get("results", []))

    days = [(now - timedelta(days=13 - d)).date() for d in range(14)]
    per_day = Counter(parse_iso(r["created_at"]).date() for r, _, _ in rows)
    running, cumulative = total - sum(per_day[d] for d in days), []
    for d in days:
        running += per_day[d]
        cumulative.append(running)
    day_scores = []
    for d in days:
        scores = [i.get("freshness_score", 0) for r, _, i in rows if parse_iso(r["created_at"]).date() == d]
        day_scores.append(round(sum(scores) / len(scores)) if scores else None)

    fresh = counts["Verified"] + counts["Partially True"]
    return {
        "total_claims": total, "total_runs": len(runs), "claims_24h": last24,
        "claims_trend_pct": None if prev24 == 0 else round((last24 - prev24) / prev24 * 100),
        "distribution": {v: counts[v] for v in VERDICTS},
        "freshness_rate": round(fresh / total * 100) if total else None,
        "avg_score": round(sum(i.get("freshness_score", 0) for _, _, i in rows) / total) if total else None,
        "avg_response_s": avg_response,
        "response_delta_s": round(avg_response - sum(older_d) / len(older_d) / 1000, 1) if recent_d and older_d else None,
        "active_users_24h": active,
        "active_users_trend_pct": None if active_prev == 0 else round((active - active_prev) / active_prev * 100),
        "hourly": hourly, "days": days, "cumulative": cumulative, "daily_claims": [per_day[d] for d in days],
        "daily_users": [sum(parse_iso(v).date() == d for v in sessions.values()) for d in days],
        "day_scores": day_scores,
        "response_series": [round(d / 1000, 1) for d in reversed(durations[:14])],
    }


# ============================================================================ access & state
security_cfg = SecurityConfig.from_env()
settings_env = get_settings()


def visitor_key():
    ip = getattr(st.context, "ip_address", None)
    if ip:
        return ip
    return "session:" + st.session_state["client_id"]


st.session_state.setdefault("client_id", uuid.uuid4().hex[:24])
st.session_state.setdefault("theme", "Dark")
st.session_state.setdefault("view", "Dashboard")
st.session_state.setdefault("profile", {"name": "Analyst", "role": "Local workspace"})
st.session_state.setdefault("claim_text", "")
st.session_state.setdefault("last_run_id", None)
st.session_state.setdefault("activity_metric", "Searches")
st.session_state.setdefault("alerts_seen", None)
if "role" not in st.session_state:
    st.session_state["role"] = role_for_token(security_cfg, "")

LIGHT = st.session_state["theme"] == "Light"


def is_admin():
    return st.session_state["role"] == ROLE_ADMIN


def model_label(model_id):
    parts = model_id.split("/")
    name, provider = parts[-1], (parts[0] if len(parts) > 1 else "")
    words = [t.upper() if t.lower() in {"gpt", "oss", "ai"} or (t[:-1].replace(".", "").isdigit() and t[-1:].lower() in "bkm")
             else t[:1].upper() + t[1:] for t in name.replace("_", "-").split("-")]
    pretty = " ".join(words) or model_id
    return f"{pretty} · {provider.title()}" if provider else pretty


def available_models():
    raw = os.getenv("AVAILABLE_MODELS", "").strip()
    models = []
    for part in raw.split(",") if raw else []:
        model_id, _, label = part.strip().partition(":")
        if model_id:
            models.append((model_id, label.strip() or model_label(model_id)))
    models = models or list(DEFAULT_MODELS)
    default = settings_env["model"]
    if default and default not in {m for m, _ in models}:
        models.insert(0, (default, model_label(default)))
    return models


# ============================================================================ styles
TOKENS_DARK = """--bg:#080B1A;--glow1:rgba(124,58,237,.16);--glow2:rgba(37,99,235,.12);--sidebar:#0B0E22;
--card:rgba(19,24,52,.72);--card-solid:#12173A;--card2:rgba(28,34,72,.55);--line:rgba(129,116,255,.16);
--line-strong:rgba(139,125,255,.34);--text:#F3F4FF;--text2:#C9CCE8;--muted:#8B90B8;--input:rgba(8,11,30,.65);
--shadow:0 18px 50px rgba(3,4,18,.45)"""
TOKENS_LIGHT = """--bg:#F4F5FB;--glow1:rgba(139,92,246,.10);--glow2:rgba(59,130,246,.08);--sidebar:#FFFFFF;
--card:#FFFFFF;--card-solid:#FFFFFF;--card2:#F5F6FC;--line:rgba(99,102,241,.16);--line-strong:rgba(124,58,237,.32);
--text:#141633;--text2:#33375E;--muted:#6B7096;--input:#FFFFFF;--shadow:0 14px 36px rgba(31,35,90,.08)"""

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root{{{TOKENS_LIGHT if LIGHT else TOKENS_DARK};--grad:linear-gradient(95deg,#7C3AED 0%,#8B5CF6 45%,#6366F1 100%);
--grad-soft:linear-gradient(105deg,rgba(124,58,237,.9),rgba(99,102,241,.85));--green:#22C55E;--amber:#F59E0B;--red:#EF4444}}
html,body,.stApp,.stMarkdown,p,label,input,textarea,button,h1,h2,h3{{font-family:'Inter',system-ui,sans-serif}}
.stApp{{background:radial-gradient(900px 520px at 78% -10%,var(--glow1),transparent 65%),
  radial-gradient(700px 480px at 30% 110%,var(--glow2),transparent 65%),var(--bg)!important;color:var(--text)}}
[data-testid="stHeader"]{{background:transparent}}[data-testid="stMainMenu"],[data-testid="stToolbar"] [data-testid="stToolbarActions"]{{display:none!important}}
.block-container{{max-width:1500px;padding:1.6rem 2rem 2.5rem}}
p,label,[data-testid="stCaptionContainer"]{{color:var(--muted)}}
.ico{{width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round;flex:0 0 auto}}

/* ---------- sidebar ---------- */
[data-testid="stSidebar"]{{background:var(--sidebar)!important;border-right:1px solid var(--line)}}
[data-testid="stSidebarContent"]{{padding-top:.6rem}}
.brand{{display:flex;align-items:center;gap:12px;padding:0 4px 18px}}
.brand-mark{{display:grid;place-items:center;width:40px;height:40px;border-radius:12px;color:#C4B5FD;
  background:linear-gradient(145deg,rgba(124,58,237,.32),rgba(99,102,241,.14));box-shadow:0 0 24px rgba(139,92,246,.35)}}
.brand-mark .ico{{width:24px;height:24px;stroke-width:2.4;filter:drop-shadow(0 0 4px rgba(167,139,250,.8))}}
.brand-name{{font-size:21px;font-weight:800;letter-spacing:-.02em;color:var(--text)}}
.brand-name span{{background:linear-gradient(90deg,#A78BFA,#818CF8);-webkit-background-clip:text;background-clip:text;color:transparent}}
.brand-tag{{font-size:11px;color:var(--muted)}}
/* radio styled as the nav list */
.st-key-nav [role="radiogroup"]{{gap:4px}}
.st-key-nav label[data-baseweb="radio"]{{margin:0;padding:11px 14px;border-radius:11px;border:1px solid transparent;width:100%;
  color:var(--muted);transition:background .18s,color .18s}}
.st-key-nav label[data-baseweb="radio"]>div:first-child{{display:none}}
.st-key-nav label[data-baseweb="radio"] p{{font-size:14px;font-weight:500;color:inherit!important}}
.st-key-nav label[data-baseweb="radio"]:hover{{background:var(--card2);color:var(--text)}}
.st-key-nav label[data-baseweb="radio"]:has(input:checked){{color:#fff;background:var(--grad-soft);border-color:rgba(167,139,250,.35);
  box-shadow:0 8px 26px rgba(124,58,237,.32)}}
.st-key-nav label[data-baseweb="radio"]:has(input:checked) p{{color:#fff!important}}
.side-card{{margin-top:18px;padding:16px;border:1px solid var(--line);border-radius:14px;background:linear-gradient(160deg,rgba(124,58,237,.16),var(--card))}}
.side-card-head{{display:flex;align-items:center;gap:8px;font-weight:600;font-size:13px;color:var(--text2)}}
.side-card-head .ico{{color:#FBBF24}}
.side-score{{display:flex;align-items:baseline;gap:6px;margin:10px 0 8px}}.side-score b{{font-size:26px;font-weight:800;color:var(--text)}}
.side-score small{{color:var(--muted);font-size:11px}}
.side-meter{{height:6px;border-radius:99px;background:var(--card2);overflow:hidden}}
.side-meter span{{display:block;height:100%;border-radius:inherit;background:linear-gradient(90deg,#F97316,#F59E0B,#22C55E)}}
.side-meta{{margin:8px 0 4px;font-size:11.5px;color:var(--muted)}}
.profile{{display:flex;align-items:center;gap:11px;margin-top:14px;padding:10px;border:1px solid var(--line);border-radius:13px;background:var(--card)}}
.avatar{{display:grid;place-items:center;width:36px;height:36px;flex:0 0 36px;border-radius:50%;background:var(--grad);color:#fff;font-weight:700}}
.profile b{{display:block;color:var(--text);font-size:13px}}.profile small{{color:var(--muted);font-size:11px}}

/* ---------- buttons ---------- */
.stButton>button,[data-testid="stDownloadButton"]>button,[data-testid="stFormSubmitButton"]>button{{border-radius:10px;
  border:1px solid var(--line);background:var(--card2);color:var(--text2);font-weight:600}}
.stButton>button:hover,[data-testid="stDownloadButton"]>button:hover{{border-color:var(--line-strong);color:var(--text)}}
button[data-testid^="stBaseButton-primary"]{{background:var(--grad)!important;color:#fff!important;border:0!important;box-shadow:0 8px 22px rgba(124,58,237,.3)}}
button[data-testid^="stBaseButton-primary"] p{{color:#fff!important}}
button:disabled{{opacity:.55!important}}

/* ---------- inputs ---------- */
[data-baseweb="textarea"],[data-baseweb="base-input"],[data-baseweb="input"]{{background:var(--input)!important;border-color:var(--line-strong)!important;border-radius:12px!important}}
textarea,[data-testid="stTextInput"] input{{color:var(--text)!important;background:var(--input)!important}}
textarea::placeholder,input::placeholder{{color:var(--muted)!important;opacity:1}}
[data-baseweb="textarea"]:focus-within,[data-baseweb="input"]:focus-within{{border-color:#8B5CF6!important;box-shadow:0 0 0 3px rgba(139,92,246,.18)}}
[data-baseweb="select"]>div{{background:var(--card2)!important;border-color:var(--line)!important;border-radius:10px!important;color:var(--text)!important}}
[data-baseweb="select"] *{{color:var(--text)!important}}
[data-baseweb="popover"] ul,[data-baseweb="popover"] [data-baseweb="menu"]{{background:var(--card-solid)!important;border:1px solid var(--line-strong)!important}}
[data-baseweb="popover"] li{{color:var(--text)!important}}
[data-baseweb="popover"] li:hover,[data-baseweb="popover"] li[aria-selected="true"]{{background:rgba(139,92,246,.18)!important}}

/* ---------- topbar ---------- */
.titles h1{{margin:0;font-size:28px;font-weight:800;letter-spacing:-.02em;color:var(--text);padding:0}}
.titles p{{margin:4px 0 0;color:var(--muted);font-size:14px}}
.st-key-topbar_actions{{display:flex;flex-direction:row!important;justify-content:flex-end;gap:8px}}
.st-key-topbar_actions [data-testid="stPopover"] button,.st-key-theme_switch button{{border-radius:12px;min-height:40px}}
.st-key-theme_switch button[data-testid="stBaseButton-segmented_controlActive"]{{background:var(--grad)!important;color:#fff!important;border-color:transparent!important}}
.st-key-theme_switch button[data-testid="stBaseButton-segmented_control"]{{background:var(--card)!important;color:var(--muted)!important;border-color:var(--line)!important}}

/* ---------- cards ---------- */
.st-key-analyze_card,[class*="st-key-panel_"],[class*="st-key-metric_"],.st-key-result_panel{{position:relative;
  border:1px solid var(--line);border-radius:16px;background:var(--card);box-shadow:var(--shadow);padding:18px!important;backdrop-filter:blur(14px)}}
.st-key-analyze_card{{border-color:rgba(139,92,246,.38);box-shadow:0 0 0 1px rgba(139,92,246,.28),0 0 42px rgba(124,58,237,.18),var(--shadow)}}
.st-key-analyze_card button[data-testid="stBaseButton-primaryFormSubmit"]{{min-height:58px;border-radius:14px!important;font-size:20px;
  box-shadow:0 10px 34px rgba(124,58,237,.38),inset 0 1px 0 rgba(255,255,255,.18)!important}}
.st-key-analyze_card button[data-testid="stBaseButton-primaryFormSubmit"] p{{font-size:20px!important;font-weight:600}}
.st-key-analyze_card [data-testid="stForm"]{{border:0;padding:0}}
.analyze-label{{margin:14px 0 2px;font-size:15px;font-weight:500;color:var(--text2)}}
[class*="st-key-chips_"] button{{border-radius:99px!important;min-height:30px!important;padding:2px 12px!important}}
[class*="st-key-chips_"] button p{{font-size:12px!important;white-space:nowrap}}
.chips-label{{font-size:12px;color:var(--muted);padding-top:6px}}
.panel-head{{display:flex;align-items:center;gap:9px;margin:0 0 12px;font-size:15px;font-weight:700;color:var(--text)}}
.panel-head .ico{{width:17px;height:17px;color:#A78BFA}}

/* status cards */
.status-card{{display:flex;align-items:center;gap:13px;min-height:70px;padding:12px 14px;border:1px solid var(--line);border-radius:13px;background:var(--card2)}}
.sc-icon{{display:grid;place-items:center;width:42px;height:42px;flex:0 0 42px;border-radius:11px}}
.sc-icon .ico{{width:21px;height:21px}}
.c-green{{color:#4ADE80;background:rgba(34,197,94,.16);box-shadow:inset 0 0 0 1px rgba(34,197,94,.3)}}
.c-teal{{color:#2DD4BF;background:rgba(20,184,166,.16);box-shadow:inset 0 0 0 1px rgba(20,184,166,.3)}}
.c-violet{{color:#A78BFA;background:rgba(139,92,246,.18);box-shadow:inset 0 0 0 1px rgba(139,92,246,.32)}}
.c-amber{{color:#FBBF24;background:rgba(245,158,11,.16);box-shadow:inset 0 0 0 1px rgba(245,158,11,.3)}}
.c-red{{color:#F87171;background:rgba(239,68,68,.16);box-shadow:inset 0 0 0 1px rgba(239,68,68,.3)}}
.sc-text small{{display:block;color:var(--muted);font-size:12px}}
.sc-text b{{font-size:15px;font-weight:700}}
.state{{display:inline-flex;align-items:center;gap:6px}}
.state::after{{content:"";width:7px;height:7px;border-radius:50%;background:currentColor;box-shadow:0 0 9px currentColor}}
.state.ok{{color:#4ADE80}}.state.warn{{color:#FBBF24}}.state.bad{{color:#F87171}}
.st-key-model_card{{gap:13px;min-height:70px;padding:8px 14px!important;border:1px solid var(--line);border-radius:13px;background:var(--card2)}}
.st-key-model_card>div:first-child{{width:auto!important;flex:0 0 auto}}
.st-key-model_card [data-testid="stSelectbox"]{{flex:1;min-width:0}}
.st-key-model_card [data-baseweb="select"]>div{{background:transparent!important;border:0!important;font-weight:700}}
.st-key-model_card label p{{font-size:12px!important;color:var(--muted)!important}}
/* whole-card click targets: an invisible button stretched over a keyed container */
[class*="st-key-click_"]{{position:relative}}
[class*="st-key-click_"] .stButton{{position:absolute;inset:0;z-index:3;margin:0}}
[class*="st-key-click_"] .stButton button{{width:100%;height:100%;opacity:0;cursor:pointer}}
[class*="st-key-click_"]:hover .status-card,[class*="st-key-click_"]:hover .recent-item{{border-color:var(--line-strong)}}

/* recent list */
.st-key-panel_recent [data-testid="stVerticalBlock"],[class*="st-key-panel_project"] [data-testid="stVerticalBlock"]{{gap:.2rem}}
[class*="st-key-click_"] [data-testid="stElementContainer"]{{margin:0}}
.st-key-link_viewall button{{background:transparent!important;border:0!important;box-shadow:none!important;min-height:30px;padding:0}}
.st-key-link_viewall button p{{color:#A78BFA!important;font-size:12.5px!important;font-weight:600;white-space:nowrap}}
.st-key-link_viewall button:hover p{{color:#C4B5FD!important}}
.recent-item{{display:flex;align-items:center;gap:12px;padding:9px 8px;border:1px solid transparent;border-radius:10px}}
[class*="st-key-click_recent"]:hover .recent-item{{background:var(--card2)}}
.v-dot{{display:grid;place-items:center;width:26px;height:26px;flex:0 0 26px;border-radius:50%;background:var(--vc);color:#fff;
  box-shadow:0 0 12px color-mix(in srgb,var(--vc) 55%,transparent)}}
.v-dot .ico{{width:14px;height:14px;stroke-width:2.8}}
.recent-text{{flex:1;min-width:0;display:flex;flex-direction:column}}
.recent-text b{{font-size:13px;font-weight:600;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.recent-text small{{font-size:11.5px;color:var(--vc);font-weight:500}}
.recent-time{{font-size:11.5px;color:var(--muted);white-space:nowrap}}
.recent-item>.ico{{width:15px;height:15px;color:var(--muted)}}
.v-verified{{--vc:#22C55E}}.v-partial{{--vc:#EAB308}}.v-stale{{--vc:#F97316}}.v-false{{--vc:#EF4444}}.v-unverified{{--vc:#7C86A8}}
.empty{{display:flex;flex-direction:column;align-items:center;gap:6px;padding:26px 10px;text-align:center;color:var(--muted);font-size:13px}}
.empty .ico{{width:30px;height:30px;color:#A78BFA}}.empty b{{color:var(--text2)}}

/* donut legend */
.legend{{list-style:none;margin:0;padding:6px 0 0;display:grid;gap:9px}}
.legend li{{display:flex;align-items:center;gap:9px;font-size:13px;color:var(--text2)}}
.legend .sw{{width:11px;height:11px;border-radius:50%;background:var(--vc);box-shadow:0 0 8px color-mix(in srgb,var(--vc) 60%,transparent)}}
.legend .lbl{{flex:1}}.legend .pct{{font-weight:600;color:var(--text)}}
.panel-foot{{margin-top:6px;font-size:12px;color:var(--muted)}}.panel-foot b{{color:var(--text2)}}

/* metrics */
.metric{{display:flex;align-items:center;gap:14px}}
.m-icon{{display:grid;place-items:center;width:42px;height:42px;flex:0 0 42px;border-radius:12px}}.m-icon .ico{{width:21px;height:21px}}
.m-body small{{display:block;color:var(--muted);font-size:12px}}.m-body em{{font-style:normal;opacity:.7}}
.m-body b{{display:block;font-size:26px;font-weight:800;letter-spacing:-.02em;color:var(--text);line-height:1.2}}
.m-trend{{font-size:12px;color:var(--muted)}}.trend-up{{color:#4ADE80;font-weight:600}}.trend-down{{color:#F87171;font-weight:600}}
.spark{{flex:1;min-width:60px;height:46px;overflow:visible}}

/* results */
.run-meta{{display:flex;gap:14px;flex-wrap:wrap;color:var(--muted);font-size:12px;margin:4px 0 10px}}
.run-input{{margin:10px 0;padding:12px 14px;border-left:3px solid #8B5CF6;border-radius:8px;background:var(--card2);color:var(--text2);font-size:13px;line-height:1.55;white-space:pre-wrap}}
.badge{{display:inline-flex;align-items:center;gap:5px;padding:3px 9px;border-radius:99px;font-size:11.5px;font-weight:600;color:var(--vc);
  background:color-mix(in srgb,var(--vc) 14%,transparent);border:1px solid color-mix(in srgb,var(--vc) 35%,transparent);margin-right:6px}}
.badge .ico{{width:12px;height:12px}}
.claim-card{{padding:16px;margin:10px 0;border:1px solid var(--line);border-left:3px solid var(--vc);border-radius:12px;background:var(--card2)}}
.claim-top{{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:8px}}
.claim-card h4{{margin:0 0 10px;font-size:14.5px;line-height:1.5;color:var(--text);padding:0}}
.score{{font-size:12px;color:var(--muted);white-space:nowrap}}.score b{{font-size:18px;color:var(--text)}}
.scorebar{{height:5px;border-radius:99px;background:rgba(124,134,168,.18);overflow:hidden;margin-bottom:12px}}
.scorebar span{{display:block;height:100%;border-radius:inherit;background:var(--vc)}}
.claim-grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px 18px}}.claim-grid .full{{grid-column:1/-1}}
.claim-grid dt{{font-size:10.5px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin-bottom:3px}}
.claim-grid dd{{margin:0;color:var(--text2);font-size:13px;line-height:1.55}}
.src{{margin:10px 0 0;padding:0;list-style:none;display:grid;gap:6px}}
.src li{{padding:8px 11px;border:1px solid var(--line);border-radius:9px;font-size:12.5px}}
.src a{{color:var(--text);font-weight:600;text-decoration:none}}.src a:hover{{color:#A78BFA}}
.src small{{display:block;color:var(--muted)}}
.kpi{{padding:16px 18px;border:1px solid var(--line);border-radius:16px;background:var(--card);box-shadow:var(--shadow)}}
.kpi small{{color:var(--muted);font-size:12px}}.kpi b{{display:block;margin:6px 0 2px;font-size:26px;font-weight:800;color:var(--text)}}
.kpi span{{font-size:12px;color:var(--muted)}}
.hbar-row{{display:grid;grid-template-columns:130px 1fr 54px;align-items:center;gap:10px;font-size:13px;margin:10px 0}}
.hbar-row .lbl{{color:var(--text2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.hbar-track{{height:10px;border-radius:99px;background:var(--card2);overflow:hidden}}
.hbar-track span{{display:block;height:100%;border-radius:inherit;background:var(--vc,var(--grad))}}
.hbar-row .val{{text-align:right;font-weight:600;color:var(--text)}}
.project-card h3{{display:flex;align-items:center;gap:8px;margin:0 0 4px;font-size:15px;color:var(--text);padding:0}}
.project-card h3 .ico{{color:#A78BFA}}.project-card p{{margin:0 0 10px;font-size:12.5px}}
.project-stats{{display:flex;gap:16px;font-size:12px;color:var(--muted)}}.project-stats b{{display:block;font-size:18px;color:var(--text)}}
.kv{{display:grid;grid-template-columns:max-content 1fr;gap:8px 16px;margin:0 0 12px;font-size:13px}}
.kv dt{{color:var(--muted)}}.kv dd{{margin:0;color:var(--text2);word-break:break-all}}
.offline{{display:flex;gap:10px;align-items:center;padding:10px 14px;margin-top:12px;border:1px solid rgba(239,68,68,.35);border-radius:12px;background:rgba(239,68,68,.08);color:var(--text2);font-size:13px}}
[data-testid="stExpander"]{{border-color:var(--line)!important;border-radius:12px;background:var(--card)}}
[data-testid="stDataFrame"]{{border:1px solid var(--line);border-radius:12px}}
[data-testid="stVegaLiteChart"]{{background:transparent}}

@media (max-width:760px){{
  .block-container{{padding:1rem .9rem 2rem}}
  .titles h1{{font-size:22px}}
  .claim-grid{{grid-template-columns:1fr}}
  .st-key-analyze_card button[data-testid="stBaseButton-primaryFormSubmit"] p{{font-size:17px!important}}
}}
</style>
""", unsafe_allow_html=True)

# ============================================================================ access gate
if st.session_state["role"] is None:
    st.markdown('<div class="titles"><h1>StaleBot</h1><p>This dashboard is private. Enter the access key you were given.</p></div>',
                unsafe_allow_html=True)
    with st.form("access_form"):
        key = st.text_input("Access key", type="password")
        if st.form_submit_button("Unlock", type="primary"):
            wait = limiter.hit([(f"dash-login:{visitor_key()}", 10, 600)])
            role = None if wait else role_for_token(security_cfg, key.strip())
            if wait:
                st.error(f"Too many attempts. Try again in {wait}s.")
            elif role:
                st.session_state["role"] = role
                st.rerun()
            else:
                st.error("That key was not accepted.")
    st.stop()

# ============================================================================ data for this run
DATA = load_store()


def touch_session():
    """Count this browser session as an active user (written at most every 5 minutes)."""
    cid, now = st.session_state["client_id"], utcnow()
    last = DATA["sessions"].get(cid)
    if last and now - parse_iso(last) < timedelta(minutes=5):
        return

    def mutate(d):
        d["sessions"][cid] = iso(now)
        cutoff = now - timedelta(days=30)
        d["sessions"] = {k: v for k, v in d["sessions"].items() if parse_iso(v) > cutoff}

    update_store(mutate)
    DATA["sessions"][cid] = iso(now)


touch_session()
STATS = compute_stats(DATA)
PROJECTS = DATA["projects"]
SELECTED_MODEL = DATA["settings"].get("model") or settings_env["model"]


def current_settings():
    return {**get_settings(), "model": SELECTED_MODEL}


@st.cache_data(ttl=60, show_spinner=False)
def shared_service_check(signature):
    """Tiny model call, at most once a minute, shared by all visitors (argument = cache key)."""
    return check_service({**get_settings(), "model": signature[0]})


def service_signature():
    return (SELECTED_MODEL,) + tuple((r["name"], r["base_url"]) for r in llm_routes(current_settings()))


if "service" not in st.session_state:
    st.session_state["service"] = shared_service_check(service_signature())
SERVICE = st.session_state["service"]


def recheck_service(force=False):
    wait = limiter.hit([(f"dash-probe:{visitor_key()}", 1, max(1, security_cfg.probe_cooldown_s))])
    if wait and not (force or is_admin()):
        st.toast(f"Checked a moment ago — try again in {wait}s.")
        return
    shared_service_check.clear()
    st.session_state["service"] = shared_service_check(service_signature())
    state = st.session_state["service"]["state"]
    st.toast({"connected": "Gateway connected and model responding.", "missing": "Model keys are not set up.",
              "unavailable": "The analysis service is offline."}.get(state, "Checked."))


# ============================================================================ widgets
def sparkline(values, color, uid):
    pts = [(i, v) for i, v in enumerate(values or []) if v is not None]
    if len(pts) < 2:
        return (f'<svg class="spark" viewBox="0 0 120 44" preserveAspectRatio="none"><line x1="0" y1="38" x2="120" y2="38" '
                f'stroke="{color}" stroke-opacity=".35" stroke-dasharray="3 4" stroke-width="1.5"/></svg>')
    xs = max(1, len(values) - 1)
    vals = [v for _, v in pts]
    lo, span = min(vals), (max(vals) - min(vals)) or 1
    coords = [((i / xs) * 120, 40 - ((v - lo) / span) * 34) for i, v in pts]
    line = " ".join(("M" if n == 0 else "L") + f"{x:.1f} {y:.1f}" for n, (x, y) in enumerate(coords))
    return (f'<svg class="spark" viewBox="0 0 120 44" preserveAspectRatio="none"><defs><linearGradient id="{uid}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{color}" stop-opacity=".35"/><stop offset="1" stop-color="{color}" stop-opacity="0"/></linearGradient></defs>'
            f'<path d="{line} L{coords[-1][0]:.1f} 44 L{coords[0][0]:.1f} 44 Z" fill="url(#{uid})"/>'
            f'<path d="{line}" fill="none" stroke="{color}" stroke-width="2" vector-effect="non-scaling-stroke" '
            f'style="filter:drop-shadow(0 0 4px {color})"/></svg>')


def trend_html(pct, invert=False, suffix="%", fallback=""):
    if pct is None:
        return f'<span class="m-trend">{esc(fallback)}</span>'
    good = pct <= 0 if invert else pct >= 0
    arrow = "↑" if pct >= 0 else "↓"
    return f'<span class="m-trend {"trend-up" if good else "trend-down"}">{arrow} {"+" if pct > 0 else ""}{pct}{suffix}</span>'


def badge(verdict):
    css, label, icon, _ = VERDICT_META[verdict]
    return f'<span class="badge {css}">{svg(icon)}{esc(label)}</span>'


def chart_config(chart):
    axis_color = "#8B90B8" if not LIGHT else "#6B7096"
    grid = "rgba(129,116,255,0.14)" if not LIGHT else "rgba(99,102,241,0.12)"
    return (chart.configure(background="transparent", font="Inter")
            .configure_view(strokeWidth=0)
            .configure_axis(labelColor=axis_color, titleColor=axis_color, gridColor=grid, domainColor=grid,
                            tickColor=grid, labelFontSize=10.5)
            .configure_legend(disable=True))


def run_by_id(run_id):
    return next((r for r in DATA["runs"] if r["id"] == run_id), None)


def render_run(run, flash=False):
    results = run.get("results", [])
    counts = Counter(verdict_of(r) for r in results)
    sources = sum(len(r.get("sources", [])) for r in results)
    project = next((p for p in PROJECTS if p["id"] == run.get("project_id")), None)
    title = f"{len(results)} claim{'s' if len(results) != 1 else ''} analyzed" if results else "No verifiable claims found"
    st.markdown(
        f'<div class="panel-head" style="font-size:16px">{esc(title)}</div>'
        f'<div class="run-meta"><span>🕒 {esc(parse_iso(run["created_at"]).astimezone().strftime("%d %b %Y, %H:%M"))}</span>'
        f'<span>🧠 {esc(run.get("model"))}</span><span>⚡ {run.get("duration_ms", 0) / 1000:.1f}s</span>'
        f'<span>🌐 {sources} sources · {run.get("search_successes", 0)} searches'
        + (f' ({run["search_failures"]} failed)' if run.get("search_failures") else "") + "</span>"
        + (f'<span>📁 {esc(project["name"])}</span>' if project else "") + "</div>"
        f'<div class="run-input">{esc(run.get("input_text"))}</div>'
        + "".join(badge(v).replace("</span>", f" · {counts[v]}</span>") for v in VERDICTS if counts[v]),
        unsafe_allow_html=True,
    )
    if run.get("claims_truncated"):
        st.caption(f"{run['claims_truncated']} more claim(s) were found but not checked — split long texts into smaller parts.")
    if not results:
        st.markdown('<div class="empty"><b>Nothing to verify</b>No factual, time-sensitive claims (versions, prices, releases, rules) were found.</div>',
                    unsafe_allow_html=True)
    for i, item in enumerate(results, start=1):
        verdict = verdict_of(item)
        css = VERDICT_META[verdict][0]
        src_items = []
        for s in item.get("sources", []):
            url = safe_url(s.get("url"))
            host = urlparse(url).hostname.removeprefix("www.") if url else ""
            date = (f"Published {s['published_date'][:10]}" if s.get("published_date")
                    else f"Dated {s['stated_date']} (from the page)" if s.get("stated_date") else "No date given")
            link = (f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(s.get("title") or host)} ↗</a>'
                    if url else f'<b>{esc(s.get("title") or "Source")}</b>')
            src_items.append(f"<li>{link}<small>{esc(host)}{' · ' if host else ''}{esc(date)}</small></li>")
        st.markdown(
            f'<div class="claim-card {css}"><div class="claim-top">{badge(verdict)}'
            f'<span class="score"><b>{int(item.get("freshness_score", 0))}</b> / 100 freshness</span></div>'
            f'<h4><span style="color:var(--muted)">#{i}</span> {esc(item.get("claim"))}</h4>'
            f'<div class="scorebar"><span style="width:{max(2, int(item.get("freshness_score", 0)))}%"></span></div>'
            '<dl class="claim-grid">'
            f'<div class="full"><dt>Current information</dt><dd>{esc(item.get("updated_fact"))}</dd></div>'
            f'<div><dt>Assessment</dt><dd>{esc(item.get("explanation"))}</dd></div>'
            f'<div><dt>Evidence analysis</dt><dd>{esc(item.get("evidence_analysis"))}</dd></div>'
            f'<div class="full"><dt>Recommended correction</dt><dd>{esc(item.get("recommended_correction"))}</dd></div></dl>'
            + (f'<ul class="src">{"".join(src_items)}</ul>' if src_items else '<div class="panel-foot">No source evidence was returned.</div>')
            + "</div>",
            unsafe_allow_html=True,
        )
    full, corrected = build_reports({**run, "created_at": parse_iso(run["created_at"]).astimezone().strftime("%Y-%m-%d %H:%M %Z")})
    c1, c2, _ = st.columns([1, 1, 2])
    c1.download_button("Full audit", full, f"stalebot-audit-{run['id']}.md", "text/markdown",
                       icon=":material/download:", use_container_width=True, key=f"dl_full_{run['id']}_{flash}")
    c2.download_button("Corrected summary", corrected, f"stalebot-corrected-{run['id']}.md", "text/markdown",
                       icon=":material/download:", use_container_width=True, key=f"dl_cor_{run['id']}_{flash}")


@st.dialog("Analysis details", width="large")
def show_run_dialog(run_id):
    run = run_by_id(run_id)
    if run:
        render_run(run)
    else:
        st.write("This analysis no longer exists.")


def recent_item_html(run, index, item, show_time=True):
    verdict = verdict_of(item)
    css, label, icon, _ = VERDICT_META[verdict]
    return (f'<div class="recent-item {css}"><span class="v-dot">{svg(icon)}</span>'
            f'<span class="recent-text"><b title="{esc(item["claim"])}">{esc(item["claim"])}</b>'
            f'<small>{esc(label)} · {int(item.get("freshness_score", 0))}/100</small></span>'
            + (f'<span class="recent-time">{esc(time_ago(run["created_at"]))}</span>' if show_time else "")
            + f'{svg("chevron")}</div>')


def clickable_claim(run, index, item, key_prefix):
    """A recent-analyses row: real HTML look, with an invisible button over it that opens details."""
    with st.container(key=f"click_{key_prefix}_{run['id']}_{index}"):
        st.markdown(recent_item_html(run, index, item), unsafe_allow_html=True)
        if st.button(f"Open details: {item['claim']}", key=f"btn_{key_prefix}_{run['id']}_{index}"):
            show_run_dialog(run["id"])


# ============================================================================ sidebar
with st.sidebar:
    st.markdown(f'<div class="brand"><span class="brand-mark">{svg("pulse")}</span><div>'
                '<div class="brand-name">Stale<span>Bot</span></div><div class="brand-tag">Stale-answer detector</div></div></div>',
                unsafe_allow_html=True)
    with st.container(key="nav"):
        st.radio("Navigation", list(VIEWS), key="view", label_visibility="collapsed",
                 format_func=lambda v: f"{VIEWS[v][0]}  {v}")

    health = STATS["avg_score"]
    stale_n = STATS["distribution"]["Stale"] + STATS["distribution"]["False"]
    st.markdown(
        f'<div class="side-card"><div class="side-card-head">{svg("gauge")}<span>Freshness Health</span></div>'
        f'<div class="side-score"><b>{health if health is not None else "—"}</b><small>/100 avg. score</small></div>'
        f'<div class="side-meter"><span style="width:{health or 0}%"></span></div>'
        f'<div class="side-meta">{f"{stale_n} stale or false of {fmt_num(STATS["total_claims"])} claims" if STATS["total_claims"] else "No claims analyzed yet"}</div></div>',
        unsafe_allow_html=True,
    )
    if st.button("Re-check systems", type="primary", icon=":material/refresh:", use_container_width=True):
        recheck_service()
        st.rerun()
    profile = st.session_state["profile"]
    initials = "".join(w[0] for w in profile["name"].split()[:2]).upper() or "A"
    st.markdown(f'<div class="profile"><span class="avatar">{esc(initials)}</span><span><b>{esc(profile["name"])}</b>'
                f'<small>{esc(profile["role"] or "Local workspace")}</small></span></div>', unsafe_allow_html=True)

# ============================================================================ topbar
VIEW = st.session_state["view"]
top_left, top_right = st.columns([5, 2], vertical_alignment="center")
with top_left:
    st.markdown(f'<div class="titles"><h1>{esc(VIEW)}</h1><p>{esc(VIEWS[VIEW][1])}</p></div>', unsafe_allow_html=True)
with top_right:
    with st.container(key="topbar_actions", horizontal=True, horizontal_alignment="right"):
        alerts = [(r, i, item) for r, i, item in claim_rows(DATA["runs"]) if verdict_of(item) in {"Stale", "False"}]
        seen = st.session_state["alerts_seen"]
        unseen = sum(1 for r, _, _ in alerts if not seen or r["created_at"] > seen)
        with st.popover(f"{unseen} new" if unseen else "Alerts", icon=":material/notifications:"):
            st.markdown("**Stale & false claims**")
            if not alerts:
                st.markdown(f'<div class="empty">{svg("check")}<b>All clear</b>No stale or false claims detected.</div>', unsafe_allow_html=True)
            for r, i, item in alerts[:8]:
                clickable_claim(r, i, item, "alert")
            if unseen:
                st.button("Mark all as read", key="alerts_read", use_container_width=True,
                          on_click=st.session_state.update, kwargs={"alerts_seen": iso(utcnow())})
        with st.container(key="theme_switch"):
            picked = st.segmented_control("Theme", ["Light", "Dark"], default=st.session_state["theme"],
                                          format_func=lambda t: ":material/light_mode:" if t == "Light" else ":material/dark_mode:",
                                          label_visibility="collapsed", key="theme_picker")
            if picked and picked != st.session_state["theme"]:
                st.session_state["theme"] = picked
                st.rerun()


# ============================================================================ dashboard page
def run_analysis(text, project_id):
    if not text.strip():
        st.toast("Enter a headline, claim or AI answer to verify.")
        return
    if len(text) > MAX_INPUT_CHARS:
        st.toast(f"Please keep it under {MAX_INPUT_CHARS:,} characters.")
        return
    if not is_admin():
        wait = limiter.hit([(f"dash-an-min:{visitor_key()}", security_cfg.analyze_limit_per_minute, 60),
                            (f"dash-an-hour:{visitor_key()}", security_cfg.analyze_limit_per_hour, 3600)])
        if wait:
            st.session_state["analysis_error"] = f"Analysis limit reached. Try again in {wait}s."
            return
    gate = concurrency_gate("dashboard-analyses", security_cfg.max_concurrent_analyses)
    if not gate.acquire(blocking=False):
        st.session_state["analysis_error"] = "StaleBot is busy with other analyses. Please try again shortly."
        return
    try:
        started = time.perf_counter()
        with st.status("Extracting claims…", expanded=True) as box:
            def progress(stage, index=None, total=None, claim=None):
                if stage == "extract":
                    st.write("🔍 Extracting the facts that can go out of date…")
                elif stage == "search":
                    box.update(label=f"Searching live sources ({index}/{total})…")
                    st.write(f"🌐 Searching: _{claim}_")
                elif stage == "score":
                    box.update(label=f"Scoring freshness ({index}/{total})…")
            result, error = analyze_text(text, current_settings(), progress=progress)
            box.update(label="Analysis complete" if not error else "Analysis failed",
                       state="complete" if not error else "error", expanded=False)
        duration_ms = round((time.perf_counter() - started) * 1000)
    finally:
        gate.release()
    if error:
        st.session_state["analysis_error"] = error
        if error in {ERR_OFFLINE, ERR_NOT_CONFIGURED}:
            shared_service_check.clear()
            st.session_state["service"] = {"state": "unavailable" if error == ERR_OFFLINE else "missing",
                                           "model_available": None, "provider": None}
        return
    run = {"id": uuid.uuid4().hex[:12], "created_at": iso(utcnow()), "input_text": text.strip(),
           "model": result.get("model_used") or SELECTED_MODEL, "provider": result.get("provider"),
           "duration_ms": duration_ms, "search_successes": result["search_successes"],
           "search_failures": result["search_failures"], "project_id": project_id or None,
           "client_id": st.session_state["client_id"], "claims_truncated": result.get("claims_truncated", 0),
           "results": result["results"]}
    update_store(lambda d: d["runs"].insert(0, run))
    st.session_state["last_run_id"] = run["id"]
    st.session_state["service"] = {"state": "connected", "model_available": True, "provider": result.get("provider")}
    if result["search_successes"] or result["search_failures"]:
        st.session_state["search_state"] = "failed" if result["search_failures"] and not result["search_successes"] else "active"
    n, bad = len(run["results"]), sum(verdict_of(r) in {"Stale", "False"} for r in run["results"])
    st.toast(f"Analyzed {n} claim{'s' if n != 1 else ''} in {duration_ms / 1000:.1f}s" + (f" — {bad} stale or false" if bad else "") + ".")


def use_example(text):
    st.session_state["claim_text"] = text


def page_dashboard():
    service_state = SERVICE.get("state")
    offline = service_state in {"unavailable", "missing"}
    with st.container(key="analyze_card"):
        with st.form("analyze_form", border=False):
            submitted = st.form_submit_button("Analyze Claim", type="primary", icon=":material/auto_fix_high:",
                                              use_container_width=True)
            st.markdown('<div class="analyze-label">Input News Headline, AI Answer or Claim to Verify</div>', unsafe_allow_html=True)
            st.text_area("Claim", key="claim_text", height=90, max_chars=MAX_INPUT_CHARS, label_visibility="collapsed",
                         placeholder="Enter specific claim details…")
        chip_cols = st.columns([1.1, 1.1, 1.1, 1.3, 2.6], vertical_alignment="center")
        chip_cols[0].markdown('<div class="chips-label">Try an example:</div>', unsafe_allow_html=True)
        for col, (label, text) in zip(chip_cols[1:4], EXAMPLES.items()):
            with col:
                with st.container(key=f"chips_{label.replace(' ', '_')}"):
                    st.button(label, key=f"chip_{label}", on_click=use_example, args=(text,), use_container_width=True)
        with chip_cols[4]:
            project_names = {"": "No project"} | {p["id"]: p["name"] for p in PROJECTS}
            st.selectbox("Save to project", list(project_names), format_func=project_names.get,
                         key="project_choice", label_visibility="collapsed")

        s1, s2, s3 = st.columns(3, gap="small")
        provider_groq = SERVICE.get("provider") == "groq"
        gw_text, gw_state, gw_icon = {
            "connected": ("Connected · Groq direct" if provider_groq else "Connected", "ok", "c-green"),
            "unavailable": ("Offline", "bad", "c-red"), "missing": ("Not set up", "warn", "c-amber"),
        }.get(service_state, ("Checking…", "warn", "c-amber"))
        with s1:
            with st.container(key="click_gateway"):
                st.markdown(f'<div class="status-card"><span class="sc-icon {gw_icon}">{svg("shield")}</span>'
                            f'<span class="sc-text"><small>Trusted Gateway Status</small><b class="state {gw_state}">{gw_text}</b></span></div>',
                            unsafe_allow_html=True)
                if st.button("Re-check the gateway", key="gateway_recheck"):
                    recheck_service()
                    st.rerun()
        with s2:
            with st.container(key="model_card", horizontal=True, vertical_alignment="center"):
                st.markdown(f'<span class="sc-icon c-teal">{svg("cpu")}</span>', unsafe_allow_html=True)
                models = available_models()
                ids = [m for m, _ in models]
                labels = dict(models)
                if SELECTED_MODEL not in ids:
                    ids.insert(0, SELECTED_MODEL)
                    labels[SELECTED_MODEL] = model_label(SELECTED_MODEL)
                choice = st.selectbox("Current AI Model", ids, index=ids.index(SELECTED_MODEL),
                                      format_func=lambda m: labels[m].replace(" (default)", ""),
                                      disabled=not is_admin(), key="model_select",
                                      help=None if is_admin() else "Admin only — enter the admin key in Settings.")
                if choice != SELECTED_MODEL and is_admin():
                    update_store(lambda d: d["settings"].__setitem__("model", choice))
                    shared_service_check.clear()
                    st.session_state["service"] = check_service({**get_settings(), "model": choice})
                    state = st.session_state["service"]
                    st.toast(f"Switched to {labels[choice]}" + (" — model is responding." if state.get("model_available") else
                             " — the gateway rejected it." if state.get("model_available") is False else " — gateway unreachable."))
                    st.rerun()
        search_state = st.session_state.get("search_state", "ready" if settings_env["tavily_api_key"] else "missing")
        sr_text, sr_state, sr_icon = {"active": ("Active", "ok", "c-violet"), "ready": ("Ready", "ok", "c-violet"),
                                      "failed": ("Failing", "bad", "c-red"), "missing": ("Not configured", "warn", "c-amber")}[search_state]
        with s3:
            st.markdown(f'<div class="status-card"><span class="sc-icon {sr_icon}">{svg("search")}</span>'
                        f'<span class="sc-text"><small>Live Source Search</small><b class="state {sr_state}">{sr_text}</b></span></div>',
                        unsafe_allow_html=True)
        if offline:
            st.markdown(f'<div class="offline">⚠️ {"The analysis service is offline right now — Analyze will re-check it first." if service_state == "unavailable" else "StaleBot is not set up yet: the model keys are missing."}</div>',
                        unsafe_allow_html=True)

    if submitted:
        st.session_state.pop("analysis_error", None)
        if offline and service_state == "unavailable":
            recheck_service(force=True)
        if st.session_state["service"].get("state") in {"unavailable", "missing"}:
            st.session_state["analysis_error"] = (ERR_NOT_CONFIGURED if st.session_state["service"]["state"] == "missing"
                                                  else ERR_OFFLINE)
        else:
            run_analysis(st.session_state["claim_text"], st.session_state.get("project_choice"))
        st.rerun()

    if st.session_state.get("analysis_error"):
        st.error(st.session_state["analysis_error"])
    last = run_by_id(st.session_state["last_run_id"]) if st.session_state["last_run_id"] else None
    if last:
        with st.container(key="result_panel"):
            render_run(last, flash=True)

    st.write("")
    g1, g2, g3 = st.columns(3, gap="medium")
    with g1:
        with st.container(key="panel_recent"):
            head_l, head_r = st.columns([1.7, 1], vertical_alignment="center")
            head_l.markdown(f'<div class="panel-head" style="margin:0">{svg("chart")}Recent Analyses</div>', unsafe_allow_html=True)
            with head_r:
                with st.container(key="link_viewall"):
                    st.button("View All →", key="view_all", use_container_width=True,
                              on_click=st.session_state.update, kwargs={"view": "Historical Data"})
            rows = list(claim_rows(DATA["runs"]))[:5]
            if not rows:
                st.markdown(f'<div class="empty">{svg("search")}<b>No analyses yet</b>Your verified claims will appear here.</div>',
                            unsafe_allow_html=True)
            for r, i, item in rows:
                clickable_claim(r, i, item, "recent")
    with g2:
        with st.container(key="panel_overview"):
            st.markdown(f'<div class="panel-head">{svg("pie")}Claim Verification Overview</div>', unsafe_allow_html=True)
            donut_col, legend_col = st.columns([1, 1.05], vertical_alignment="center")
            with donut_col:
                st.altair_chart(donut_chart(), use_container_width=True, theme=None)
            total = STATS["total_claims"]
            with legend_col:
                items = "".join(
                    f'<li class="{VERDICT_META[v][0]}"><span class="sw"></span><span class="lbl">{SHORT[v]}</span>'
                    f'<span class="pct">{round(STATS["distribution"][v] / total * 100) if total else 0}%</span></li>' for v in VERDICTS)
                st.markdown(f'<ul class="legend">{items}</ul>', unsafe_allow_html=True)
            st.markdown('<div class="panel-foot">' + (
                f'Freshness rate (verified + partially true) across <b>{fmt_num(total)}</b> claims · avg. score <b>{STATS["avg_score"]}</b>/100'
                if total else "Analyze a claim to see the verdict mix.") + "</div>", unsafe_allow_html=True)
    with g3:
        with st.container(key="panel_activity"):
            head_l, head_r = st.columns([1.2, 1], vertical_alignment="center")
            head_l.markdown(f'<div class="panel-head" style="margin:0">{svg("activity")}Live Source Search Activity</div>',
                            unsafe_allow_html=True)
            head_r.selectbox("Metric", ["Searches", "Claims"], key="activity_metric", label_visibility="collapsed",
                             help="Per hour, last 24 hours")
            st.altair_chart(activity_chart(), use_container_width=True, theme=None)

    m1, m2, m3 = st.columns(3, gap="medium")
    metrics = [
        (m1, "zap", "c-amber", "Total Claims Analyzed", fmt_num(STATS["total_claims"]),
         trend_html(STATS["claims_trend_pct"], fallback=f"+{STATS['claims_24h']} in last 24h" if STATS["claims_24h"] else "No claims in last 24h"),
         sparkline(STATS["cumulative"], "#22C55E", "gTotal")),
        (m2, "users", "c-violet", "Active Users <em>· 24h</em>", fmt_num(STATS["active_users_24h"]),
         trend_html(STATS["active_users_trend_pct"], fallback="unique browsers"), sparkline(STATS["daily_users"], "#8B5CF6", "gUsers")),
        (m3, "clock", "c-teal", "Avg. Response Time", f"{STATS['avg_response_s']}s" if STATS["avg_response_s"] is not None else "—",
         trend_html(STATS["response_delta_s"], invert=True, suffix="s",
                    fallback="last 10 analyses" if STATS["avg_response_s"] is not None else "No analyses yet"),
         sparkline(STATS["response_series"], "#22D3EE", "gResp")),
    ]
    for col, icon, color, label, value, trend, spark in metrics:
        with col:
            with st.container(key=f"metric_{icon}"):
                st.markdown(f'<div class="metric"><span class="m-icon {color}">{svg(icon)}</span><div class="m-body">'
                            f'<small>{label}</small><b>{value}</b>{trend}</div>{spark}</div>', unsafe_allow_html=True)


def donut_chart():
    total = STATS["total_claims"]
    if total:
        df = pd.DataFrame([{"verdict": v, "count": STATS["distribution"][v], "label": VERDICT_META[v][1],
                            "pct": f'{round(STATS["distribution"][v] / total * 100)}%'} for v in VERDICTS if STATS["distribution"][v]])
        colors = [VERDICT_META[v][3] for v in df["verdict"]]
    else:
        df = pd.DataFrame([{"verdict": "none", "count": 1, "label": "No claims yet", "pct": "—"}])
        colors = ["#2A2F55" if not LIGHT else "#E5E7F5"]
    ring = alt.Chart(df).mark_arc(innerRadius=58, outerRadius=76, padAngle=0.02, cornerRadius=2).encode(
        theta=alt.Theta("count:Q", stack=True),
        color=alt.Color("verdict:N", scale=alt.Scale(domain=list(df["verdict"]), range=colors), legend=None),
        order=alt.Order("count:Q", sort="descending"),
        tooltip=[alt.Tooltip("label:N", title="Verdict"), alt.Tooltip("count:Q", title="Claims"), alt.Tooltip("pct:N", title="Share")],
    )
    center = pd.DataFrame([{"big": f"{STATS['freshness_rate']}%" if STATS["freshness_rate"] is not None else "—", "small": "fresh"}])
    text_color = "#F3F4FF" if not LIGHT else "#141633"
    big = alt.Chart(center).mark_text(fontSize=28, fontWeight=800, color=text_color, dy=-6).encode(text="big:N")
    small = alt.Chart(center).mark_text(fontSize=11, color="#8B90B8", dy=16).encode(text="small:N")
    return chart_config(alt.layer(ring, big, small).properties(height=170))


def activity_chart():
    hourly = STATS["hourly"]
    metric = "searches" if st.session_state["activity_metric"].startswith("Searches") else "claims"
    labels = [("Now" if h["slot"] == 23 else h["hour"].astimezone().strftime("%-I%p" if os.name != "nt" else "%#I%p"))
              if h["slot"] in {0, 6, 12, 18, 23} else "" for h in hourly]
    df = pd.DataFrame([{
        "slot": h["slot"], "value": h[metric], "searches": h["searches"], "claims": h["claims"], "failures": h["failures"],
        "range": f'{h["hour"].astimezone().strftime("%H:%M")}–{(h["hour"] + timedelta(hours=1)).astimezone().strftime("%H:%M")}',
        "current": h["slot"] == 23} for h in hourly])
    top = max(4, int(df["value"].max() or 0))
    gradient = alt.Gradient(gradient="linear", x1=1, x2=1, y1=0, y2=1,
                            stops=[alt.GradientStop(color="#22D3EE", offset=0), alt.GradientStop(color="#3B82F6", offset=0.7),
                                   alt.GradientStop(color="rgba(59,130,246,0.45)", offset=1)])
    current = alt.Gradient(gradient="linear", x1=1, x2=1, y1=0, y2=1,
                           stops=[alt.GradientStop(color="#C4B5FD", offset=0), alt.GradientStop(color="#8B5CF6", offset=1)])
    x = alt.X("slot:O", title=None, axis=alt.Axis(labelExpr=f"{json.dumps(labels)}[datum.value]", labelAngle=0,
                                                   ticks=False, domain=True, grid=False))
    y = alt.Y("value:Q", title=None, scale=alt.Scale(domain=[0, top]), axis=alt.Axis(tickCount=4, grid=True, domain=False, ticks=False))
    tooltip = [alt.Tooltip("range:N", title="Hour"), alt.Tooltip("searches:Q", title="Live searches"),
               alt.Tooltip("claims:Q", title="Claims analyzed"), alt.Tooltip("failures:Q", title="Failed searches")]
    bars = alt.Chart(df).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color=gradient).encode(
        x=x, y=y, tooltip=tooltip).transform_filter("!datum.current")
    now_bar = alt.Chart(df).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color=current).encode(
        x=x, y=y, tooltip=tooltip).transform_filter("datum.current")
    floor = alt.Chart(df).mark_tick(color="rgba(124,134,168,0.35)", thickness=2, size=8).encode(x=x, y=alt.Y("zero:Q", scale=alt.Scale(domain=[0, top]))).transform_calculate(zero="0")
    layers = [bars, now_bar, floor]
    if df["value"].sum() == 0:
        note = pd.DataFrame([{"slot": 11, "y": top / 2, "t": "No live searches in the last 24h" if metric == "searches" else "No claims in the last 24h"}])
        layers.append(alt.Chart(note).mark_text(color="#8B90B8", fontSize=12).encode(x=alt.X("slot:O"), y=alt.Y("y:Q"), text="t:N"))
    return chart_config(alt.layer(*layers).properties(height=190))


# ============================================================================ analytics page
def page_analytics():
    s = STATS
    stale = s["distribution"]["Stale"] + s["distribution"]["False"]
    searches = sum(r.get("search_successes", 0) for r in DATA["runs"])
    kpis = [("Avg. freshness score", f"{s['avg_score']}/100" if s["avg_score"] is not None else "—", "mean of all claim scores"),
            ("Stale or false rate", f"{round(stale / s['total_claims'] * 100)}%" if s["total_claims"] else "—", f"{stale} of {fmt_num(s['total_claims'])} claims"),
            ("Analyses run", fmt_num(s["total_runs"]), f"{fmt_num(s['total_claims'])} claims extracted"),
            ("Live searches", fmt_num(searches), "Tavily queries completed")]
    for col, (label, value, sub) in zip(st.columns(4, gap="medium"), kpis):
        col.markdown(f'<div class="kpi"><small>{label}</small><b>{value}</b><span>{sub}</span></div>', unsafe_allow_html=True)
    st.write("")
    a, b = st.columns(2, gap="medium")
    days = [datetime.combine(d, datetime.min.time()) for d in s["days"]]
    with a:
        with st.container(key="panel_score"):
            st.markdown(f'<div class="panel-head">{svg("trend")}Average Freshness Score · 14 days</div>', unsafe_allow_html=True)
            df = pd.DataFrame({"day": days, "score": s["day_scores"]}).dropna()
            if df.empty:
                st.markdown('<div class="empty"><b>No scored claims in the last 14 days</b></div>', unsafe_allow_html=True)
            else:
                line = alt.Chart(df).mark_line(strokeWidth=2.5, color="#8B5CF6", point=alt.OverlayMarkDef(size=60, color="#8B5CF6")).encode(
                    x=alt.X("day:T", title=None, axis=alt.Axis(format="%d %b", grid=False)),
                    y=alt.Y("score:Q", title=None, scale=alt.Scale(domain=[0, 100])),
                    tooltip=[alt.Tooltip("day:T", title="Day", format="%a %d %b"), alt.Tooltip("score:Q", title="Avg. freshness")])
                st.altair_chart(chart_config(line.properties(height=230)), use_container_width=True, theme=None)
    with b:
        with st.container(key="panel_daily"):
            st.markdown(f'<div class="panel-head">{svg("chart")}Claims per Day · 14 days</div>', unsafe_allow_html=True)
            df = pd.DataFrame({"day": days, "claims": s["daily_claims"]})
            bars = alt.Chart(df).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color="#6366F1").encode(
                x=alt.X("day:T", title=None, axis=alt.Axis(format="%d %b", grid=False)),
                y=alt.Y("claims:Q", title=None, scale=alt.Scale(domainMin=0, nice=True), axis=alt.Axis(tickMinStep=1)),
                tooltip=[alt.Tooltip("day:T", title="Day", format="%a %d %b"), alt.Tooltip("claims:Q", title="Claims")])
            st.altair_chart(chart_config(bars.properties(height=230)), use_container_width=True, theme=None)
    c, d = st.columns(2, gap="medium")
    total = s["total_claims"] or 1
    with c:
        with st.container(key="panel_verdicts"):
            rows = "".join(f'<div class="hbar-row {VERDICT_META[v][0]}"><span class="lbl">{VERDICT_META[v][1]}</span>'
                           f'<span class="hbar-track"><span style="width:{s["distribution"][v] / total * 100}%"></span></span>'
                           f'<span class="val">{s["distribution"][v]}</span></div>' for v in VERDICTS)
            st.markdown(f'<div class="panel-head">{svg("pie")}Verdict Breakdown</div>{rows}', unsafe_allow_html=True)
    with d:
        with st.container(key="panel_models"):
            usage = Counter(r.get("model") for r in DATA["runs"])
            top = max(usage.values(), default=1)
            rows = "".join(f'<div class="hbar-row"><span class="lbl" title="{esc(m)}">{esc(model_label(m or "unknown"))}</span>'
                           f'<span class="hbar-track"><span style="width:{n / top * 100}%;background:var(--grad)"></span></span>'
                           f'<span class="val">{n}</span></div>' for m, n in usage.most_common())
            st.markdown(f'<div class="panel-head">{svg("cpu")}Model Usage</div>'
                        + (rows or '<div class="empty"><b>No model usage yet</b></div>'), unsafe_allow_html=True)


# ============================================================================ projects page
def page_projects():
    with st.container(key="panel_newproject"):
        with st.form("new_project", clear_on_submit=True, border=False):
            c1, c2, c3 = st.columns([2, 3, 1.2], vertical_alignment="bottom")
            name = c1.text_input("Project name", placeholder="e.g. Q4 pricing page audit", max_chars=80, disabled=not is_admin())
            desc = c2.text_input("Description", placeholder="Short description (optional)", max_chars=300, disabled=not is_admin())
            created = c3.form_submit_button("Create project", type="primary", icon=":material/add:",
                                            use_container_width=True, disabled=not is_admin())
        if not is_admin():
            st.caption("Creating and deleting projects is admin only — enter the admin key in Settings.")
        if created and name.strip():
            project = {"id": uuid.uuid4().hex[:10], "name": name.strip(), "description": desc.strip(), "created_at": iso(utcnow())}
            update_store(lambda d: d["projects"].append(project))
            st.session_state["open_project"] = project["id"]
            st.toast(f"Project “{project['name']}” created.")
            st.rerun()
    st.write("")
    if not PROJECTS:
        st.markdown(f'<div class="empty">{svg("folder")}<b>No projects yet</b>Create one above, then pick it under the claim input so new analyses are filed there.</div>',
                    unsafe_allow_html=True)
        return
    counts = Counter(r.get("project_id") for r in DATA["runs"])
    claim_counts, stale_counts = Counter(), Counter()
    for r, _, item in claim_rows(DATA["runs"]):
        claim_counts[r.get("project_id")] += 1
        stale_counts[r.get("project_id")] += verdict_of(item) in {"Stale", "False"}
    cols = st.columns(3, gap="medium")
    for n, p in enumerate(PROJECTS):
        with cols[n % 3]:
            with st.container(key=f"panel_project_{p['id']}"):
                st.markdown(f'<div class="project-card"><h3>{svg("folder")}{esc(p["name"])}</h3><p>{esc(p.get("description") or "No description")}</p>'
                            f'<div class="project-stats"><span><b>{counts[p["id"]]}</b>analyses</span><span><b>{claim_counts[p["id"]]}</b>claims</span>'
                            f'<span><b style="color:{"#F97316" if stale_counts[p["id"]] else "inherit"}">{stale_counts[p["id"]]}</b>stale / false</span></div></div>',
                            unsafe_allow_html=True)
                b1, b2 = st.columns(2)
                if b1.button("Open", key=f"open_{p['id']}", use_container_width=True):
                    st.session_state["open_project"] = p["id"]
                    st.rerun()
                if b2.button("Delete", key=f"del_{p['id']}", icon=":material/delete:", use_container_width=True, disabled=not is_admin()):
                    st.session_state["confirm_delete_project"] = p["id"]
                if st.session_state.get("confirm_delete_project") == p["id"]:
                    st.warning("Delete this project? Its analyses stay in Historical Data, unassigned.")
                    y, nb = st.columns(2)
                    if y.button("Yes, delete", key=f"yes_{p['id']}", type="primary", use_container_width=True):
                        def mutate(d, pid=p["id"]):
                            d["projects"] = [x for x in d["projects"] if x["id"] != pid]
                            for r in d["runs"]:
                                if r.get("project_id") == pid:
                                    r["project_id"] = None
                        update_store(mutate)
                        st.session_state.pop("confirm_delete_project", None)
                        st.rerun()
                    if nb.button("Cancel", key=f"no_{p['id']}", use_container_width=True):
                        st.session_state.pop("confirm_delete_project", None)
                        st.rerun()
    pid = st.session_state.get("open_project")
    project = next((p for p in PROJECTS if p["id"] == pid), None)
    if project:
        st.write("")
        with st.container(key="panel_projectdetail"):
            st.markdown(f'<div class="panel-head">{svg("folder")}{esc(project["name"])} · claims</div>', unsafe_allow_html=True)
            rows = [(r, i, item) for r, i, item in claim_rows(DATA["runs"]) if r.get("project_id") == pid]
            if not rows:
                st.markdown(f'<div class="empty">{svg("search")}<b>No claims in this project yet</b>Pick it in the Dashboard project selector, or assign analyses in Historical Data.</div>',
                            unsafe_allow_html=True)
            for r, i, item in rows:
                clickable_claim(r, i, item, "project")


# ============================================================================ history page
def page_history():
    with st.container(key="panel_history"):
        f1, f2, f3, f4 = st.columns([2.4, 1.3, 1.3, 1], vertical_alignment="bottom")
        query = f1.text_input("Search", placeholder="Search claims…", label_visibility="collapsed", key="h_query").strip().lower()
        verdict = f2.selectbox("Verdict", ["All verdicts"] + VERDICTS, label_visibility="collapsed", key="h_verdict",
                               format_func=lambda v: v if v == "All verdicts" else VERDICT_META[v][1])
        names = {"": "All projects"} | {p["id"]: p["name"] for p in PROJECTS}
        project = f3.selectbox("Project", list(names), format_func=names.get, label_visibility="collapsed", key="h_project")
        records = []
        for r, i, item in claim_rows(DATA["runs"]):
            v = verdict_of(item)
            if verdict != "All verdicts" and v != verdict:
                continue
            if project and r.get("project_id") != project:
                continue
            if query and query not in item["claim"].lower() and query not in r["input_text"].lower():
                continue
            records.append({"When": parse_iso(r["created_at"]).astimezone().strftime("%Y-%m-%d %H:%M"), "Claim": item["claim"],
                            "Verdict": VERDICT_META[v][1], "Score": int(item.get("freshness_score", 0)),
                            "Model": (r.get("model") or "").split("/")[-1],
                            "Project": next((p["name"] for p in PROJECTS if p["id"] == r.get("project_id")), "—"),
                            "Current information": item.get("updated_fact", ""), "run_id": r["id"]})
        df = pd.DataFrame(records)
        f4.download_button("Export CSV", (df.drop(columns=["run_id"]) if not df.empty else df).to_csv(index=False),
                           f"stalebot-claims-{utcnow():%Y-%m-%d}.csv", "text/csv", icon=":material/download:",
                           use_container_width=True, disabled=df.empty)
        if df.empty:
            st.markdown(f'<div class="empty">{svg("clock")}<b>No matching claims</b>'
                        f'{"Try clearing the filters." if (query or project or verdict != "All verdicts") else "Run an analysis from the Dashboard."}</div>',
                        unsafe_allow_html=True)
            return
        event = st.dataframe(
            df.drop(columns=["run_id"]), hide_index=True, use_container_width=True, on_select="rerun",
            selection_mode="single-row", key="history_table",
            column_config={"Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d"),
                           "Claim": st.column_config.TextColumn(width="large")})
        st.caption(f"{len(df)} claim{'s' if len(df) != 1 else ''} · select a row to open, assign or delete it")
        selected = event.selection.rows if event and event.selection else []
        if selected:
            run_id = df.iloc[selected[0]]["run_id"]
            run = run_by_id(run_id)
            a1, a2, a3 = st.columns([1, 1.6, 1], vertical_alignment="bottom")
            if a1.button("Open details", icon=":material/open_in_new:", use_container_width=True):
                show_run_dialog(run_id)
            pnames = {"": "No project"} | {p["id"]: p["name"] for p in PROJECTS}
            target = a2.selectbox("Assign to project", list(pnames), format_func=pnames.get,
                                  index=list(pnames).index(run.get("project_id") or ""), disabled=not is_admin(), key=f"assign_{run_id}")
            if is_admin() and target != (run.get("project_id") or ""):
                update_store(lambda d: next(x for x in d["runs"] if x["id"] == run_id).__setitem__("project_id", target or None))
                st.toast("Analysis moved." if target else "Removed from project.")
                st.rerun()
            if a3.button("Delete analysis", icon=":material/delete:", use_container_width=True, disabled=not is_admin()):
                update_store(lambda d: d.__setitem__("runs", [x for x in d["runs"] if x["id"] != run_id]))
                if st.session_state["last_run_id"] == run_id:
                    st.session_state["last_run_id"] = None
                st.toast("Analysis deleted.")
                st.rerun()


# ============================================================================ settings page
def page_settings():
    cfg_settings = current_settings()
    left, right = st.columns(2, gap="medium")
    with left:
        with st.container(key="panel_gateway"):
            state = SERVICE.get("state")
            yes = lambda b: '<span class="state ok">Configured</span>' if b else '<span class="state warn">Missing</span>'
            st.markdown(
                f'<div class="panel-head">{svg("shield")}AI Gateway (Bifrost)</div><dl class="kv">'
                f'<dt>Base URL</dt><dd>{esc(cfg_settings["base_url"]) if is_admin() else "Hidden (admin only)"}</dd>'
                f'<dt>Virtual key</dt><dd>{yes(cfg_settings["virtual_key"])}</dd>'
                f'<dt>Groq fallback</dt><dd>{yes(cfg_settings["groq_api_key"])}</dd>'
                f'<dt>Status</dt><dd>{esc({"connected": "Connected" + (" · Groq direct" if SERVICE.get("provider") == "groq" else ""), "unavailable": "Offline", "missing": "Not set up"}.get(state, "Not checked"))}</dd>'
                f'<dt>Selected model</dt><dd>{esc(SELECTED_MODEL)}</dd></dl>', unsafe_allow_html=True)
            if st.button("Test connection", type="primary", icon=":material/refresh:"):
                recheck_service()
                st.rerun()
        with st.container(key="panel_access"):
            role = st.session_state["role"]
            st.markdown(
                f'<div class="panel-head">{svg("shield")}Access</div><dl class="kv">'
                f'<dt>Your role</dt><dd>{"Admin" + (" (local development — no key needed)" if security_cfg.open_admin else "") if role == ROLE_ADMIN else "Viewer"}</dd>'
                f'<dt>Server mode</dt><dd>{"Production" if security_cfg.production else "Development"}</dd>'
                f'<dt>Analysis limit</dt><dd>{security_cfg.analyze_limit_per_minute}/min · {security_cfg.analyze_limit_per_hour}/hour (admins exempt)</dd>'
                f'<dt>Claims per check</dt><dd>Up to {cfg_settings["max_claims"]}</dd></dl>', unsafe_allow_html=True)
            if not is_admin():
                with st.form("admin_key", border=False):
                    key = st.text_input("Admin key", type="password")
                    if st.form_submit_button("Unlock admin", type="primary"):
                        wait = limiter.hit([(f"dash-admin:{visitor_key()}", 10, 600)])
                        if not wait and role_for_token(security_cfg, key.strip()) == ROLE_ADMIN:
                            st.session_state["role"] = ROLE_ADMIN
                            st.rerun()
                        st.error(f"Too many attempts. Try again in {wait}s." if wait else "That key was not accepted.")
    with right:
        with st.container(key="panel_search"):
            st.markdown(f'<div class="panel-head">{svg("globe")}Live Source Search (Tavily)</div><dl class="kv">'
                        f'<dt>Provider</dt><dd>Tavily (advanced depth, 3 results / claim)</dd>'
                        f'<dt>API key</dt><dd>{"Configured" if cfg_settings["tavily_api_key"] else "Missing"}</dd></dl>'
                        '<div class="panel-foot">API keys are read from .env / Streamlit secrets on the server and never shown here.</div>',
                        unsafe_allow_html=True)
        with st.container(key="panel_profile"):
            st.markdown(f'<div class="panel-head">👤 Profile</div>', unsafe_allow_html=True)
            with st.form("profile", border=False):
                name = st.text_input("Display name", value=st.session_state["profile"]["name"], max_chars=40)
                role_text = st.text_input("Role / team", value=st.session_state["profile"]["role"], max_chars=40)
                if st.form_submit_button("Save profile", type="primary"):
                    st.session_state["profile"] = {"name": name.strip() or "Analyst", "role": role_text.strip()}
                    st.toast("Profile saved.")
                    st.rerun()
        with st.container(key="panel_data"):
            st.markdown(f'<div class="panel-head">⚙️ Data</div><dl class="kv"><dt>Storage</dt><dd>{esc(STORE_PATH) if is_admin() else "Hidden (admin only)"}</dd>'
                        f'<dt>Analyses</dt><dd>{fmt_num(STATS["total_runs"])} runs · {fmt_num(STATS["total_claims"])} claims</dd></dl>',
                        unsafe_allow_html=True)
            d1, d2 = st.columns(2)
            export = [{k: v for k, v in r.items() if k != "client_id"} for r in DATA["runs"]]
            d1.download_button("Export JSON", json.dumps(export, indent=2), f"stalebot-history-{utcnow():%Y-%m-%d}.json",
                               "application/json", icon=":material/download:", use_container_width=True)
            if d2.button("Clear history", icon=":material/delete:", use_container_width=True, disabled=not is_admin()):
                st.session_state["confirm_clear"] = True
            if st.session_state.get("confirm_clear"):
                st.warning("Permanently delete every stored analysis? Projects are kept. This cannot be undone.")
                y, n = st.columns(2)
                if y.button("Yes, clear everything", type="primary", use_container_width=True):
                    update_store(lambda d: d.__setitem__("runs", []))
                    st.session_state["last_run_id"] = None
                    st.session_state.pop("confirm_clear", None)
                    st.toast("History cleared.")
                    st.rerun()
                if n.button("Cancel", use_container_width=True):
                    st.session_state.pop("confirm_clear", None)
                    st.rerun()


# ============================================================================ router
{"Dashboard": page_dashboard, "Analytics": page_analytics, "Claim Projects": page_projects,
 "Historical Data": page_history, "Settings": page_settings}[VIEW]()
