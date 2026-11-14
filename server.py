"""StaleBot dashboard API: serves the dashboard UI and wraps the stale-answer detector.

Run:  python server.py   (then open http://localhost:8000)
Security settings (access keys, rate limits, production mode) are documented in .env.example.
"""
import json
import logging
import os
import re
import threading
import time
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from detector import (
    ERR_NOT_CONFIGURED, ERR_OFFLINE, analyze_text, build_reports, check_bifrost, get_settings,
)
from security import (
    ROLE_ADMIN, SecurityConfig, bearer_token, build_csp, client_ip, limiter, role_for_token,
    security_headers,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("stalebot")

ROOT = Path(__file__).parent
STATIC_DIR = ROOT / "static"
DATA_DIR = Path(os.getenv("DATA_DIR", "").strip() or ROOT / "data")
STORE_PATH = DATA_DIR / "store.json"
CLIENT_ID_RE = re.compile(r"^[A-Za-z0-9]{8,64}$")
MAX_SESSIONS = 20_000
SESSION_WRITE_INTERVAL = timedelta(minutes=5)
MAX_INPUT_CHARS = 8000
VERDICTS = ["Verified", "Partially True", "Stale", "False", "Unverified"]
VERDICT_FROM_STATUS = {"Fresh": "Verified", "Stale": "Stale", "Unverified": "Unverified"}

# Models offered in the dropdown. Names are Bifrost "provider/model" ids; override with
# AVAILABLE_MODELS="provider/model:Label,provider/model:Label" in .env.
DEFAULT_MODELS = [
    ("openai/gpt-4o", "GPT-4o"),
    ("anthropic/claude-3-5-sonnet-20241022", "Claude 3.5 Sonnet"),
    ("gemini/gemini-1.5-pro", "Gemini 1.5 Pro"),
]


def utcnow():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_iso(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def model_label(model_id):
    """'groq/openai/gpt-oss-20b' -> 'GPT OSS 20B · Groq'."""
    parts = model_id.split("/")
    name, provider = parts[-1], parts[0] if len(parts) > 1 else ""
    words = []
    for token in name.replace("_", "-").split("-"):
        if token.lower() in {"gpt", "oss", "ai", "llm"} or re.fullmatch(r"\d+(\.\d+)?[bkm]", token.lower()):
            words.append(token.upper())
        else:
            words.append(token[:1].upper() + token[1:])
    pretty = " ".join(words) or model_id
    return f"{pretty} · {provider.title()}" if provider else pretty


def available_models(configured):
    raw = os.getenv("AVAILABLE_MODELS", "").strip()
    models = []
    if raw:
        for part in raw.split(","):
            model_id, _, label = part.strip().partition(":")
            if model_id:
                models.append((model_id, label.strip() or model_label(model_id)))
    else:
        models = list(DEFAULT_MODELS)
    if configured and configured not in {m for m, _ in models}:
        models.insert(0, (configured, model_label(configured) + " (default)"))
    return [{"id": m, "label": label} for m, label in models]


class Store:
    """Small JSON-file store; good enough for a single-instance local dashboard."""

    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self.data = {"runs": [], "projects": [], "sessions": {}, "settings": {}}
        if path.exists():
            try:
                self.data.update(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                backup = path.with_suffix(".corrupt.json")
                path.replace(backup)

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1), encoding="utf-8")
        tmp.replace(self.path)


store = Store(STORE_PATH)
runtime = {
    "probe": None,          # last gateway probe result
    "probe_model": None,
    "probe_at": None,
    "probing": False,
    "model_health": {},     # model id -> "ok" | "unavailable"
    "tavily_state": None,   # None until first search, then "active" | "failed"
}

cfg = SecurityConfig.from_env()
for note in cfg.warnings():
    log.warning("SECURITY: %s", note)
log.info(
    "Mode=%s host=%s access_key=%s admin_key=%s docs=%s limits: api %d/min, analyze %d/min %d/h, "
    "%d concurrent",
    "production" if cfg.production else "development", cfg.host,
    "on" if cfg.access_token else "off", "on" if cfg.admin_token else ("open (dev)" if cfg.open_admin else "off"),
    "on" if cfg.enable_docs else "off", cfg.api_limit_per_minute, cfg.analyze_limit_per_minute,
    cfg.analyze_limit_per_hour, cfg.max_concurrent_analyses,
)

CSP = build_csp((STATIC_DIR / "index.html").read_text(encoding="utf-8"))
analysis_slots = threading.BoundedSemaphore(cfg.max_concurrent_analyses)
probe_lock = threading.Lock()

app = FastAPI(
    title="StaleBot API",
    docs_url="/api/docs" if cfg.enable_docs else None,
    openapi_url="/api/openapi.json" if cfg.enable_docs else None,
    redoc_url=None,
)


def caller_ip(request: Request):
    return client_ip(cfg, request.headers, request.client.host if request.client else None)


def too_many(wait, message="Too many requests"):
    return JSONResponse(
        {"detail": f"{message}. Try again in {wait}s."}, status_code=429,
        headers={"Retry-After": str(wait)},
    )


@app.middleware("http")
async def guard(request: Request, call_next):
    path = request.url.path
    response = None
    if path.startswith("/api/"):
        length = request.headers.get("content-length", "")
        if length.isdigit() and int(length) > cfg.max_body_bytes:
            response = JSONResponse({"detail": "Request body too large."}, status_code=413)
        else:
            wait = limiter.hit([(f"api:{caller_ip(request)}", cfg.api_limit_per_minute, 60)])
            if wait:
                response = too_many(wait)
    if response is None:
        response = await call_next(request)
    # Always revalidate the UI so edits show up without a hard refresh (ETags keep it cheap).
    if path == "/" or path.startswith(("/static/", "/api/")):
        response.headers["Cache-Control"] = "no-cache"
    for name, value in security_headers(cfg, path, CSP).items():
        response.headers.setdefault(name, value)
    return response


def request_role(request: Request):
    return role_for_token(cfg, bearer_token(request.headers))


def require_access(request: Request):
    role = request_role(request)
    if role is None:
        raise HTTPException(401, "Access key required.", headers={"WWW-Authenticate": "Bearer"})
    return role


def require_admin(request: Request):
    role = require_access(request)
    if role != ROLE_ADMIN:
        if cfg.admin_token:
            raise HTTPException(403, "Admin access required. Enter the admin key in Settings → Access.")
        raise HTTPException(403, "Admin actions are disabled on this server (ADMIN_TOKEN is not set).")
    return role


# ---------- helpers ----------

def current_settings():
    settings = get_settings()
    selected = store.data["settings"].get("model")
    if selected:
        settings["model"] = selected
    return settings


def touch_session(request: Request):
    """Record a browser as active. Writes at most every few minutes per browser, ignores
    malformed IDs, and caps the table so a flood of fake IDs can't grow it without bound."""
    client_id = request.headers.get("x-client-id", "")
    if not CLIENT_ID_RE.match(client_id):
        return ""
    now = utcnow()
    with store.lock:
        sessions = store.data["sessions"]
        last = sessions.get(client_id)
        if last and now - parse_iso(last) < SESSION_WRITE_INTERVAL:
            return client_id
        sessions[client_id] = iso(now)
        cutoff = now - timedelta(days=30)
        kept = {k: v for k, v in sessions.items() if parse_iso(v) > cutoff}
        if len(kept) > MAX_SESSIONS:
            kept = dict(sorted(kept.items(), key=lambda kv: kv[1])[-MAX_SESSIONS:])
        store.data["sessions"] = kept
        store.save()
    return client_id


def run_probe(model=None):
    settings = current_settings()
    if model:
        settings["model"] = model
    runtime["probing"] = True
    try:
        probe = check_bifrost(settings)
    finally:
        runtime["probing"] = False
    runtime.update(probe=probe, probe_model=settings["model"], probe_at=iso(utcnow()))
    if probe["model_available"] is True:
        runtime["model_health"][settings["model"]] = "ok"
    elif probe["model_available"] is False:
        runtime["model_health"][settings["model"]] = "unavailable"
    return probe


def status_payload(role=ROLE_ADMIN):
    settings = current_settings()
    probe = runtime["probe"]
    if runtime["probing"]:
        gateway = "checking"
    elif probe is None:
        gateway = "unknown"
    else:
        gateway = probe["state"]  # connected | unavailable | missing
    tavily = (
        "missing" if not settings["tavily_api_key"]
        else runtime["tavily_state"] or "ready"
    )
    return {
        "gateway": {
            "state": gateway,
            # The internal gateway address is only shown to admins.
            "base_url": settings["base_url"] if role == ROLE_ADMIN else None,
            "checked_at": runtime["probe_at"],
            # Which route answered last: "bifrost", or "groq" when running on the direct fallback.
            "provider": (probe or {}).get("provider"),
            "fallback_available": bool(settings.get("groq_api_key")),
        },
        "model": {
            "selected": settings["model"],
            "default": get_settings()["model"],
            "health": runtime["model_health"].get(settings["model"], "unknown"),
            "options": [
                {**m, "health": runtime["model_health"].get(m["id"], "unknown")}
                for m in available_models(get_settings()["model"])
            ],
        },
        "search": {"state": tavily, "provider": "Tavily"},
    }


def claim_rows(runs):
    for run in runs:
        for index, item in enumerate(run.get("results", [])):
            yield run, index, item


def verdict_of(item):
    return item.get("verdict") or VERDICT_FROM_STATUS.get(item.get("status"), "Unverified")


def confidence_of(item):
    """How sure the verdict is (0-100), derived from the freshness score.

    Fresh scores 70-100 -> score; Stale 0-40 -> 100-score; Unverified 41-69 -> low by design.
    """
    score = int(item.get("freshness_score") or 0)
    status = item.get("status")
    if status == "Fresh":
        return score
    if status == "Stale":
        return 100 - score
    return min(score, 100 - score)


def public_run(run, include_sources=True):
    results = []
    for item in run.get("results", []):
        entry = {**item, "verdict": verdict_of(item), "confidence": confidence_of(item)}
        if not include_sources:
            entry.pop("sources", None)
        results.append(entry)
    return {k: v for k, v in run.items() if k != "client_id"} | {"results": results}


def compute_stats():
    now = utcnow()
    runs = store.data["runs"]
    rows = list(claim_rows(runs))
    counts = Counter(verdict_of(item) for _, _, item in rows)
    total = len(rows)

    def claims_between(start, end):
        return sum(len(r.get("results", [])) for r in runs if start <= parse_iso(r["created_at"]) < end)

    last24 = claims_between(now - timedelta(hours=24), now + timedelta(seconds=1))
    prev24 = claims_between(now - timedelta(hours=48), now - timedelta(hours=24))
    claims_trend = None if prev24 == 0 else round((last24 - prev24) / prev24 * 100)

    fresh = counts["Verified"] + counts["Partially True"]
    freshness_rate = round(fresh / total * 100) if total else None
    avg_score = round(sum(i.get("freshness_score", 0) for _, _, i in rows) / total) if total else None

    durations = [r["duration_ms"] for r in runs if r.get("duration_ms")]
    recent_d, older_d = durations[:10], durations[10:20]
    avg_response = round(sum(recent_d) / len(recent_d) / 1000, 1) if recent_d else None
    response_delta = (
        round(avg_response - sum(older_d) / len(older_d) / 1000, 1) if recent_d and older_d else None
    )

    sessions = store.data["sessions"]
    active_24h = sum(1 for v in sessions.values() if parse_iso(v) > now - timedelta(hours=24))
    active_prev = sum(
        1 for v in sessions.values()
        if now - timedelta(hours=48) < parse_iso(v) <= now - timedelta(hours=24)
    )

    # Live search activity: searches per hour over the last 24h (oldest -> newest).
    start_hour = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=23)
    hourly = [{"hour": iso(start_hour + timedelta(hours=h)), "searches": 0, "failures": 0, "claims": 0}
              for h in range(24)]
    for r in runs:
        created = parse_iso(r["created_at"])
        slot = int((created - start_hour).total_seconds() // 3600)
        if 0 <= slot < 24:
            hourly[slot]["searches"] += r.get("search_successes", 0)
            hourly[slot]["failures"] += r.get("search_failures", 0)
            hourly[slot]["claims"] += len(r.get("results", []))

    # 14-day daily series for sparklines.
    days = [(now - timedelta(days=13 - d)).date() for d in range(14)]
    daily_claims = Counter(parse_iso(r["created_at"]).date() for r, _, _ in rows)
    cumulative, running = [], total - sum(daily_claims[d] for d in days)
    for d in days:
        running += daily_claims[d]
        cumulative.append(running)
    daily_sessions = [
        sum(1 for v in sessions.values() if parse_iso(v).date() == d) for d in days
    ]
    daily_scores = []
    for d in days:
        scores = [i.get("freshness_score", 0) for r, _, i in rows if parse_iso(r["created_at"]).date() == d]
        daily_scores.append(round(sum(scores) / len(scores)) if scores else None)

    # System health: share of live searches that succeeded, last 7 days vs the 7 before.
    def search_rate(start, end):
        ok = fail = 0
        for r in runs:
            if start <= parse_iso(r["created_at"]) < end:
                ok += r.get("search_successes", 0)
                fail += r.get("search_failures", 0)
        return None if ok + fail == 0 else round(ok / (ok + fail) * 100, 1)

    health = search_rate(now - timedelta(days=7), now + timedelta(seconds=1))
    health_prev = search_rate(now - timedelta(days=14), now - timedelta(days=7))
    health_series = [
        search_rate(datetime.combine(d, datetime.min.time(), timezone.utc),
                    datetime.combine(d, datetime.min.time(), timezone.utc) + timedelta(days=1))
        for d in days
    ]

    daily_search = []
    for d in days[-7:]:
        start = datetime.combine(d, datetime.min.time(), timezone.utc)
        bucket = {"day": d.isoformat(), "searches": 0, "failures": 0, "claims": 0}
        for r in runs:
            if start <= parse_iso(r["created_at"]) < start + timedelta(days=1):
                bucket["searches"] += r.get("search_successes", 0)
                bucket["failures"] += r.get("search_failures", 0)
                bucket["claims"] += len(r.get("results", []))
        daily_search.append(bucket)

    return {
        "total_claims": total,
        "health": {
            "rate": health,
            "delta": None if health is None or health_prev is None else round(health - health_prev, 1),
            "series": health_series,
        },
        "daily_search": daily_search,
        "total_runs": len(runs),
        "claims_24h": last24,
        "claims_trend_pct": claims_trend,
        "distribution": {v: counts[v] for v in VERDICTS},
        "freshness_rate": freshness_rate,
        "avg_score": avg_score,
        "avg_response_s": avg_response,
        "response_delta_s": response_delta,
        "active_users_24h": active_24h,
        "active_users_trend_pct": None if active_prev == 0 else round((active_24h - active_prev) / active_prev * 100),
        "hourly_search": hourly,
        "series": {
            "days": [d.isoformat() for d in days],
            "cumulative_claims": cumulative,
            "daily_claims": [daily_claims[d] for d in days],
            "active_users": daily_sessions,
            "avg_score": daily_scores,
            "response_times": [round(d / 1000, 1) for d in reversed(durations[:14])],
        },
    }


# ---------- API ----------

class AnalyzeIn(BaseModel):
    text: str = Field(..., max_length=MAX_INPUT_CHARS)
    project_id: Optional[str] = None


class ModelIn(BaseModel):
    model: str = Field(..., max_length=200)


class ProjectIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    description: str = Field("", max_length=300)


class RunPatch(BaseModel):
    project_id: Optional[str] = None


@app.get("/healthz")
@app.head("/healthz")
def healthz():
    """Liveness check for load balancers; never calls the gateway (free)."""
    return {"status": "ok"}


@app.get("/api/session")
def session_info(request: Request):
    """Who am I? Works without a key so the UI knows when to ask for one."""
    settings = get_settings()
    return {
        "role": request_role(request),
        "auth_required": bool(cfg.access_token),
        "admin_configured": bool(cfg.admin_token),
        "admin_open": cfg.open_admin,
        "production": cfg.production,
        "limits": {
            "analyze_per_minute": cfg.analyze_limit_per_minute,
            "analyze_per_hour": cfg.analyze_limit_per_hour,
            "max_claims": settings["max_claims"],
            "max_input_chars": MAX_INPUT_CHARS,
        },
    }


@app.get("/api/status")
def get_status(request: Request, role: str = Depends(require_access)):
    touch_session(request)
    return status_payload(role)


@app.post("/api/status/refresh")
def refresh_status(request: Request, role: str = Depends(require_access)):
    """Re-check the gateway. Each probe is a (tiny) paid model call, so non-admins share one
    result per PROBE_COOLDOWN_SECONDS and only one probe runs at a time."""
    touch_session(request)
    recent = runtime["probe_at"] and utcnow() - parse_iso(runtime["probe_at"]) < timedelta(seconds=cfg.probe_cooldown_s)
    if role != ROLE_ADMIN and recent:
        return status_payload(role)
    if probe_lock.acquire(blocking=False):
        try:
            run_probe()
        finally:
            probe_lock.release()
    return status_payload(role)


@app.post("/api/model")
def set_model(body: ModelIn, role: str = Depends(require_admin)):
    allowed = {m["id"] for m in available_models(get_settings()["model"])}
    if body.model not in allowed:
        raise HTTPException(400, "Unknown model. Add it to AVAILABLE_MODELS in .env first.")
    with store.lock:
        store.data["settings"]["model"] = body.model
        store.save()
    with probe_lock:
        run_probe(body.model)
    return status_payload(role)


@app.post("/api/analyze")
def analyze(body: AnalyzeIn, request: Request, role: str = Depends(require_access)):
    client_id = touch_session(request)
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "Enter a claim or answer to verify.")
    if body.project_id and not any(p["id"] == body.project_id for p in store.data["projects"]):
        raise HTTPException(400, "Project not found.")

    # Each analysis costs model calls and searches: limit per caller (admins exempt) and overall.
    if role != ROLE_ADMIN:
        ip = caller_ip(request)
        wait = limiter.hit([
            (f"analyze-min:{ip}", cfg.analyze_limit_per_minute, 60),
            (f"analyze-hour:{ip}", cfg.analyze_limit_per_hour, 3600),
        ])
        if wait:
            log.info("Analyze rate limit hit for %s", ip)
            raise HTTPException(429, f"Analysis limit reached. Try again in {wait}s.",
                                headers={"Retry-After": str(wait)})
    if not analysis_slots.acquire(blocking=False):
        raise HTTPException(503, "StaleBot is busy with other analyses. Please try again shortly.",
                            headers={"Retry-After": "10"})
    try:
        settings = current_settings()
        started = time.perf_counter()
        result, error = analyze_text(text, settings)
        duration_ms = round((time.perf_counter() - started) * 1000)
    finally:
        analysis_slots.release()
    if error:
        log.warning("Analysis failed: %s", error)
        if error == ERR_OFFLINE:
            runtime["probe"] = {"state": "unavailable", "model_available": None, "provider": None}
            runtime["probe_at"] = iso(utcnow())
        status = 503 if error in {ERR_OFFLINE, ERR_NOT_CONFIGURED} else 502
        raise HTTPException(status, error, headers={"Retry-After": "30"} if status == 503 else None)

    runtime["probe"] = {"state": "connected", "model_available": True,
                        "provider": result.get("provider"), "provider_label": result.get("provider_label")}
    runtime["probe_at"] = iso(utcnow())
    runtime["model_health"][settings["model"]] = "ok"
    if result["search_successes"] or result["search_failures"]:
        runtime["tavily_state"] = "failed" if result["search_failures"] and not result["search_successes"] else "active"

    run = {
        "id": uuid.uuid4().hex[:12],
        "created_at": iso(utcnow()),
        "input_text": text,
        "model": result.get("model_used") or settings["model"],
        "provider": result.get("provider"),
        "duration_ms": duration_ms,
        "search_successes": result["search_successes"],
        "search_failures": result["search_failures"],
        "project_id": body.project_id,
        "client_id": client_id,
        "claims_truncated": result.get("claims_truncated", 0),
        "results": result["results"],
    }
    with store.lock:
        store.data["runs"].insert(0, run)
        store.save()
    return {"run": public_run(run), "stats": compute_stats(), "status": status_payload(role)}


