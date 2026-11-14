"""Access control, rate limiting and HTTP hardening shared by the StaleBot apps.

Everything is driven by environment variables (documented in .env.example). With none of them
set, StaleBot behaves like a local single-user tool: every request gets admin rights. Set
APP_ENV=production (plus ADMIN_TOKEN, and ACCESS_TOKEN for a private deployment) before
exposing it to other people.
"""
import base64
import hashlib
import hmac
import ipaddress
import logging
import os
import re
import threading
import time
from collections import deque
from dataclasses import dataclass

log = logging.getLogger("stalebot.security")

ROLE_ADMIN = "admin"
ROLE_VIEWER = "viewer"


def _env_bool(name, default):
    value = os.getenv(name, "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def _env_int(name, default, minimum=0):
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return max(minimum, int(raw))
    except ValueError:
        log.warning("%s=%r is not a whole number; using %s", name, raw, default)
        return default


def _is_loopback(host):
    if host in {"localhost", ""}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@dataclass(frozen=True)
class SecurityConfig:
    production: bool
    access_token: str
    admin_token: str
    host: str
    trust_proxy: bool
    enable_docs: bool
    api_limit_per_minute: int
    analyze_limit_per_minute: int
    analyze_limit_per_hour: int
    max_concurrent_analyses: int
    probe_cooldown_s: int
    max_body_bytes: int

    @classmethod
    def from_env(cls):
        production = os.getenv("APP_ENV", "development").strip().lower() in {"production", "prod"}
        return cls(
            production=production,
            access_token=os.getenv("ACCESS_TOKEN", "").strip(),
            admin_token=os.getenv("ADMIN_TOKEN", "").strip(),
            host=os.getenv("HOST", "127.0.0.1").strip() or "127.0.0.1",
            trust_proxy=_env_bool("TRUST_PROXY", False),
            enable_docs=_env_bool("ENABLE_API_DOCS", not production),
            api_limit_per_minute=_env_int("API_RATE_LIMIT_PER_MINUTE", 120, 1),
            analyze_limit_per_minute=_env_int("ANALYZE_LIMIT_PER_MINUTE", 3, 1),
            analyze_limit_per_hour=_env_int("ANALYZE_LIMIT_PER_HOUR", 30, 1),
            max_concurrent_analyses=_env_int("MAX_CONCURRENT_ANALYSES", 3, 1),
            probe_cooldown_s=_env_int("PROBE_COOLDOWN_SECONDS", 60, 0),
            max_body_bytes=_env_int("MAX_REQUEST_BYTES", 64 * 1024, 1024),
        )

    @property
    def open_admin(self):
        """Local-development convenience: no admin token and not production -> everyone is admin."""
        return not self.admin_token and not self.production

    def warnings(self):
        notes = []
        if self.production and not self.admin_token:
            notes.append("ADMIN_TOKEN is not set: admin actions (deleting history, switching "
                         "models, managing projects) are disabled.")
        if self.production and not self.access_token:
            notes.append("ACCESS_TOKEN is not set: anyone with the URL can read the shared "
                         "history and run (rate-limited) analyses.")
        for name, token in (("ADMIN_TOKEN", self.admin_token), ("ACCESS_TOKEN", self.access_token)):
            if token and len(token) < 16:
                notes.append(f"{name} is shorter than 16 characters; use a long random value.")
        if self.admin_token and self.admin_token == self.access_token:
            notes.append("ADMIN_TOKEN and ACCESS_TOKEN are identical, so every viewer is an admin.")
        if not self.production and not _is_loopback(self.host):
            notes.append(f"HOST={self.host} makes the app reachable from other machines while "
                         "APP_ENV is not 'production', so every visitor gets admin rights. "
                         "Set APP_ENV=production and ADMIN_TOKEN.")
        return notes


def tokens_match(supplied, expected):
    """Constant-time comparison; an empty expected token never matches."""
    if not supplied or not expected:
        return False
    return hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8"))


def role_for_token(cfg, token):
    """Return 'admin', 'viewer', or None (access key required but missing/wrong)."""
    if tokens_match(token, cfg.admin_token):
        return ROLE_ADMIN
    if cfg.access_token:
        return ROLE_VIEWER if tokens_match(token, cfg.access_token) else None
    return ROLE_ADMIN if cfg.open_admin else ROLE_VIEWER


def bearer_token(headers):
    value = headers.get("authorization", "")
    return value[7:].strip() if value[:7].lower() == "bearer " else ""


def client_ip(cfg, headers, peer_host):
    """Caller's IP. X-Forwarded-For is trusted only when TRUST_PROXY=true (behind your own proxy)."""
    if cfg.trust_proxy:
        forwarded = headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()[:64]
    return (peer_host or "unknown")[:64]


class RateLimiter:
    """In-memory sliding-window limiter. Per process: run a single worker, or move to Redis."""

    def __init__(self, max_keys=50_000):
        self._hits = {}
        self._lock = threading.Lock()
        self._max_keys = max_keys

    def hit(self, rules):
        """rules: [(key, limit, window_seconds)]. Records a hit against every rule only if all
        pass. Returns 0 when allowed, otherwise the seconds to wait."""
        now = time.monotonic()
        with self._lock:
            wait = 0
            for key, limit, window in rules:
                queue = self._hits.setdefault(key, deque())
                while queue and queue[0] <= now - window:
                    queue.popleft()
                if len(queue) >= limit:
                    wait = max(wait, int(queue[0] + window - now) + 1)
            if wait:
                return wait
            for key, _, _ in rules:
                self._hits[key].append(now)
            if len(self._hits) > self._max_keys:
                self._hits = {k: q for k, q in self._hits.items() if q}
            return 0


limiter = RateLimiter()

_gates = {}
_gates_lock = threading.Lock()


def concurrency_gate(name, size):
    """Process-wide semaphore (created once per name) to cap simultaneous paid analyses."""
    with _gates_lock:
        return _gates.setdefault(name, threading.BoundedSemaphore(size))

_INLINE_SCRIPT = re.compile(r"<script>(.*?)</script>", re.S)


def build_csp(index_html):
    """CSP for the dashboard; inline <script> blocks in index.html are allowed by hash."""
    hashes = " ".join(
        "'sha256-" + base64.b64encode(hashlib.sha256(body.encode("utf-8")).digest()).decode() + "'"
        for body in _INLINE_SCRIPT.findall(index_html)
    )
    return "; ".join([
        "default-src 'self'",
        f"script-src 'self' {hashes}".strip(),
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        "font-src 'self' https://fonts.gstatic.com",
        "img-src 'self' data:",
        "connect-src 'self'",
        "frame-ancestors 'none'",
        "base-uri 'none'",
        "form-action 'self'",
        "object-src 'none'",
    ])


def security_headers(cfg, path, csp):
    headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
        "Cross-Origin-Opener-Policy": "same-origin",
    }
    # Swagger UI loads its assets from a CDN, so the strict CSP is skipped for the docs pages.
    if not path.startswith(("/api/docs", "/api/openapi")):
        headers["Content-Security-Policy"] = csp
    if cfg.production:
        headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return headers
