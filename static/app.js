/* StaleBot dashboard — vanilla JS, no build step. Talks to server.py (/api/*). */
(() => {
  "use strict";

  // ---------------------------------------------------------------- icons
  const ICONS = {
    dashboard: '<rect width="7" height="9" x="3" y="3" rx="1.5"/><rect width="7" height="5" x="14" y="3" rx="1.5"/><rect width="7" height="9" x="14" y="12" rx="1.5"/><rect width="7" height="5" x="3" y="16" rx="1.5"/>',
    chart: '<path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
    folder: '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
    history: '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z"/>',
    bell: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>',
    moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
    wand: '<path d="m21.64 3.64-1.28-1.28a1.21 1.21 0 0 0-1.72 0L2.36 18.64a1.21 1.21 0 0 0 0 1.72l1.28 1.28a1.2 1.2 0 0 0 1.72 0L21.64 5.36a1.2 1.2 0 0 0 0-1.72"/><path d="m14 7 3 3"/><path d="M5 6v4M19 14v4M10 2v2M7 8H3M21 16h-4M11 3H9"/>',
    "arrow-right": '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
    file: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8M16 13H8M16 17H8"/>',
    shield: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
    cpu: '<rect width="16" height="16" x="4" y="4" rx="2"/><rect width="6" height="6" x="9" y="9" rx="1"/><path d="M15 2v2M15 20v2M2 15h2M2 9h2M20 15h2M20 9h2M9 2v2M9 20v2"/>',
    search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "chevron-down": '<path d="m6 9 6 6 6-6"/>',
    "chevron-right": '<path d="m9 18 6-6-6-6"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    alert: '<path d="M12 7v6M12 17h.01"/>',
    x: '<path d="M18 6 6 18M6 6l12 12"/>',
    clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    hourglass: '<path d="M5 22h14M5 2h14M17 22v-4.17a2 2 0 0 0-.59-1.42L12 12l-4.41 4.41A2 2 0 0 0 7 17.83V22M7 2v4.17a2 2 0 0 0 .59 1.42L12 12l4.41-4.41A2 2 0 0 0 17 6.17V2"/>',
    help: '<path d="M9.1 9a3 3 0 0 1 5.82 1c0 2-3 3-3 3M12 17h.01"/>',
    zap: '<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/>',
    users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
    pie: '<path d="M21.21 15.89A10 10 0 1 1 8 2.83"/><path d="M22 12A10 10 0 0 0 12 2v10z"/>',
    activity: '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    trash: '<path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
    external: '<path d="M15 3h6v6M10 14 21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
    refresh: '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
    globe: '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20M2 12h20"/>',
    trend: '<path d="m22 7-8.5 8.5-5-5L2 17"/><path d="M16 7h6v6"/>',
    user: '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    gauge: '<path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/>',
    info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
  };
  const icon = (name, cls = "") => `<i data-i="${name}" class="${cls}">${svg(name)}</i>`;
  const svg = (name) => `<svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ""}</svg>`;
  const hydrateIcons = (root = document) =>
    root.querySelectorAll("i[data-i]:empty").forEach((el) => (el.innerHTML = svg(el.dataset.i)));

  // ---------------------------------------------------------------- constants
  const VERDICTS = {
    "Verified": { cls: "v-verified", icon: "check", label: "Verified · Current", short: "Verified" },
    "Partially True": { cls: "v-partial", icon: "alert", label: "Partially True", short: "Partially True" },
    "Stale": { cls: "v-stale", icon: "hourglass", label: "Stale / Outdated", short: "Stale" },
    "False": { cls: "v-false", icon: "x", label: "False", short: "False" },
    "Unverified": { cls: "v-unverified", icon: "help", label: "Unverified", short: "Unverified" },
  };
  const VERDICT_ORDER = Object.keys(VERDICTS);
  const VERDICT_COLORS = { "Verified": "#22C55E", "Partially True": "#EAB308", "Stale": "#F97316", "False": "#EF4444", "Unverified": "#7C86A8" };

  const EXAMPLES = [
    { label: "Tech versions", text: "Python 3.9 is the latest stable release of Python. React 17 is the latest major release of React. Node.js 18 is currently an Active LTS release." },
    { label: "AI API pricing", text: "GPT-4 Turbo is the latest model in the GPT-4 family. GPT-4 Turbo API pricing is $10 per million input tokens and $30 per million output tokens." },
    { label: "Mixed 2026 claims", text: "Python 3.14 was released in 2025. React 17 is the latest major release of React. Node.js 24 is an Active LTS release." },
  ];

  const VIEWS = {
    dashboard: ["Dashboard", "Track, analyze and verify claims. Catch stale answers before they ship."],
    analytics: ["Analytics", "Freshness trends, verdict mix and model usage across every analysis."],
    projects: ["Claim Projects", "Group related audits — a docs page, a release note, a pricing table."],
    history: ["Historical Data", "Every claim ever checked, searchable and exportable."],
    settings: ["Settings", "Gateway, model, live search, profile and data."],
  };

  // ---------------------------------------------------------------- helpers
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const store = {
    get(k, d = null) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* storage unavailable */ } },
  };
  const clientId = store.get("vp.clientId") || (() => {
    const id = (crypto.randomUUID ? crypto.randomUUID() : String(Math.random()).slice(2) + Date.now()).replace(/-/g, "").slice(0, 24);
    store.set("vp.clientId", id);
    return id;
  })();

  // Access key (viewer or admin) — sent as a Bearer token; kept on this device only.
  const accessKey = {
    get: () => store.get("vp.accessKey", ""),
    set: (v) => store.set("vp.accessKey", v),
    clear: () => { try { localStorage.removeItem("vp.accessKey"); } catch { /* ignore */ } },
  };
  const authHeaders = () => {
    const key = accessKey.get();
    return { "X-Client-Id": clientId, ...(key ? { Authorization: `Bearer ${key}` } : {}) };
  };

  async function apiRaw(path, opts = {}) {
    const res = await fetch(path, {
      ...opts,
      headers: { "Content-Type": "application/json", ...authHeaders(), ...(opts.headers || {}) },
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    });
    if (!res.ok) {
      const isJson = (res.headers.get("content-type") || "").includes("json");
      const data = isJson ? await res.json() : await res.text();
      let msg = data && data.detail ? data.detail : `Request failed (${res.status})`;
      if (Array.isArray(msg)) msg = msg.map((d) => d.msg).join("; ");
      if (res.status === 401) promptAccessKey();
      const err = new Error(msg);
      err.status = res.status;
      throw err;
    }
    return res;
  }

  async function api(path, opts = {}) {
    const res = await apiRaw(path, opts);
    return (res.headers.get("content-type") || "").includes("json") ? res.json() : res.text();
  }

  const fmtNum = (n) => {
    if (n === null || n === undefined) return "—";
    if (n >= 1e6) return (n / 1e6).toFixed(1).replace(/\.0$/, "") + "M";
    if (n >= 10000) return (n / 1000).toFixed(1).replace(/\.0$/, "") + "K";
    return n.toLocaleString();
  };
  function timeAgo(iso) {
    const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
    if (s < 45) return "just now";
    if (s < 3600) return `${Math.round(s / 60)}m ago`;
    if (s < 86400) return `${Math.round(s / 3600)}h ago`;
    if (s < 86400 * 7) return `${Math.round(s / 86400)}d ago`;
    return new Date(iso).toLocaleDateString();
  }
  const fmtDate = (iso) => new Date(iso).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
  const hourLabel = (d) => d.toLocaleTimeString([], { hour: "numeric" }).replace(/\s/g, "").toUpperCase();
  const verdictMeta = (v) => VERDICTS[v] || VERDICTS.Unverified;
  const badge = (v) => { const m = verdictMeta(v); return `<span class="badge ${m.cls}">${icon(m.icon)}${esc(m.label)}</span>`; };
  const safeUrl = (u) => { try { const x = new URL(u); return ["http:", "https:"].includes(x.protocol) ? x.href : null; } catch { return null; } };
  const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

  function toast(message, kind = "info") {
    const colors = { info: "var(--accent)", ok: "var(--green)", warn: "var(--amber)", error: "var(--red)" };
    const icons = { info: "info", ok: "check", warn: "alert", error: "x" };
    const el = document.createElement("div");
    el.className = "toast";
    el.style.setProperty("--vc", colors[kind]);
    el.innerHTML = `${icon(icons[kind])}<div>${esc(message)}</div>`;
    $("#toasts").appendChild(el);
    setTimeout(() => { el.classList.add("out"); setTimeout(() => el.remove(), 260); }, kind === "error" ? 6500 : 3800);
  }

  // ---------------------------------------------------------------- tooltip
  const tip = $("#tooltip");
  function showTip(html, ev) { tip.innerHTML = html; tip.hidden = false; moveTip(ev); }
  function moveTip(ev) {
    const pad = 14, r = tip.getBoundingClientRect();
    let x = ev.clientX + pad, y = ev.clientY - r.height - pad;
    if (x + r.width > innerWidth - 8) x = ev.clientX - r.width - pad;
    if (y < 8) y = ev.clientY + pad;
    tip.style.left = x + "px"; tip.style.top = y + "px";
  }
  const hideTip = () => (tip.hidden = true);
  function bindTip(el, htmlFn) {
    el.addEventListener("mouseenter", (e) => showTip(htmlFn(), e));
    el.addEventListener("mousemove", moveTip);
    el.addEventListener("mouseleave", hideTip);
  }

  // ---------------------------------------------------------------- state
  const state = {
    session: null,
    view: "dashboard",
    status: null,
    stats: null,
    claims: [],
    projects: [],
    config: null,
    analyzing: false,
    lastRun: null,
    activityMetric: "searches",
    activeProject: null,
    newClaimKeys: new Set(),
  };

  // ---------------------------------------------------------------- access & roles
  const isAdmin = () => state.session?.role === "admin";

  function applyRole() {
    const role = state.session?.role || "none";
    document.body.dataset.role = role;
    if (role === "admin") return;
    $$("select[data-admin], input[data-admin]").forEach((el) => { el.disabled = true; });
    $$("[data-admin]").forEach((el) => { el.title = adminHint(); });
  }
  const adminHint = () => (state.session?.admin_configured
    ? "Admin only — enter the admin key in Settings → Access"
    : "Admin actions are disabled on this server");

  let accessPromptOpen = false;
  function promptAccessKey(message = "") {
    if (accessPromptOpen) return;
    accessPromptOpen = true;
    openModal("Access key required", `
      <p>This StaleBot server is private. Enter the access key (or admin key) you were given.</p>
      <form id="accessForm" autocomplete="off">
        <input class="field" id="accessInput" type="password" placeholder="Access key" style="width:100%" required>
        <p class="muted small" id="accessError" style="color:var(--red)">${esc(message)}</p>
        <div class="row-actions"><button class="btn btn-grad" type="submit">Unlock</button></div>
      </form>`, true);
    $("#modal [data-close]").hidden = true;
    $("#accessInput").focus();
    $("#accessForm").addEventListener("submit", async (e) => {
      e.preventDefault();
      const key = $("#accessInput").value.trim();
      const res = await fetch("/api/session", { headers: { Authorization: `Bearer ${key}` } });
      const info = await res.json();
      if (!info.role) { $("#accessError").textContent = "That key was not accepted."; return; }
      accessKey.set(key);
      location.reload();
    });
  }

  function renderAccess() {
    const s = state.session;
    if (!s) return;
    const roleText = s.role === "admin" ? (s.admin_open ? "Admin (local development — no key needed)" : "Admin") : s.role === "viewer" ? "Viewer" : "Locked";
    $("#accessKv").innerHTML = `
      <dt>Your role</dt><dd><span class="state ${s.role === "admin" ? "ok" : "warn"}">${esc(roleText)}</span></dd>
      <dt>Server mode</dt><dd>${s.production ? "Production" : "Development"}</dd>
      <dt>Access key</dt><dd>${s.auth_required ? "Required to use this server" : "Not required"}</dd>
      <dt>Analysis limit</dt><dd>${s.limits.analyze_per_minute}/min · ${s.limits.analyze_per_hour}/hour per visitor (admins exempt)</dd>
      <dt>Claims per check</dt><dd>Up to ${s.limits.max_claims}</dd>`;
    $("#accessSaved").textContent = accessKey.get() ? "A key is saved on this device." : "No key saved on this device.";
  }

  // ---------------------------------------------------------------- theme
  function applyTheme(theme) {
    if (theme !== "light") theme = "dark";
    document.documentElement.dataset.theme = theme;
    store.set("vp.theme", theme);
    $$("[data-theme-set]").forEach((b) => b.classList.toggle("on", b.dataset.themeSet === theme));
  }

  // ---------------------------------------------------------------- navigation
  function setView(view) {
    if (!VIEWS[view]) view = "dashboard";
    state.view = view;
    $$(".view").forEach((s) => (s.hidden = s.id !== `view-${view}`));
    $$(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
    $("#viewTitle").textContent = VIEWS[view][0];
    $("#viewSub").textContent = VIEWS[view][1];
    document.title = `${VIEWS[view][0]} · StaleBot`;
    closeSidebar();
    if (location.hash !== `#${view}`) history.replaceState(null, "", `#${view}`);
    if (view === "analytics") renderAnalytics();
    if (view === "projects") renderProjects();
    if (view === "history") loadHistory();
    if (view === "settings") renderSettings();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  const closeSidebar = () => $("#sidebar").classList.remove("open");

  // ---------------------------------------------------------------- profile
  function loadProfile() {
    const p = store.get("vp.profile", { name: "Analyst", role: "Local workspace" });
    $("#profileName").textContent = p.name || "Analyst";
    $("#profileRole").textContent = p.role || "Local workspace";
    $("#avatar").textContent = (p.name || "A").trim().split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
    $("#pfName").value = p.name || "";
    $("#pfRole").value = p.role || "";
  }

  // ---------------------------------------------------------------- status cards
  function renderStatus() {
    const s = state.status;
    if (!s) return;
    const g = $("#gatewayValue");
    const gw = {
      connected: ["Connected", "ok"], unavailable: ["Unreachable", "bad"], missing: ["Not configured", "warn"],
      checking: ["Checking…", "busy idle"], unknown: ["Not checked", "idle"],
    }[s.gateway.state] || ["Unknown", "idle"];
    g.textContent = gw[0];
    g.className = `state ${gw[1]}`;
    $("#gatewayCard").title = `Bifrost gateway${s.gateway.base_url ? " · " + s.gateway.base_url : ""}` + (s.gateway.checked_at ? `\nLast checked ${timeAgo(s.gateway.checked_at)}` : "") + "\nClick to re-check";
    const gIcon = $("#gatewayCard .sc-icon");
    gIcon.className = "sc-icon " + ({ ok: "c-green", bad: "c-red", warn: "c-amber" }[gw[1]] || "c-slate");

    const opt = s.model.options.find((o) => o.id === s.model.selected);
    $("#modelValue").textContent = opt ? opt.label.replace(" (default)", "") : s.model.selected;
    $("#modelCard").title = s.model.selected + (s.model.health === "unavailable" ? " — not available on gateway" : "");
    $("#modelMenu").innerHTML = s.model.options.map((o) => `
      <li role="option" tabindex="-1" data-model="${esc(o.id)}" aria-selected="${o.id === s.model.selected}">
        <span class="health ${esc(o.health)}" title="${o.health === "ok" ? "Responding" : o.health === "unavailable" ? "Not available on gateway" : "Not checked yet"}"></span>
        <span class="opt-main"><b>${esc(o.label)}</b><small>${esc(o.id)}</small></span>
        ${o.id === s.model.selected ? icon("check", "check") : ""}
      </li>`).join("");

    const sv = $("#searchValue");
    const sr = { active: ["Active", "ok"], ready: ["Ready", "ok"], failed: ["Failing", "bad"], missing: ["Not configured", "warn"] }[s.search.state] || ["Unknown", "idle"];
    sv.textContent = sr[0];
    sv.className = `state ${sr[1]}`;
    $("#searchCard").title = {
      active: "Tavily returned results on the last analysis", ready: "Tavily key configured — not used yet this session",
      failed: "The last Tavily searches failed", missing: "Set TAVILY_API_KEY in .env",
    }[s.search.state] || "";
    $("#searchCard .sc-icon").className = "sc-icon " + ({ ok: "c-violet", bad: "c-red", warn: "c-amber" }[sr[1]] || "c-slate");
    if ($("#view-settings").hidden === false) renderSettings();
  }

  async function refreshStatus(probe = false) {
    try {
      if (probe) {
        state.status && (state.status.gateway.state = "checking");
        renderStatus();
      }
      state.status = await api(probe ? "/api/status/refresh" : "/api/status", { method: probe ? "POST" : "GET" });
      renderStatus();
      // Another request may be probing the gateway right now; poll until it settles.
      if (state.status.gateway.state === "checking") setTimeout(() => refreshStatus(false), 1500);
      return state.status;
    } catch (e) {
      toast("Could not reach the StaleBot server: " + e.message, "error");
    }
  }

  function toggleModelMenu(open) {
    const menu = $("#modelMenu"), trig = $("#modelTrigger");
    const show = open ?? menu.hidden;
    menu.hidden = !show;
    trig.setAttribute("aria-expanded", String(show));
    if (show) (menu.querySelector('[aria-selected="true"]') || menu.firstElementChild)?.focus();
  }

  async function chooseModel(id) {
    toggleModelMenu(false);
    if (!state.status || id === state.status.model.selected) return;
    const label = state.status.model.options.find((o) => o.id === id)?.label || id;
    $("#modelValue").textContent = label;
    $("#gatewayValue").className = "state busy idle";
    $("#gatewayValue").textContent = "Checking…";
    try {
      state.status = await api("/api/model", { method: "POST", body: { model: id } });
      renderStatus();
      const h = state.status.model.health;
      if (h === "ok") toast(`Switched to ${label} — model is responding.`, "ok");
      else if (h === "unavailable") toast(`${label} is selected but the gateway rejected it. Check provider keys in Bifrost.`, "warn");
      else toast(`Switched to ${label}. Gateway could not be reached to test it.`, "warn");
    } catch (e) {
      toast(e.message, "error");
      refreshStatus();
    }
  }

  // ---------------------------------------------------------------- analyze
  const STEPS = ["Extracting claims", "Searching live sources", "Scoring freshness"];
  let loadingTimer = null;

  function showLoading() {
    const panel = $("#resultPanel");
    panel.hidden = false;
    const started = Date.now();
    const draw = () => {
      const secs = Math.floor((Date.now() - started) / 1000);
      // The backend runs as one request, so the stage is an estimate from elapsed time.
      const stage = secs < 4 ? 0 : secs < 14 ? 1 : 2;
      panel.innerHTML = `
        <div class="loading">
          <div class="pulse-ring"></div>
          <div class="loading-text">
            <b>${STEPS[stage]}…</b>
            <span>Checking claims against live web sources · ${secs}s elapsed</span>
            <div class="steps">${STEPS.map((s, i) => `<span class="step ${i < stage ? "done" : i === stage ? "on" : ""}">${i < stage ? "✓ " : ""}${s}</span>`).join("")}</div>
          </div>
        </div>`;
    };
    draw();
    loadingTimer = setInterval(draw, 1000);
  }

  function setAnalyzing(on) {
    state.analyzing = on;
    const btn = $("#analyzeBtn");
    btn.disabled = on;
    $("#claimInput").readOnly = on;
    $(".ab-icon", btn).innerHTML = on ? '<span class="spinner"></span>' : icon("wand");
    $("#analyzeLabel").textContent = on ? "Analyzing…" : "Analyze Claim";
  }

  async function analyze() {
    if (state.analyzing) return;
    const input = $("#claimInput");
    const text = input.value.trim();
    if (!text) {
      toast("Enter a headline, claim or AI answer to verify.", "warn");
      input.focus();
      return;
    }
    setAnalyzing(true);
    showLoading();
    $("#resultPanel").scrollIntoView({ behavior: "smooth", block: "nearest" });
    try {
      const res = await api("/api/analyze", { method: "POST", body: { text, project_id: $("#projectSelect").value || null } });
      clearInterval(loadingTimer);
      state.lastRun = res.run;
      state.stats = res.stats;
      state.status = res.status;
      const rows = claimRowsFromRun(res.run);
      rows.forEach((r) => state.newClaimKeys.add(r.run_id + ":" + r.index));
      state.claims = [...rows, ...state.claims];
      renderResult(res.run, $("#resultPanel"), true);
      renderStatus();
      renderDashboard();
      const n = res.run.results.length;
      const bad = res.run.results.filter((r) => ["Stale", "False"].includes(r.verdict)).length;
      if (!n) toast("No independently verifiable claims were found in that text.", "warn");
      else toast(`Analyzed ${n} claim${n > 1 ? "s" : ""} in ${(res.run.duration_ms / 1000).toFixed(1)}s${bad ? ` — ${bad} stale or false` : ""}.`, bad ? "warn" : "ok");
      setTimeout(() => state.newClaimKeys.clear(), 2000);
    } catch (e) {
      clearInterval(loadingTimer);
      $("#resultPanel").innerHTML = `
        <div class="error-box">
          <span class="sc-icon c-red">${icon("alert")}</span>
          <div><b>Analysis failed</b><p>${esc(e.message)}</p></div>
        </div>`;
      toast(e.message, "error");
      refreshStatus();
    } finally {
      setAnalyzing(false);
    }
  }

  function claimRowsFromRun(run) {
    return run.results.map((r, index) => ({
      run_id: run.id, index, claim: r.claim, verdict: r.verdict, status: r.status,
      freshness_score: r.freshness_score, updated_fact: r.updated_fact, created_at: run.created_at,
      model: run.model, project_id: run.project_id, source_count: (r.sources || []).length,
    }));
  }

  function renderResult(run, container, flash = false, focusIndex = null) {
    const counts = {};
    run.results.forEach((r) => (counts[r.verdict] = (counts[r.verdict] || 0) + 1));
    const sources = run.results.reduce((a, r) => a + (r.sources || []).length, 0);
    const project = state.projects.find((p) => p.id === run.project_id);
    container.innerHTML = `
      <div class="run-head">
        <div>
          <h3>${run.results.length ? `${run.results.length} claim${run.results.length > 1 ? "s" : ""} analyzed` : "No verifiable claims found"}</h3>
          <div class="run-meta">
            <span>${icon("clock")}${esc(fmtDate(run.created_at))}</span>
            <span>${icon("cpu")}${esc(run.model)}</span>
            <span>${icon("zap")}${(run.duration_ms / 1000).toFixed(1)}s</span>
            <span>${icon("globe")}${sources} source${sources === 1 ? "" : "s"} · ${run.search_successes} search${run.search_successes === 1 ? "" : "es"}${run.search_failures ? ` (${run.search_failures} failed)` : ""}</span>
            ${project ? `<span>${icon("folder")}${esc(project.name)}</span>` : ""}
          </div>
        </div>
        <div class="row-actions" style="margin:0">
          <button type="button" class="btn btn-ghost btn-sm" data-report="${esc(run.id)}" data-kind="full">${icon("download")}Full audit</button>
          <button type="button" class="btn btn-ghost btn-sm" data-report="${esc(run.id)}" data-kind="corrected">${icon("download")}Corrected summary</button>
        </div>
      </div>
      <div class="run-input">${esc(run.input_text)}</div>
      ${run.claims_truncated ? `<p class="muted small">${icon("info")} ${run.claims_truncated} more claim${run.claims_truncated > 1 ? "s were" : " was"} found but not checked — each check is limited to ${run.results.length} claims. Split long texts into smaller parts.</p>` : ""}
      ${run.results.length ? `<div class="summary-chips">${VERDICT_ORDER.filter((v) => counts[v]).map((v) => `${badge(v).replace("</span>", ` · ${counts[v]}</span>`)}`).join("")}</div>` : `
        <div class="empty">${icon("info")}<b>Nothing to verify</b>The model did not find factual, time-sensitive claims (versions, prices, releases, regulations…) in this text.</div>`}
      <div class="claims">
        ${run.results.map((r, i) => claimCard(r, i, flash)).join("")}
      </div>`;
    if (focusIndex !== null) container.querySelectorAll(".claim-card")[focusIndex]?.scrollIntoView({ block: "center" });
  }

  function claimCard(r, i, flash) {
    const m = verdictMeta(r.verdict);
    const srcs = (r.sources || []).map((s) => {
      const url = safeUrl(s.url);
      let host = "";
      try { host = url ? new URL(url).hostname.replace(/^www\./, "") : ""; } catch { /* ignore */ }
      return `<li>
        ${url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(s.title || host || "Source")}${icon("external")}</a>` : `<b>${esc(s.title || "Source")}</b>`}
        <small>${esc(host)}${s.published_date ? " · " + esc(s.published_date) : ""}</small>
        ${s.content ? `<p>${esc(s.content)}</p>` : ""}
      </li>`;
    }).join("");
    return `
      <article class="claim-card ${m.cls} ${flash ? "flash" : ""}">
        <div class="claim-top">${badge(r.verdict)}<span class="score"><b>${r.freshness_score}</b> / 100 freshness</span></div>
        <h4><span class="muted">#${i + 1}</span> ${esc(r.claim)}</h4>
        <div class="scorebar"><span style="width:${Math.max(2, r.freshness_score)}%"></span></div>
        <dl class="claim-grid">
          <div class="full"><dt>Current information</dt><dd>${esc(r.updated_fact)}</dd></div>
          <div><dt>Assessment</dt><dd>${esc(r.explanation)}</dd></div>
          <div><dt>Evidence analysis</dt><dd>${esc(r.evidence_analysis)}</dd></div>
          <div class="full"><dt>Recommended correction</dt><dd>${esc(r.recommended_correction)}</dd></div>
        </dl>
        <details class="sources" ${(r.sources || []).length ? "" : "open"}>
          <summary>Live sources (${(r.sources || []).length})</summary>
          ${srcs ? `<ul>${srcs}</ul>` : `<p class="muted small">No source evidence was returned for this claim.</p>`}
        </details>
      </article>`;
  }

  async function downloadReport(runId, kind) {
    try {
      const res = await apiRaw(`/api/runs/${encodeURIComponent(runId)}/report?kind=${encodeURIComponent(kind)}`);
      const name = (res.headers.get("content-disposition") || "").match(/filename="([^"]+)"/)?.[1] || `stalebot-${kind}-${runId}.md`;
      download(name, await res.text(), "text/markdown");
    } catch (e) { toast(e.message, "error"); }
  }

  async function openRun(runId, focusIndex = null) {
    openModal("Analysis details", '<div class="loading"><div class="pulse-ring"></div><div class="loading-text"><b>Loading…</b></div></div>');
    try {
      const run = await api(`/api/runs/${encodeURIComponent(runId)}`);
      renderResult(run, $("#modalBody"), false, focusIndex);
      hydrateIcons($("#modalBody"));
    } catch (e) {
      $("#modalBody").innerHTML = `<p>${esc(e.message)}</p>`;
    }
  }

  // ---------------------------------------------------------------- modal
  let lastFocus = null;
  function openModal(title, html, small = false) {
    lastFocus = document.activeElement;
    $("#modalTitle").textContent = title;
    $("#modalBody").innerHTML = html;
    $(".modal-box").classList.toggle("sm", small);
    $("#modal").hidden = false;
    document.body.style.overflow = "hidden";
    $("#modal [data-close]").focus();
  }
  function closeModal() {
    $("#modal").hidden = true;
    document.body.style.overflow = "";
    lastFocus?.focus?.();
  }
  function confirmDialog(title, message, confirmLabel = "Delete") {
    return new Promise((resolve) => {
      openModal(title, `<p>${esc(message)}</p><div class="row-actions"><button class="btn btn-danger" id="cfYes">${icon("trash")}${esc(confirmLabel)}</button><button class="btn btn-ghost" id="cfNo">Cancel</button></div>`, true);
      const done = (v) => { closeModal(); resolve(v); };
      $("#cfYes").onclick = () => done(true);
      $("#cfNo").onclick = () => done(false);
      $("#modal [data-close]").onclick = () => done(false);
    });
  }

  // ---------------------------------------------------------------- dashboard widgets
  function renderDashboard() {
    renderRecent();
    renderDonut();
    renderBars();
    renderMetrics();
    renderSideCard();
    renderBell();
  }

  function renderRecent() {
    const list = $("#recentList");
    const items = state.claims.slice(0, 5);
    if (!items.length) {
      list.innerHTML = `<li class="empty">${icon("search")}<b>No analyses yet</b>Your verified claims will appear here.</li>`;
      return;
    }
    list.innerHTML = items.map((c) => {
      const m = verdictMeta(c.verdict);
      const isNew = state.newClaimKeys.has(c.run_id + ":" + c.index);
      return `<li><button class="recent-item ${m.cls} ${isNew ? "new" : ""}" data-run="${esc(c.run_id)}" data-index="${c.index}" title="${esc(c.claim)}">
        <span class="v-dot">${icon(m.icon)}</span>
        <span class="recent-text"><b>${esc(c.claim)}</b><small>${esc(m.label)} · ${c.freshness_score}/100</small></span>
        <span class="recent-time" data-ago="${esc(c.created_at)}">${timeAgo(c.created_at)}</span>
        ${icon("chevron-right")}
      </button></li>`;
    }).join("");
  }

  function renderDonut() {
    const s = state.stats;
    const svgEl = $("#donut");
    const total = s ? s.total_claims : 0;
    const R = 54, C = 2 * Math.PI * R;
    let html = `<circle cx="70" cy="70" r="${R}" fill="none" stroke="rgba(124,134,168,.16)" stroke-width="14"/>`;
    if (total) {
      let offset = 0;
      VERDICT_ORDER.forEach((v) => {
        const n = s.distribution[v] || 0;
        if (!n) return;
        const len = (n / total) * C;
        const gap = len > 4 ? 2 : 0;
        html += `<circle class="seg" data-v="${esc(v)}" cx="70" cy="70" r="${R}" fill="none" stroke="${VERDICT_COLORS[v]}" stroke-width="14"
          stroke-dasharray="${Math.max(0, len - gap)} ${C}" stroke-dashoffset="${-offset}" stroke-linecap="butt"
          style="filter:drop-shadow(0 0 5px ${VERDICT_COLORS[v]}88)"/>`;
        offset += len;
      });
    }
    svgEl.innerHTML = html;
    $$(".seg", svgEl).forEach((c) => {
      const v = c.dataset.v, n = s.distribution[v];
      bindTip(c, () => `<b>${esc(verdictMeta(v).label)}</b><br><span class="tt-sub">${n} claim${n > 1 ? "s" : ""} · ${Math.round((n / total) * 100)}%</span>`);
    });
    $("#donutPct").textContent = s && s.freshness_rate !== null ? `${s.freshness_rate}%` : "—";
    $("#legend").innerHTML = VERDICT_ORDER.map((v) => {
      const n = s ? s.distribution[v] || 0 : 0;
      const pct = total ? Math.round((n / total) * 100) : 0;
      return `<li class="${verdictMeta(v).cls}" title="${n} claim${n === 1 ? "" : "s"}"><span class="sw"></span><span class="lbl">${esc(verdictMeta(v).short)}</span><span class="pct">${pct}%</span></li>`;
    }).join("");
    $("#donutFoot").innerHTML = total
      ? `Freshness rate (verified + partially true) across <b>${fmtNum(total)}</b> claims · avg. score <b>${s.avg_score}</b>/100`
      : "Analyze a claim to see the verdict mix.";
  }

  function barChart(container, values, labels, tipFn, { highlightLast = false, emptyText = "No activity yet" } = {}) {
    const max = Math.max(...values, 0);
    const niceMax = max <= 4 ? 4 : Math.ceil(max / 4) * 4;
    const ticks = [niceMax, (niceMax * 3) / 4, niceMax / 2, niceMax / 4, 0].map((t) => fmtNum(Math.round(t)));
    container.innerHTML = `
      <div class="bc-y">${ticks.map((t) => `<span>${t}</span>`).join("")}</div>
      <div class="bc-plot">
        ${values.map((v, i) => `<div class="bc-bar ${v ? "" : "zero"} ${highlightLast && i === values.length - 1 ? "current" : ""}" data-i="${i}"><span style="height:${v ? Math.max(3, (v / niceMax) * 100) : 0}%"></span></div>`).join("")}
        ${max === 0 ? `<div class="bc-empty">${esc(emptyText)}</div>` : ""}
      </div>
      <div class="bc-x">${labels.map((l) => (l ? `<span style="left:${l.pos}%">${esc(l.text)}</span>` : "")).join("")}</div>`;
    $$(".bc-bar", container).forEach((b) => bindTip(b, () => tipFn(Number(b.dataset.i))));
  }

  function renderBars() {
    const s = state.stats;
    if (!s) return;
    const metric = state.activityMetric;
    const hours = s.hourly_search;
    const values = hours.map((h) => (metric === "searches" ? h.searches : h.claims));
    const n = hours.length;
    const labels = [0, 6, 12, 18, n - 1].map((i) => ({ pos: ((i + 0.5) / n) * 100, text: i === n - 1 ? "Now" : hourLabel(new Date(hours[i].hour)) }));
    barChart($("#barChart"), values, labels, (i) => {
      const h = hours[i], start = new Date(h.hour), end = new Date(start.getTime() + 3600e3);
      return `<b>${hourLabel(start)} – ${hourLabel(end)}</b>${i === n - 1 ? " (current hour)" : ""}<br>
        <span class="tt-sub">${h.searches} live search${h.searches === 1 ? "" : "es"}${h.failures ? ` · ${h.failures} failed` : ""}<br>${h.claims} claim${h.claims === 1 ? "" : "s"} analyzed</span>`;
    }, { highlightLast: true, emptyText: metric === "searches" ? "No live searches in the last 24h" : "No claims analyzed in the last 24h" });
  }

  function sparkline(svgEl, data, color, id) {
    const pts = data.map((v, i) => [i, v]).filter(([, v]) => v !== null && v !== undefined);
    if (pts.length < 2) {
      svgEl.innerHTML = `<line x1="0" y1="38" x2="120" y2="38" stroke="${color}" stroke-opacity=".35" stroke-dasharray="3 4" stroke-width="1.5"/>`;
      return;
    }
    const xs = data.length - 1 || 1;
    const vals = pts.map((p) => p[1]);
    const min = Math.min(...vals), max = Math.max(...vals), span = max - min || 1;
    const P = pts.map(([i, v]) => [(i / xs) * 120, 40 - ((v - min) / span) * 34]);
    const line = P.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
    svgEl.innerHTML = `
      <defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity=".35"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>
      <path d="${line} L${P[P.length - 1][0]} 44 L${P[0][0]} 44 Z" fill="url(#${id})"/>
      <path d="${line}" fill="none" stroke="${color}" stroke-width="2" vector-effect="non-scaling-stroke" style="filter:drop-shadow(0 0 4px ${color})"/>`;
  }

  function trendChip(el, pct, { invert = false, suffix = "%", fallback = "" } = {}) {
    if (pct === null || pct === undefined) { el.className = "m-trend"; el.textContent = fallback; return; }
    const good = invert ? pct <= 0 : pct >= 0;
    el.className = "m-trend " + (good ? "trend-up" : "trend-down");
    el.textContent = `${pct >= 0 ? "↑" : "↓"} ${pct > 0 ? "+" : ""}${pct}${suffix}`;
  }

  function renderMetrics() {
    const s = state.stats;
    if (!s) return;
    $("#mTotal").textContent = fmtNum(s.total_claims);
    trendChip($("#mTotalTrend"), s.claims_trend_pct, { fallback: s.claims_24h ? `+${s.claims_24h} in last 24h` : "No claims in last 24h" });
    $("#mUsers").textContent = fmtNum(s.active_users_24h);
    trendChip($("#mUsersTrend"), s.active_users_trend_pct, { fallback: "unique browsers" });
    $("#mResp").textContent = s.avg_response_s !== null ? `${s.avg_response_s}s` : "—";
    trendChip($("#mRespTrend"), s.response_delta_s, { invert: true, suffix: "s", fallback: s.avg_response_s !== null ? "last 10 analyses" : "No analyses yet" });
    sparkline($("#sparkTotal"), s.series.cumulative_claims, "#22C55E", "gTotal");
    sparkline($("#sparkUsers"), s.series.active_users, "#8B5CF6", "gUsers");
    sparkline($("#sparkResp"), s.series.response_times, "#22D3EE", "gResp");
  }

  function renderSideCard() {
    const s = state.stats;
    if (!s || !s.total_claims) {
      $("#sideScore").textContent = "—";
      $("#sideMeter").style.width = "0";
      $("#sideMeta").textContent = "No claims analyzed yet";
      return;
    }
    $("#sideScore").textContent = s.avg_score;
    $("#sideMeter").style.width = s.avg_score + "%";
    const stale = (s.distribution.Stale || 0) + (s.distribution.False || 0);
    $("#sideMeta").textContent = `${stale} stale or false of ${fmtNum(s.total_claims)} claims`;
  }

  // ---------------------------------------------------------------- notifications
  const alerts = () => state.claims.filter((c) => c.verdict === "Stale" || c.verdict === "False");
  function renderBell() {
    const seen = store.get("vp.alertsSeen", null);
    const unseen = alerts().filter((c) => !seen || c.created_at > seen).length;
    const dot = $("#bellDot");
    dot.hidden = unseen === 0;
    dot.textContent = unseen > 9 ? "9+" : unseen;
    $("#bellBtn").setAttribute("aria-label", `Stale claim alerts (${unseen} new)`);
  }
  function toggleNotif(open) {
    const panel = $("#notifPanel");
    const show = open ?? panel.hidden;
    panel.hidden = !show;
    $("#bellBtn").setAttribute("aria-expanded", String(show));
    if (!show) return;
    const items = alerts().slice(0, 8);
    panel.innerHTML = `<h4>Stale &amp; false claims</h4>` + (items.length
      ? `<ul class="recent-list">${items.map((c) => {
        const m = verdictMeta(c.verdict);
        return `<li><button class="recent-item ${m.cls}" data-run="${esc(c.run_id)}" data-index="${c.index}"><span class="v-dot">${icon(m.icon)}</span><span class="recent-text"><b>${esc(c.claim)}</b><small>${esc(m.label)}</small></span><span class="recent-time">${timeAgo(c.created_at)}</span></button></li>`;
      }).join("")}</ul>`
      : `<div class="empty">${icon("check")}<b>All clear</b>No stale or false claims detected.</div>`);
    store.set("vp.alertsSeen", new Date().toISOString());
    renderBell();
  }

  // ---------------------------------------------------------------- analytics view
  async function renderAnalytics() {
    const s = state.stats;
    if (!s) return;
    const staleN = (s.distribution.Stale || 0) + (s.distribution.False || 0);
    let runs = [];
    try { runs = (await api("/api/runs?limit=1000")).items; } catch (e) { toast(e.message, "error"); }
    const sourcesUsed = runs.reduce((a, r) => a + r.search_successes, 0);
    $("#kpiRow").innerHTML = [
      ["Avg. freshness score", s.avg_score !== null ? `${s.avg_score}/100` : "—", "mean of all claim scores"],
      ["Stale or false rate", s.total_claims ? `${Math.round((staleN / s.total_claims) * 100)}%` : "—", `${staleN} of ${fmtNum(s.total_claims)} claims`],
      ["Analyses run", fmtNum(s.total_runs), `${fmtNum(s.total_claims)} claims extracted`],
      ["Live searches", fmtNum(sourcesUsed), "Tavily queries completed"],
    ].map(([l, v, sub]) => `<div class="card kpi"><small>${l}</small><b>${v}</b><span>${sub}</span></div>`).join("");

    // Line chart — average freshness score per day
    const days = s.series.days.map((d) => new Date(d + "T12:00:00"));
    lineChart($("#scoreChart"), s.series.avg_score, days);

    const daily = s.series.daily_claims;
    const labels = [0, 4, 9, 13].map((i) => ({ pos: ((i + 0.5) / 14) * 100, text: days[i].toLocaleDateString([], { month: "short", day: "numeric" }) }));
    barChart($("#dailyChart"), daily, labels, (i) => `<b>${days[i].toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" })}</b><br><span class="tt-sub">${daily[i]} claim${daily[i] === 1 ? "" : "s"} analyzed</span>`, { emptyText: "No claims in the last 14 days" });

    const total = s.total_claims || 1;
    $("#verdictBars").innerHTML = VERDICT_ORDER.map((v) => {
      const n = s.distribution[v] || 0;
      return `<div class="hbar-row ${verdictMeta(v).cls}"><span class="lbl">${esc(verdictMeta(v).label)}</span><span class="hbar-track"><span style="width:${(n / total) * 100}%"></span></span><span class="val">${n}</span></div>`;
    }).join("");

    const usage = {};
    runs.forEach((r) => { usage[r.model] = usage[r.model] || { runs: 0, ms: 0 }; usage[r.model].runs++; usage[r.model].ms += r.duration_ms; });
    const entries = Object.entries(usage).sort((a, b) => b[1].runs - a[1].runs);
    const maxRuns = Math.max(1, ...entries.map(([, u]) => u.runs));
    $("#modelBars").innerHTML = entries.length ? entries.map(([m, u]) => `
      <div class="hbar-row" title="${esc(m)} · avg ${(u.ms / u.runs / 1000).toFixed(1)}s per analysis"><span class="lbl">${esc(m.split("/").pop())}</span><span class="hbar-track"><span style="width:${(u.runs / maxRuns) * 100}%;background:var(--grad)"></span></span><span class="val">${u.runs}</span></div>`).join("")
      : `<div class="empty">${icon("cpu")}<b>No model usage yet</b></div>`;
  }

  function lineChart(container, values, dates) {
    const W = Math.max(280, container.clientWidth || 600), H = 230, L = 34, B = 24, T = 10, Rp = 10;
    const pts = values.map((v, i) => (v === null ? null : [L + (i / (values.length - 1)) * (W - L - Rp), T + (1 - v / 100) * (H - T - B), v, i]));
    const valid = pts.filter(Boolean);
    let path = "";
    let prev = null;
    pts.forEach((p) => { if (p) { path += (prev ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1) + " "; } prev = p; });
    const grid = [0, 25, 50, 75, 100].map((t) => { const y = T + (1 - t / 100) * (H - T - B); return `<line x1="${L}" x2="${W - Rp}" y1="${y}" y2="${y}" stroke="var(--line)"/><text x="${L - 6}" y="${y + 3.5}" text-anchor="end" font-size="10.5" fill="var(--muted)">${t}</text>`; }).join("");
    const xl = [0, 4, 9, 13].map((i) => `<text x="${L + (i / 13) * (W - L - Rp)}" y="${H - 6}" text-anchor="middle" font-size="10.5" fill="var(--muted)">${dates[i].toLocaleDateString([], { month: "short", day: "numeric" })}</text>`).join("");
    container.innerHTML = `<svg viewBox="0 0 ${W} ${H}">
      <defs><linearGradient id="lcG" x1="0" x2="1"><stop offset="0" stop-color="#8B5CF6"/><stop offset="1" stop-color="#22D3EE"/></linearGradient></defs>
      ${grid}${xl}
      ${path ? `<path d="${path}" fill="none" stroke="url(#lcG)" stroke-width="2.5" vector-effect="non-scaling-stroke" stroke-linejoin="round"/>` : ""}
      ${valid.map((p) => `<circle cx="${p[0]}" cy="${p[1]}" r="4.5" fill="#8B5CF6" stroke="var(--card-solid)" stroke-width="2" data-i="${p[3]}" style="cursor:pointer"/>`).join("")}
    </svg>${valid.length ? "" : `<div class="bc-empty">No scored claims in the last 14 days</div>`}`;
    $$("circle", container).forEach((c) => {
      const i = Number(c.dataset.i);
      bindTip(c, () => `<b>${dates[i].toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" })}</b><br><span class="tt-sub">Avg. freshness ${values[i]}/100</span>`);
    });
  }

  // ---------------------------------------------------------------- projects
  async function loadProjects() {
    try { state.projects = await api("/api/projects"); } catch (e) { toast(e.message, "error"); }
    const opts = state.projects.map((p) => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join("");
    const keep = (sel, first) => { const el = $(sel); const v = el.value; el.innerHTML = first + opts; el.value = state.projects.some((p) => p.id === v) ? v : ""; };
    keep("#projectSelect", '<option value="">No project</option>');
    keep("#historyProject", '<option value="">All projects</option>');
  }

  function renderProjects() {
    const grid = $("#projectGrid");
    if (!state.projects.length) {
      grid.innerHTML = `<div class="card panel empty" style="grid-column:1/-1">${icon("folder")}<b>No projects yet</b>Create one above, then pick it under the claim input so new analyses are filed there automatically.</div>`;
      $("#projectDetail").hidden = true;
      return;
    }
    grid.innerHTML = state.projects.map((p) => `
      <div class="card project-card ${state.activeProject === p.id ? "active" : ""}" data-project="${esc(p.id)}" tabindex="0" role="button">
        <h3>${icon("folder")}<span style="flex:1">${esc(p.name)}</span><button class="icon-sm" data-admin data-del-project="${esc(p.id)}" title="Delete project">${icon("trash")}</button></h3>
        <p>${esc(p.description || "No description")}</p>
        <div class="project-stats"><span><b>${p.runs}</b>analyses</span><span><b>${p.claims}</b>claims</span><span><b style="color:${p.stale ? "var(--v-stale)" : "inherit"}">${p.stale}</b>stale / false</span></div>
      </div>`).join("");
    if (state.activeProject) showProject(state.activeProject);
  }

  async function showProject(id) {
    state.activeProject = id;
    $$(".project-card").forEach((c) => c.classList.toggle("active", c.dataset.project === id));
    const p = state.projects.find((x) => x.id === id);
    const box = $("#projectDetail");
    if (!p) { box.hidden = true; return; }
    box.hidden = false;
    const { items } = await api(`/api/claims?limit=500&project_id=${encodeURIComponent(id)}`);
    box.innerHTML = `<div class="panel-head"><h2>${icon("folder", "h-icon")}${esc(p.name)} · claims</h2><span class="muted small">Created ${esc(fmtDate(p.created_at))}</span></div>
      ${items.length ? `<ul class="recent-list">${items.map((c) => { const m = verdictMeta(c.verdict); return `<li><button class="recent-item ${m.cls}" data-run="${esc(c.run_id)}" data-index="${c.index}"><span class="v-dot">${icon(m.icon)}</span><span class="recent-text"><b>${esc(c.claim)}</b><small>${esc(m.label)} · ${c.freshness_score}/100</small></span><span class="recent-time">${timeAgo(c.created_at)}</span>${icon("chevron-right")}</button></li>`; }).join("")}</ul>`
      : `<div class="empty">${icon("search")}<b>No claims in this project yet</b>Select it in the dashboard's project picker before analyzing, or assign past analyses from Historical Data.</div>`}`;
  }

  // ---------------------------------------------------------------- history
  let historyItems = [];
  async function loadHistory() {
    const q = $("#historySearch").value.trim(), v = $("#historyVerdict").value, p = $("#historyProject").value;
    const params = new URLSearchParams({ limit: "500", q, verdict: v, project_id: p });
    try {
      const res = await api(`/api/claims?${params}`);
      historyItems = res.items;
      const projOpts = (sel) => `<option value="">—</option>` + state.projects.map((x) => `<option value="${esc(x.id)}" ${x.id === sel ? "selected" : ""}>${esc(x.name)}</option>`).join("");
      $("#historyBody").innerHTML = historyItems.length ? historyItems.map((c) => `
        <tr data-run="${esc(c.run_id)}" data-index="${c.index}">
          <td class="nowrap" title="${esc(fmtDate(c.created_at))}">${timeAgo(c.created_at)}</td>
          <td class="claim-cell"><b>${esc(c.claim)}</b><small>${esc(c.updated_fact || "")}</small></td>
          <td>${badge(c.verdict)}</td>
          <td><b>${c.freshness_score}</b></td>
          <td class="nowrap hide-sm">${esc((c.model || "").split("/").pop())}</td>
          <td class="hide-sm"><select data-admin data-assign="${esc(c.run_id)}" aria-label="Assign project">${projOpts(c.project_id)}</select></td>
          <td><button class="icon-sm" data-admin data-del-run="${esc(c.run_id)}" title="Delete this analysis">${icon("trash")}</button></td>
        </tr>`).join("")
        : `<tr><td colspan="7"><div class="empty">${icon("history")}<b>No matching claims</b>${q || v || p ? "Try clearing the filters." : "Run an analysis from the Dashboard."}</div></td></tr>`;
      $("#historyFoot").textContent = res.total > historyItems.length ? `Showing ${historyItems.length} of ${res.total} claims` : `${res.total} claim${res.total === 1 ? "" : "s"}`;
    } catch (e) { toast(e.message, "error"); }
  }

  function exportCsv() {
    if (!historyItems.length) return toast("Nothing to export.", "warn");
    const cols = ["created_at", "claim", "verdict", "status", "freshness_score", "updated_fact", "model", "project", "run_id"];
    const projName = (id) => state.projects.find((p) => p.id === id)?.name || "";
    const cell = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const csv = [cols.join(","), ...historyItems.map((c) => cols.map((k) => cell(k === "project" ? projName(c.project_id) : c[k])).join(","))].join("\r\n");
    download(`stalebot-claims-${new Date().toISOString().slice(0, 10)}.csv`, csv, "text/csv");
  }
  function download(name, content, type) {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([content], { type }));
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  // ---------------------------------------------------------------- settings
  async function renderSettings() {
    renderAccess();
    try { state.config = await api("/api/config"); } catch (e) { return toast(e.message, "error"); }
    const c = state.config, s = state.status;
    const yes = (b) => (b ? '<span class="state ok">Configured</span>' : '<span class="state warn">Missing</span>');
    $("#gatewayKv").innerHTML = `
      <dt>Base URL</dt><dd>${c.base_url ? esc(c.base_url) : '<span class="muted">Hidden (admin only)</span>'}</dd>
      <dt>Virtual key</dt><dd>${yes(c.gateway_key_configured)}</dd>
      <dt>Status</dt><dd>${esc($("#gatewayValue").textContent)}${s && s.gateway.checked_at ? ` · checked ${timeAgo(s.gateway.checked_at)}` : ""}</dd>
      <dt>.env default model</dt><dd>${esc(c.default_model)}</dd>`;
    if (s) $("#settingsModel").innerHTML = s.model.options.map((o) => `<option value="${esc(o.id)}" ${o.id === s.model.selected ? "selected" : ""}>${esc(o.label)} — ${esc(o.id)}</option>`).join("");
    $("#searchKv").innerHTML = `<dt>Provider</dt><dd>Tavily (advanced depth, 3 results / claim)</dd><dt>API key</dt><dd>${yes(c.tavily_key_configured)}</dd><dt>Status</dt><dd>${esc($("#searchValue").textContent)}</dd>`;
    $("#dataKv").innerHTML = `<dt>Storage</dt><dd>${c.store_path ? esc(c.store_path) + " (server)" : '<span class="muted">Hidden (admin only)</span>'}</dd><dt>Analyses</dt><dd>${fmtNum(state.stats?.total_runs ?? 0)} runs · ${fmtNum(state.stats?.total_claims ?? 0)} claims</dd><dt>Max input</dt><dd>${fmtNum(c.max_input_chars)} characters</dd>`;
  }

  // ---------------------------------------------------------------- data loading
  async function loadAll() {
    const [stats, claims] = await Promise.all([api("/api/stats"), api("/api/claims?limit=50")]);
    state.stats = stats;
    state.claims = claims.items;
    renderDashboard();
  }

  // ---------------------------------------------------------------- events
  function bindEvents() {
    $$(".nav-item").forEach((b) => b.addEventListener("click", () => setView(b.dataset.view)));
    $$("[data-goto]").forEach((b) => b.addEventListener("click", () => setView(b.dataset.goto)));
    $("#profileBtn").addEventListener("click", () => setView("settings"));
    $("#menuBtn").addEventListener("click", () => $("#sidebar").classList.add("open"));
    $("#scrim").addEventListener("click", closeSidebar);
    $$("[data-theme-set]").forEach((b) => b.addEventListener("click", () => applyTheme(b.dataset.themeSet)));
    window.addEventListener("hashchange", () => setView(location.hash.slice(1)));
    window.addEventListener("resize", debounce(() => { if (state.view === "analytics") renderAnalytics(); }, 200));

    // analyze
    const input = $("#claimInput");
    const autoGrow = () => {
      input.style.height = "auto";
      input.style.height = Math.min(input.scrollHeight, 220) + "px";
      const n = input.value.length;
      $("#charCount").textContent = n ? `${n.toLocaleString()} / 8,000` : "";
    };
    input.addEventListener("input", autoGrow);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); analyze(); }
    });
    $("#analyzeForm").addEventListener("submit", (e) => { e.preventDefault(); analyze(); });
    $("#exampleChips").insertAdjacentHTML("beforeend", EXAMPLES.map((x, i) => `<button type="button" class="chip" data-example="${i}">${esc(x.label)}</button>`).join(""));
    $("#exampleChips").addEventListener("click", (e) => {
      const b = e.target.closest("[data-example]");
      if (!b) return;
      input.value = EXAMPLES[Number(b.dataset.example)].text;
      autoGrow();
      input.focus();
    });

    // status cards
    $("#gatewayCard").addEventListener("click", async () => {
      await refreshStatus(true);
      const st = state.status?.gateway.state;
      toast(st === "connected" ? "Gateway connected and model responding." : st === "missing" ? "Gateway is not configured — set BIFROST_* in .env." : "Gateway is unreachable.", st === "connected" ? "ok" : "warn");
    });
    $("#sideRecheck").addEventListener("click", () => $("#gatewayCard").click());
    $("#modelTrigger").addEventListener("click", (e) => { e.stopPropagation(); toggleModelMenu(); });
    $("#modelMenu").addEventListener("click", (e) => { const li = e.target.closest("[data-model]"); if (li) chooseModel(li.dataset.model); });
    $("#modelMenu").addEventListener("keydown", (e) => {
      const items = $$("#modelMenu li"), i = items.indexOf(document.activeElement);
      if (e.key === "ArrowDown") { e.preventDefault(); items[(i + 1) % items.length].focus(); }
      if (e.key === "ArrowUp") { e.preventDefault(); items[(i - 1 + items.length) % items.length].focus(); }
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); document.activeElement.click(); }
      if (e.key === "Escape") { toggleModelMenu(false); $("#modelTrigger").focus(); }
    });

    // activity chart metric
    $("#activityMetric").addEventListener("change", (e) => { state.activityMetric = e.target.value; renderBars(); });

    // report downloads (authenticated fetch, works in the result panel and the modal)
    document.addEventListener("click", (e) => {
      const b = e.target.closest("[data-report]");
      if (b) downloadReport(b.dataset.report, b.dataset.kind);
    });

    // viewers: admin-only controls explain themselves instead of failing on the server
    document.addEventListener("click", (e) => {
      const el = e.target.closest("[data-admin]");
      if (!el || isAdmin()) return;
      e.preventDefault();
      e.stopImmediatePropagation();
      toast(adminHint() + ".", "warn");
    }, true);

    // access key settings
    $("#accessForm").addEventListener("submit", async (e) => {
      e.preventDefault();
      const key = $("#accessKeyInput").value.trim();
      if (!key) return;
      const info = await (await fetch("/api/session", { headers: { Authorization: `Bearer ${key}` } })).json();
      if (!info.role) return toast("That key was not accepted.", "error");
      accessKey.set(key);
      toast(`Key saved — you are now ${info.role === "admin" ? "an admin" : "a viewer"}.`, "ok");
      location.reload();
    });
    $("#accessClear").addEventListener("click", () => {
      accessKey.clear();
      toast("Key removed from this device.", "ok");
      location.reload();
    });

    // open run details from any list
    document.addEventListener("click", (e) => {
      const item = e.target.closest(".recent-item[data-run]");
      if (item) { toggleNotif(false); openRun(item.dataset.run, Number(item.dataset.index)); return; }
      if (!e.target.closest(".model-card")) toggleModelMenu(false);
      if (!e.target.closest(".notif-wrap")) $("#notifPanel").hidden = true;
    });
    $("#bellBtn").addEventListener("click", (e) => { e.stopPropagation(); toggleNotif(); });

    // modal
    $("#modal").addEventListener("click", (e) => {
      if (accessPromptOpen) return;
      if (e.target.id === "modal" || e.target.closest("[data-close]")) closeModal();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      if (!$("#modal").hidden && !accessPromptOpen) closeModal();
      toggleModelMenu(false);
      $("#notifPanel").hidden = true;
      closeSidebar();
    });

    // projects
    $("#projectForm").addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        const p = await api("/api/projects", { method: "POST", body: { name: $("#projectName").value, description: $("#projectDesc").value } });
        $("#projectForm").reset();
        await loadProjects();
        state.activeProject = p.id;
        renderProjects();
        toast(`Project “${p.name}” created.`, "ok");
      } catch (err) { toast(err.message, "error"); }
    });
    $("#projectGrid").addEventListener("click", async (e) => {
      const del = e.target.closest("[data-del-project]");
      if (del) {
        e.stopPropagation();
        const p = state.projects.find((x) => x.id === del.dataset.delProject);
        if (!(await confirmDialog("Delete project?", `“${p?.name}” will be removed. Its analyses stay in Historical Data, unassigned.`))) return;
        await api(`/api/projects/${encodeURIComponent(del.dataset.delProject)}`, { method: "DELETE" });
        if (state.activeProject === del.dataset.delProject) state.activeProject = null;
        await loadProjects();
        renderProjects();
        toast("Project deleted.", "ok");
        return;
      }
      const card = e.target.closest("[data-project]");
      if (card) showProject(card.dataset.project);
    });
    $("#projectGrid").addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.dataset.project) showProject(e.target.dataset.project); });

    // history
    $("#historySearch").addEventListener("input", debounce(loadHistory, 250));
    $("#historyVerdict").innerHTML += VERDICT_ORDER.map((v) => `<option value="${esc(v)}">${esc(verdictMeta(v).label)}</option>`).join("");
    $("#historyVerdict").addEventListener("change", loadHistory);
    $("#historyProject").addEventListener("change", loadHistory);
    $("#exportCsv").addEventListener("click", exportCsv);
    $("#historyBody").addEventListener("click", async (e) => {
      if (e.target.closest("select")) return;
      const del = e.target.closest("[data-del-run]");
      if (del) {
        if (!(await confirmDialog("Delete analysis?", "This removes the analysis and all of its claims from history. This cannot be undone."))) return;
        await api(`/api/runs/${encodeURIComponent(del.dataset.delRun)}`, { method: "DELETE" });
        toast("Analysis deleted.", "ok");
        await Promise.all([loadAll(), loadHistory(), loadProjects()]);
        return;
      }
      const row = e.target.closest("tr[data-run]");
      if (row) openRun(row.dataset.run, Number(row.dataset.index));
    });
    $("#historyBody").addEventListener("change", async (e) => {
      const sel = e.target.closest("[data-assign]");
      if (!sel) return;
      try {
        await api(`/api/runs/${encodeURIComponent(sel.dataset.assign)}`, { method: "PATCH", body: { project_id: sel.value || null } });
        toast(sel.value ? "Analysis moved to project." : "Removed from project.", "ok");
        await loadProjects();
        loadHistory();
      } catch (err) { toast(err.message, "error"); }
    });

    // settings
    $("#settingsModel").addEventListener("change", (e) => chooseModel(e.target.value));
    $("#testGateway").addEventListener("click", async () => {
      const b = $("#testGateway");
      b.disabled = true;
      $("#testResult").textContent = "Testing…";
      await refreshStatus(true);
      b.disabled = false;
      const st = state.status?.gateway.state;
      $("#testResult").textContent = st === "connected" ? (state.status.model.health === "ok" ? "✓ Gateway and model OK" : "Gateway OK, model rejected") : st === "missing" ? "Not configured" : "✗ Gateway unreachable";
    });
    $("#profileForm").addEventListener("submit", (e) => {
      e.preventDefault();
      store.set("vp.profile", { name: $("#pfName").value.trim() || "Analyst", role: $("#pfRole").value.trim() });
      loadProfile();
      toast("Profile saved.", "ok");
    });
    $("#exportJson").addEventListener("click", async () => {
      const runs = await api("/api/runs?limit=1000");
      download(`stalebot-history-${new Date().toISOString().slice(0, 10)}.json`, JSON.stringify(runs.items, null, 2), "application/json");
    });
    $("#clearHistory").addEventListener("click", async () => {
      if (!(await confirmDialog("Clear all history?", "Every stored analysis and claim will be permanently deleted. Projects are kept. This cannot be undone.", "Clear history"))) return;
      await api("/api/runs", { method: "DELETE" });
      $("#resultPanel").hidden = true;
      await Promise.all([loadAll(), loadProjects()]);
      renderSettings();
      toast("History cleared.", "ok");
    });
  }

  // ---------------------------------------------------------------- init
  async function init() {
    hydrateIcons();
    applyTheme(document.documentElement.dataset.theme || "dark");
    loadProfile();
    bindEvents();
    try {
      state.session = await (await fetch("/api/session", { headers: authHeaders() })).json();
    } catch (e) {
      toast("Could not reach the StaleBot server: " + e.message, "error");
      return;
    }
    applyRole();
    if (!state.session.role) {
      promptAccessKey(accessKey.get() ? "The saved key is no longer valid." : "");
      return;
    }
    setView(location.hash.slice(1) || "dashboard");
    const status = await refreshStatus(false);
    try { await Promise.all([loadAll(), loadProjects()]); } catch (e) { toast("Could not load dashboard data: " + e.message, "error"); }
    if (status && status.gateway.state === "unknown") refreshStatus(true); // first probe of this server run

    // keep timestamps and shared data fresh (another tab may analyze too)
    setInterval(() => $$("[data-ago]").forEach((el) => (el.textContent = timeAgo(el.dataset.ago))), 30000);
    setInterval(async () => {
      if (state.analyzing || document.hidden) return;
      try { await loadAll(); state.status = await api("/api/status"); renderStatus(); } catch { /* transient */ }
    }, 60000);
  }

  // MutationObserver keeps icons hydrated for any HTML injected later.
  new MutationObserver(() => { hydrateIcons(); if (state.session && !isAdmin()) applyRole(); })
    .observe(document.body, { childList: true, subtree: true });
  init();
})();