@app.get("/api/stats", dependencies=[Depends(require_access)])
def stats():
    return compute_stats()


OVERVIEW_RANGES = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30), "all": None}


@app.get("/api/overview", dependencies=[Depends(require_access)])
def overview(window_key: str = Query("7d", alias="range", pattern="^(24h|7d|30d|all)$")):
    """Verdict mix for a time window, plus freshness-rate change vs the previous window."""
    now = utcnow()
    span = OVERVIEW_RANGES[window_key]
    rows = list(claim_rows(store.data["runs"]))

    def window(start, end):
        return [i for r, _, i in rows if (start is None or parse_iso(r["created_at"]) >= start)
                and parse_iso(r["created_at"]) < end]

    def fresh_rate(items):
        if not items:
            return None
        fresh = sum(verdict_of(i) in {"Verified", "Partially True"} for i in items)
        return round(fresh / len(items) * 100)

    end = now + timedelta(seconds=1)
    current = window(None if span is None else now - span, end)
    previous = [] if span is None else window(now - 2 * span, now - span)
    counts = Counter(verdict_of(i) for i in current)
    rate, prev_rate = fresh_rate(current), fresh_rate(previous)

    # Daily freshness rate across the last 7 days for the callout sparkline.
    trend = []
    for d in range(6, -1, -1):
        day_start = (now - timedelta(days=d)).replace(hour=0, minute=0, second=0, microsecond=0)
        trend.append(fresh_rate(window(day_start, day_start + timedelta(days=1))))

    return {
        "range": window_key,
        "total": len(current),
        "distribution": {v: counts[v] for v in VERDICTS},
        "verified_pct": round(counts["Verified"] / len(current) * 100) if current else None,
        "freshness_rate": rate,
        "previous_freshness_rate": prev_rate,
        "freshness_delta": None if rate is None or prev_rate is None else rate - prev_rate,
        "trend": trend,
    }


