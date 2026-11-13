# StaleBot — AI Stale-Answer Detector

StaleBot checks AI answers, headlines and claims for **outdated or false information**. It pulls
out the time-sensitive facts (versions, prices, releases, regulations), searches the live web
for each one, and scores how current it is:

**Verified** · **Partially True** · **Stale** · **False** · **Unverified**

Missing evidence never counts as "stale": weak or conflicting evidence is reported as *Unverified*.

| Part | File | Port |
|---|---|---|
| Dashboard + JSON API | `server.py`, `static/` | 8000 |
| Optional Streamlit UI | `app.py` | 8501 |
| Detection pipeline (shared) | `detector.py` | — |
| Access control, rate limits, headers (shared) | `security.py` | — |

It uses an OpenAI-compatible **[Bifrost](https://github.com/maximhq/bifrost) gateway** for the
model and **[Tavily](https://tavily.com)** for live web search. You need both.

---

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements-streamlit.txt
copy .env.example .env            # macOS/Linux: cp .env.example .env  — then fill in the keys
python server.py                  # dashboard: http://localhost:8000
python -m streamlit run app.py    # optional:  http://localhost:8501
```

With the default `APP_ENV=development` there are no keys to enter and everyone is an admin.
That is only safe on your own machine.

---

## Configuration

Every setting is documented in [`.env.example`](.env.example). The essentials:

| Variable | Required | Purpose |
|---|---|---|
| `TAVILY_API_KEY` | ✅ | Live web search |
| `BIFROST_BASE_URL` | ✅ | Gateway URL, e.g. `http://localhost:8080/v1` |
| `BIFROST_VIRTUAL_KEY` | ✅ | Gateway key |
| `MODEL_NAME` | ✅ | Default model, `provider/model` |
| `APP_ENV` | prod: ✅ | `production` turns on the protections below |
| `ADMIN_TOKEN` | prod: ✅ | Admin key: delete history, switch models, manage projects |
| `ACCESS_TOKEN` | recommended | If set, visitors need this key to use the app at all |
| `HOST` / `PORT` | — | `0.0.0.0` in containers; the platform usually sets `PORT` |
| `DATA_DIR` | prod: ✅ | Where history is stored; must be a **persistent** disk |
| `TRUST_PROXY` | — | `true` only behind your own reverse proxy |
| `ANALYZE_LIMIT_PER_MINUTE` / `_PER_HOUR`, `MAX_CONCURRENT_ANALYSES`, `MAX_CLAIMS_PER_REQUEST` | — | Cost controls |

Generate keys with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Security modes

| | Development (default) | Production, public | Production, private |
|---|---|---|---|
| Set | nothing | `APP_ENV=production`, `ADMIN_TOKEN` | + `ACCESS_TOKEN` |
| Who can use it | anyone who can reach it | anyone | key holders only |
| Admin actions | everyone | admin key only | admin key only |
| Shared history visible to | everyone | **everyone** | key holders |
| API docs (`/api/docs`) | on | off | off |

Always on: per-IP rate limits, a cap on simultaneous analyses, a claim cap per request, a request
size limit, a strict Content-Security-Policy and other security headers (plus HSTS in production).
Check the startup log: it prints the active mode and a `SECURITY:` warning for anything risky.

---

## Deploy

### Docker Compose (any VPS)

```bash
cp .env.example .env              # fill in keys; set ADMIN_TOKEN (and ACCESS_TOKEN)
docker compose up -d --build                        # dashboard on 127.0.0.1:8000
docker compose --profile streamlit up -d --build    # also Streamlit on 127.0.0.1:8501
```

Ports are bound to `127.0.0.1` on purpose. Put a TLS reverse proxy in front, e.g. Caddy:

```
stalebot.example.com {
    reverse_proxy 127.0.0.1:8000
}
```

When the app is reachable *only* through that proxy, set `TRUST_PROXY=true` so rate limits apply
per visitor instead of to the proxy's IP. If Bifrost runs on the host, the compose file already
points the container at `http://host.docker.internal:8080/v1` (override it with
`BIFROST_BASE_URL_DOCKER`).

### Docker (single container)

```bash
docker build -t stalebot .
docker run -d --name stalebot --env-file .env -e APP_ENV=production \
  -p 127.0.0.1:8000:8000 -v stalebot-data:/data stalebot
```

The image runs as a non-root user, keeps history on the `/data` volume, and has a built-in
health check (`GET /healthz`).

### Platforms (Render, Railway, Fly.io, Heroku-style)

* Start command: `HOST=0.0.0.0 python server.py` (see `Procfile`); the platform provides `PORT`.
* Set every variable from `.env.example` in the platform's secret settings. Don't upload `.env`.
* Attach a **persistent disk** and point `DATA_DIR` at it. Most platforms wipe local files on
  redeploy, which would erase the history.
* Health check path: `/healthz`
* Run exactly **one** instance (see Known limitations).
* The gateway must be reachable from the platform: deploy Bifrost too, or use a hosted gateway URL.

---

## Pre-launch checklist

- [ ] `APP_ENV=production`
- [ ] `ADMIN_TOKEN` set: long and random, not shared with viewers
- [ ] `ACCESS_TOKEN` set, unless you accept that **all visitors see the shared history**
- [ ] `.env` is not committed or uploaded (`.gitignore` and `.dockerignore` already exclude it)
- [ ] `DATA_DIR` is on persistent storage and backed up
- [ ] HTTPS in front of the app; `TRUST_PROXY=true` only if the app is reachable solely via the proxy
- [ ] `BIFROST_BASE_URL` reachable from the server, and `AVAILABLE_MODELS` lists models your gateway actually serves
- [ ] Rate limits and `MAX_CLAIMS_PER_REQUEST` reviewed against your Tavily/model budget
- [ ] Startup log shows no `SECURITY:` warnings
- [ ] `https://your-domain/healthz` returns `{"status":"ok"}`
- [ ] A privacy notice for users: submitted text goes to the model provider and to Tavily, and is kept in history

---

## API

`GET /healthz` · `GET /api/session` (current role and limits; no key needed) ·
`POST /api/analyze` · `GET /api/stats` · `GET /api/claims` · `GET /api/runs[/{id}]` ·
`GET /api/runs/{id}/report?kind=full|corrected` · `GET /api/status` · `POST /api/status/refresh` ·
`GET /api/projects` · `GET /api/config`

Admin only: `POST /api/model` · `PATCH|DELETE /api/runs/{id}` · `DELETE /api/runs` ·
`POST /api/projects` · `DELETE /api/projects/{id}`

Authenticate with `Authorization: Bearer <access or admin key>`. Interactive docs are at
`/api/docs` in development.

---

## Known limitations

* **One process only.** History (`data/store.json`) and rate-limit counters live in memory and in a
  local file. Running several workers or instances would split them. Moving to SQLite/Postgres
  and Redis would remove this limit.
* **Analyses are a single long request** (about 5 seconds per claim). Proxies with short timeouts
  (under 60s) can cut off big checks. Lower `MAX_CLAIMS_PER_REQUEST` or raise the proxy timeout.
* **Shared history.** Without `ACCESS_TOKEN`, every visitor sees every check. There are no per-user accounts yet.
* Values in `.env` take precedence over environment variables already set. On servers, prefer
  platform environment variables and don't ship a `.env` file.