@app.get("/api/claims", dependencies=[Depends(require_access)])
def list_claims(
    limit: int = Query(50, ge=1, le=500),
    q: str = "",
    verdict: str = "",
    project_id: str = "",
):
    q = q.lower().strip()
    items = []
    for run, index, item in claim_rows(store.data["runs"]):
        v = verdict_of(item)
        if verdict and v != verdict:
            continue
        if project_id and run.get("project_id") != project_id:
            continue
        if q and q not in item["claim"].lower() and q not in run["input_text"].lower():
            continue
        items.append({
            "run_id": run["id"], "index": index, "claim": item["claim"], "verdict": v,
            "status": item.get("status"), "freshness_score": item.get("freshness_score"),
            "confidence": confidence_of(item),
            "updated_fact": item.get("updated_fact"), "created_at": run["created_at"],
            "model": run.get("model"), "project_id": run.get("project_id"),
            "source_count": len(item.get("sources", [])),
        })
    return {"total": len(items), "items": items[:limit]}


@app.get("/api/runs", dependencies=[Depends(require_access)])
def list_runs(limit: int = Query(100, ge=1, le=1000), project_id: str = ""):
    runs = [r for r in store.data["runs"] if not project_id or r.get("project_id") == project_id]
    return {"total": len(runs), "items": [public_run(r, include_sources=False) for r in runs[:limit]]}


def find_run(run_id):
    run = next((r for r in store.data["runs"] if r["id"] == run_id), None)
    if not run:
        raise HTTPException(404, "Analysis not found.")
    return run


@app.get("/api/runs/{run_id}", dependencies=[Depends(require_access)])
def get_run(run_id: str):
    return public_run(find_run(run_id))


@app.patch("/api/runs/{run_id}", dependencies=[Depends(require_admin)])
def patch_run(run_id: str, body: RunPatch):
    if body.project_id and not any(p["id"] == body.project_id for p in store.data["projects"]):
        raise HTTPException(400, "Project not found.")
    with store.lock:
        run = find_run(run_id)
        run["project_id"] = body.project_id
        store.save()
    return public_run(run, include_sources=False)


@app.delete("/api/runs/{run_id}", dependencies=[Depends(require_admin)])
def delete_run(run_id: str):
    with store.lock:
        find_run(run_id)
        store.data["runs"] = [r for r in store.data["runs"] if r["id"] != run_id]
        store.save()
    return {"ok": True}


@app.delete("/api/runs", dependencies=[Depends(require_admin)])
def clear_runs():
    with store.lock:
        store.data["runs"] = []
        store.save()
    return {"ok": True}


@app.get("/api/runs/{run_id}/report", response_class=PlainTextResponse, dependencies=[Depends(require_access)])
def run_report(run_id: str, kind: str = Query("full", pattern="^(full|corrected)$")):
    run = find_run(run_id)
    created = parse_iso(run["created_at"]).astimezone().strftime("%Y-%m-%d %H:%M %Z")
    full, corrected = build_reports({**run, "created_at": created})
    filename = f"stale-answer-{'audit' if kind == 'full' else 'corrected'}-{run_id}.md"
    return PlainTextResponse(
        full if kind == "full" else corrected,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/projects", dependencies=[Depends(require_access)])
def list_projects():
    counts = Counter(r.get("project_id") for r in store.data["runs"])
    claim_counts = Counter()
    stale_counts = Counter()
    for run, _, item in claim_rows(store.data["runs"]):
        claim_counts[run.get("project_id")] += 1
        if verdict_of(item) in {"Stale", "False"}:
            stale_counts[run.get("project_id")] += 1
    return [
        {**p, "runs": counts[p["id"]], "claims": claim_counts[p["id"]], "stale": stale_counts[p["id"]]}
        for p in store.data["projects"]
    ]


@app.post("/api/projects", dependencies=[Depends(require_admin)])
def create_project(body: ProjectIn):
    project = {
        "id": uuid.uuid4().hex[:10], "name": body.name.strip(),
        "description": body.description.strip(), "created_at": iso(utcnow()),
    }
    with store.lock:
        store.data["projects"].append(project)
        store.save()
    return project


@app.delete("/api/projects/{project_id}", dependencies=[Depends(require_admin)])
def delete_project(project_id: str):
    with store.lock:
        store.data["projects"] = [p for p in store.data["projects"] if p["id"] != project_id]
        for run in store.data["runs"]:
            if run.get("project_id") == project_id:
                run["project_id"] = None
        store.save()
    return {"ok": True}


@app.get("/api/config")
def config(role: str = Depends(require_access)):
    settings = current_settings()
    admin = role == ROLE_ADMIN
    try:
        store_path = str(STORE_PATH.relative_to(ROOT))
    except ValueError:
        store_path = str(STORE_PATH)
    return {
        # Infrastructure details are admin-only.
        "base_url": settings["base_url"] if admin else None,
        "store_path": store_path if admin else None,
        "default_model": get_settings()["model"],
        "selected_model": settings["model"],
        "gateway_key_configured": bool(settings["virtual_key"]),
        "groq_fallback_configured": bool(settings["groq_api_key"]),
        "tavily_key_configured": bool(settings["tavily_api_key"]),
        "max_input_chars": MAX_INPUT_CHARS,
        "max_claims": settings["max_claims"],
    }


@app.get("/")
@app.head("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    import uvicorn

    # Pass the app object (not "server:app") so the module isn't imported twice, and keep a single
    # process on purpose: the JSON store and the rate limiter live in this process's memory.
    uvicorn.run(app, host=cfg.host, port=int(os.getenv("PORT", "8000")), server_header=False)
