import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity, ArrowUpRight, BarChart3, Bell, BriefcaseBusiness, CalendarDays, Check, ChevronDown,
  CircleAlert, Clock, Database, Gauge, Link2, LogOut, Mail, MapPin, Menu, MessageSquarePlus, Mic, Plus, RefreshCw,
  Search, Send, Settings2, ShieldCheck, Sparkles, Square, Star, Trash2, UploadCloud, Users, Video, X, Zap,
  Truck, TrendingUp, Calculator, Save,
} from "lucide-react";
import "./styles.css";

const API = "/api";
const readToken = () => sessionStorage.getItem("sales_token") || "";

async function request(path, options = {}) {
  const headers = { ...(options.body ? { "Content-Type": "application/json" } : {}), ...(options.headers || {}) };
  const token = readToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${API}${path}`, { ...options, headers });
  if (response.status === 401) {
    sessionStorage.removeItem("sales_token");
    window.dispatchEvent(new Event("auth-expired"));
  }
  if (!response.ok) {
    let message = "Request failed";
    try { message = (await response.json()).detail || message; } catch { /* response may not be JSON */ }
    throw new Error(message);
  }
  return response.status === 204 ? null : response.json();
}

function App() {
  const [config, setConfig] = useState(null);
  const [user, setUser] = useState(null);
  const [health, setHealth] = useState(null);
  const [tab, setTab] = useState("dash");
  const [notice, setNotice] = useState(null);
  const [mobileNav, setMobileNav] = useState(false);
  const [tour, setTour] = useState(() => !sessionStorage.getItem(TOUR_KEY));

  useEffect(() => {
    requestPublicConfig().then(setConfig).catch((error) => setNotice({ type: "error", text: error.message }));
    const expire = () => setUser(null);
    window.addEventListener("auth-expired", expire);
    return () => window.removeEventListener("auth-expired", expire);
  }, []);

  useEffect(() => {
    if (!config) return;
    if (readToken()) request("/auth/me").then(setUser).catch(() => setUser(null));
  }, [config]);

  useEffect(() => {
    if (notice) {
      const timer = setTimeout(() => setNotice(null), 4200);
      return () => clearTimeout(timer);
    }
  }, [notice]);

  if (!config || (readToken() && !user)) return <LoadingScreen />;
  if (!user) return <SignInPage config={config} onLogin={setUser} onNotice={setNotice} />;

  const logout = () => { sessionStorage.removeItem("sales_token"); setUser(null); };
  return (
    <div className="shell">
      <aside className={`sidebar ${mobileNav ? "open" : ""}`}>
        <div className="brand"><img src="/KalisoftAI-logo.png" alt="Kalisoft AI" className="brand-logo" /><span>Kalisoft <b>AI</b></span></div>
        <div className="workspace-label">Revenue workspace</div>
        <nav>
          <NavItem icon={Gauge} label="Dashboard" active={tab === "dash"} onClick={() => { setTab("dash"); setMobileNav(false); }} />
          <NavItem icon={Mic} label="Field desk" active={tab === "field"} onClick={() => { setTab("field"); setMobileNav(false); }} />
          <NavItem icon={Activity} label="Overview" active={tab === "overview"} onClick={() => { setTab("overview"); setMobileNav(false); }} />
          <NavItem icon={Users} label="Contacts" active={tab === "contacts"} onClick={() => { setTab("contacts"); setMobileNav(false); }} />
          <NavItem icon={CalendarDays} label="Events" active={tab === "events"} onClick={() => { setTab("events"); setMobileNav(false); }} />
          <NavItem icon={Mail} label="Email connections" active={tab === "email"} onClick={() => { setTab("email"); setMobileNav(false); }} />
          <NavItem icon={BriefcaseBusiness} label="Signal desk" active={tab === "signals"} onClick={() => { setTab("signals"); setMobileNav(false); }} />
          <NavItem icon={Send} label="Outreach" active={tab === "outreach"} onClick={() => { setTab("outreach"); setMobileNav(false); }} />
          <NavItem icon={Clock} label="Scheduler" active={tab === "scheduler"} onClick={() => { setTab("scheduler"); setMobileNav(false); }} />
          <NavItem icon={BarChart3} label="KPIs" active={tab === "kpis"} onClick={() => { setTab("kpis"); setMobileNav(false); }} />
          <NavItem icon={MessageSquarePlus} label="Feedback" active={tab === "feedback"} onClick={() => { setTab("feedback"); setMobileNav(false); }} />
          <NavItem icon={Zap} label="Feedback pipeline" active={tab === "pipeline"} onClick={() => { setTab("pipeline"); setMobileNav(false); }} />
          <NavItem icon={Truck} label="ERP & forecast" active={tab === "erp"} onClick={() => { setTab("erp"); setMobileNav(false); }} />
          <NavItem icon={ShieldCheck} label="UAT & ops" active={tab === "uat"} onClick={() => { setTab("uat"); setMobileNav(false); }} />
          <NavItem icon={Star} label="Recent changes" active={tab === "changelog"} onClick={() => { setTab("changelog"); setMobileNav(false); }} />
        </nav>
        <div className="sidebar-bottom">
          <div className="security-note"><ShieldCheck size={16} /><span>Private workspace<br /><small>Google verified access</small></span></div>
          <button className="profile-row" onClick={logout}><span className="avatar">{user.name?.[0] || user.email[0]}</span><span className="profile-copy"><b>{user.name || "Workspace user"}</b><small>{user.email}</small></span><LogOut size={16} /></button>
        </div>
      </aside>
      {mobileNav && <button className="scrim" aria-label="Close menu" onClick={() => setMobileNav(false)} />}
      <main className="main">
        <header className="topbar"><button className="icon-button menu-button" onClick={() => setMobileNav(true)} aria-label="Open menu"><Menu size={20} /></button><div><div className="eyebrow">KALISOFT AI / SALES PIPELINE</div><h1>{tab === "dash" ? "Kalika command center" : tab === "field" ? "Field desk" : tab === "overview" ? "Good work starts with a clear signal." : tab === "contacts" ? "Contacts" : tab === "email" ? "Email connections" : tab === "events" ? "Events" : tab === "signals" ? "Signal desk" : tab === "scheduler" ? "Scheduler" : tab === "kpis" ? "Business KPIs" : tab === "feedback" ? "Feedback" : tab === "pipeline" ? "Feedback pipeline" : tab === "erp" ? "ERP & sales forecast" : tab === "uat" ? "UAT & operations" : tab === "changelog" ? "Recent changes" : "Outreach"}</h1></div><div className="topbar-actions"><EnvBadge env={health?.env} /><button className="text-button" onClick={() => setTour(true)}><Sparkles size={15} /> Take the tour</button><span className="live-dot"><i /> API healthy</span><button className="icon-button" aria-label="Settings"><Settings2 size={18} /></button></div></header>
        {tab === "dash" && <KalikaDash onNavigate={setTab} onNotice={setNotice} />}
        {tab === "field" && <FieldDesk onNotice={setNotice} user={user} />}
        {tab === "overview" && <Overview onNavigate={setTab} onNotice={setNotice} health={health} setHealth={setHealth} />}
        {tab === "contacts" && <Contacts onNotice={setNotice} />}
        {tab === "email" && <EmailConnections onNotice={setNotice} config={config} />}
        {tab === "events" && <Events onNotice={setNotice} />}
        {tab === "signals" && <Signals onNotice={setNotice} />}
        {tab === "outreach" && <Outreach onNotice={setNotice} />}
        {tab === "scheduler" && <Scheduler onNotice={setNotice} />}
        {tab === "kpis" && <Kpis onNotice={setNotice} />}
        {tab === "feedback" && <Feedback onNotice={setNotice} />}
        {tab === "pipeline" && <FeedbackPipeline onNotice={setNotice} />}
        {tab === "erp" && <ErpDashboard onNotice={setNotice} />}
        {tab === "uat" && <UatOps onNotice={setNotice} />}
        {tab === "changelog" && <RecentChanges />}
      </main>
      {tour && <Walkthrough onClose={() => setTour(false)} />}
      {notice && <div className={`toast ${notice.type === "error" ? "error" : ""}`}><span>{notice.type === "error" ? <CircleAlert size={17} /> : <Check size={17} />}</span>{notice.text}<button onClick={() => setNotice(null)} aria-label="Dismiss"><X size={15} /></button></div>}
    </div>
  );
}

async function requestPublicConfig() { const response = await fetch(`${API}/config`); if (!response.ok) throw new Error("API configuration unavailable"); return response.json(); }

function LoadingScreen() { return <div className="loading-screen"><img src="/KalisoftAI-logo.png" alt="Kalisoft AI" className="brand-logo" /><span>Preparing your workspace...</span></div>; }

function Login({ config, onLogin, onNotice }) {
  const [email, setEmail] = useState("ai.solutions@kalisoftai.in");
  const [busy, setBusy] = useState(false);
  const [pwForm, setPwForm] = useState({ username: "", password: "" });
  const [pwBusy, setPwBusy] = useState(false);
  const login = async (idToken) => {
    setBusy(true);
    try { const result = await request("/auth/google", { method: "POST", body: JSON.stringify({ id_token: idToken }) }); sessionStorage.setItem("sales_token", result.access_token); onLogin(await request("/auth/me")); }
    catch (error) { onNotice({ type: "error", text: error.message }); }
    finally { setBusy(false); }
  };
  const passwordLogin = async (event) => {
    event.preventDefault();
    setPwBusy(true);
    try {
      const result = await request("/auth/password", { method: "POST", body: JSON.stringify(pwForm) });
      sessionStorage.setItem("sales_token", result.access_token);
      onLogin(await request("/auth/me"));
    } catch (error) { onNotice({ type: "error", text: error.message }); }
    finally { setPwBusy(false); }
  };
  useEffect(() => {
    if (!config.google_client_id) return undefined;
    const renderGoogleButton = () => {
      if (!window.google?.accounts?.id) return;
      window.google.accounts.id.initialize({ client_id: config.google_client_id, callback: (response) => login(response.credential) });
      window.google.accounts.id.renderButton(document.getElementById("google-button"), { theme: "outline", size: "large", width: 320, shape: "rectangular" });
    };
    renderGoogleButton();
    const poll = window.setInterval(renderGoogleButton, 100);
    const stop = window.setTimeout(() => window.clearInterval(poll), 10000);
    return () => { window.clearInterval(poll); window.clearTimeout(stop); };
  }, [config.google_client_id]);
  return <div className="login-page"><div className="login-art"><div className="art-grid" /><div className="art-copy"><div className="brand"><img src="/KalisoftAI-logo.png" alt="Kalisoft AI" className="brand-logo" /><span>Kalisoft <b>AI</b></span><img src="/kalika-logo.svg" alt="Kalika" className="brand-logo kalika-mark" /><span className="kalika-word">Kalika</span></div><h1>Turn scattered signals into your next best conversation.</h1><p>A focused workspace for the people, companies, and market cues that move your pipeline forward.</p><div className="art-stat"><span><b>01</b> verified workspace</span><span><b>02</b> live signal streams</span></div></div></div><section className="login-panel"><div className="panel-inner"><div className="eyebrow">PRIVATE SALES WORKSPACE</div><h2>Welcome back.</h2><p className="muted">Sign in with your verified Google account to continue.</p><div id="google-button" className={config.google_client_id ? "google-button" : "hidden"} />{!config.google_client_id && <div className="config-warning"><CircleAlert size={18} /><span>Google Sign-In is not configured on this environment.</span></div>}<form className="pw-login" onSubmit={passwordLogin}><label>Kalika username &amp; password</label><input value={pwForm.username} onChange={(e) => setPwForm({ ...pwForm, username: e.target.value })} placeholder="username" autoComplete="username" required /><input type="password" value={pwForm.password} onChange={(e) => setPwForm({ ...pwForm, password: e.target.value })} placeholder="password" autoComplete="current-password" required /><button className="primary-button" type="submit" disabled={pwBusy}>{pwBusy ? "Signing in..." : "Sign in"}</button><small>Demo: kalika / kalika123 (admin) · field / field123 (field executive)</small></form>{config.dev_mode && <div className="dev-login"><label>Local development access</label><div className="input-action"><input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@company.com" /><button onClick={() => login(`dev:${email}`)} disabled={busy}>{busy ? "Checking..." : "Enter"}<ArrowUpRight size={16} /></button></div><small>Enabled only when AUTH_DEV_MODE is true.</small></div>}<div className="login-footer"><ShieldCheck size={16} /> Your session is protected with short-lived tokens.</div></div></section></div>;
}

function NavItem({ icon: Icon, label, active, onClick }) { return <button className={`nav-item ${active ? "active" : ""}`} onClick={onClick}><Icon size={18} /><span>{label}</span>{active && <ChevronDown size={15} className="nav-caret" />}</button>; }

function EnvBadge({ env }) {
  const normalized = (env || "development").toLowerCase();
  const style = normalized === "production" ? { background: "#e5f6e5", color: "#187a2f", borderColor: "#187a2f" } : normalized === "staging" ? { background: "#fff4d6", color: "#8a5a00", borderColor: "#8a5a00" } : { background: "#e0ecff", color: "#1d4fa3", borderColor: "#1d4fa3" };
  const label = normalized === "production" ? "PROD" : normalized === "staging" ? "UAT" : "DEV";
  return <span title={`Environment: ${normalized}`} style={{ ...style, border: "1px solid", borderRadius: 999, padding: "2px 10px", fontSize: 11, fontWeight: 700, letterSpacing: 0.5 }}>{label}</span>;
}

const RECENT_CHANGES_SAMPLE = [
  { module: "Quotation Management", area: "Sales", status: "shipped", progress: 100, date: "Oct 2026", detail: "Draft -> Sent -> Accepted / Rejected / Expired, revisions, PDF generation and email delivery." },
  { module: "Purchase GST & Discount", area: "Purchase", status: "shipped", progress: 100, date: "Oct 2026", detail: "Line total = qty x rate, less discount %, plus GST %; applied on create, update and import." },
  { module: "Production Auto-Status", area: "Production", status: "shipped", progress: 100, date: "Oct 2026", detail: "PLANNED -> IN PRODUCTION -> COMPLETED with completion_pct, balance_qty and completion_date." },
  { module: "Sample-Data Onboarding", area: "Packaging", status: "in_progress", progress: 60, date: "Q4 2026", detail: "Read-only Jabil / Amber quote sample, packaging leads and GCS KPI inventory for new users." },
  { module: "Update-Progress UI", area: "Platform", status: "in_progress", progress: 35, date: "Q4 2026", detail: "Timeline and per-module progress bars kept in sync with the recent-changes document." },
  { module: "MCP Polymer Price Calculator", area: "MCP", status: "planned", progress: 0, date: "TBD", detail: "Local-only MCP tool for polymer price calculation; not part of the deployed service." },
];

const CHANGE_STATUS_STYLE = {
  shipped: { label: "Shipped", background: "#e5f6e5", color: "#187a2f", borderColor: "#187a2f" },
  in_progress: { label: "In progress", background: "#fff4d6", color: "#8a5a00", borderColor: "#8a5a00" },
  planned: { label: "Planned", background: "#e0ecff", color: "#1d4fa3", borderColor: "#1d4fa3" },
};

function RecentChanges() {
  const total = RECENT_CHANGES_SAMPLE.length;
  const shipped = RECENT_CHANGES_SAMPLE.filter((item) => item.status === "shipped").length;
  const overall = total ? Math.round(RECENT_CHANGES_SAMPLE.reduce((sum, item) => sum + item.progress, 0) / total) : 0;
  return (
    <div className="content">
      <div className="welcome-row">
        <div>
          <div className="section-kicker">LATEST UPDATE PROGRESS</div>
          <h2>Recent changes</h2>
          <p className="muted">{shipped} of {total} modules shipped · {overall}% overall complete (sample data).</p>
        </div>
        <span className="section-kicker">{overall}% overall</span>
      </div>
      <div className="panel" style={{ padding: "12px 16px", marginBottom: 16 }}>
        <div className="section-kicker" style={{ marginBottom: 8 }}>OVERALL PROGRESS</div>
        <div style={{ height: 10, borderRadius: 999, background: "#e6ece9", overflow: "hidden" }}>
          <div style={{ width: `${overall}%`, height: "100%", background: "#187a2f" }} />
        </div>
      </div>
      <div className="two-column">
        {RECENT_CHANGES_SAMPLE.map((item) => {
          const badge = CHANGE_STATUS_STYLE[item.status] || CHANGE_STATUS_STYLE.planned;
          return (
            <section className="panel" key={item.module}>
              <div className="panel-heading">
                <div>
                  <div className="section-kicker">{item.area} · {item.date}</div>
                  <h3>{item.module}</h3>
                </div>
                <span style={{ ...badge, border: "1px solid", borderRadius: 999, padding: "2px 10px", fontSize: 11, fontWeight: 700 }}>{badge.label}</span>
              </div>
              <p className="muted">{item.detail}</p>
              <div style={{ height: 8, borderRadius: 999, background: "#e6ece9", overflow: "hidden", marginTop: 10 }}>
                <div style={{ width: `${item.progress}%`, height: "100%", background: badge.color }} />
              </div>
              <small className="muted">{item.progress}%</small>
            </section>
          );
        })}
      </div>
      <p className="muted" style={{ marginTop: 12 }}>Sample data for the latest update progress view; edit <b>RECENT_CHANGES_SAMPLE</b> to refresh.</p>
    </div>
  );
}

function HowItWorks({ stats }) {
  const steps = [
    { icon: UploadCloud, label: "Import", value: stats ? `${stats.total ?? 0} contacts` : "—", tab: "contacts" },
    { icon: Sparkles, label: "Classified", value: stats ? `${Object.keys(stats.by_intent || {}).length} intents` : "—", tab: "contacts" },
    { icon: Search, label: "Signals", value: "LinkedIn · Reddit · YouTube", tab: "signals" },
    { icon: Send, label: "Outreach", value: "Human-approved", tab: "outreach" },
  ];
  return (
    <div className="panel" style={{ marginBottom: 16, padding: "12px 16px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <span className="section-kicker" style={{ marginRight: 8 }}>HOW IT WORKS</span>
        {steps.map((s, i) => (
          <span key={s.label} style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }} title={s.label}>
              <s.icon size={15} /><b>{s.label}</b><small className="muted">{s.value}</small>
            </span>
            {i < steps.length - 1 && <ArrowUpRight size={14} className="muted" />}
          </span>
        ))}
      </div>
    </div>
  );
}

function Overview({ onNavigate, onNotice, health, setHealth }) {
  const [stats, setStats] = useState(null);
  const [contacts, setContacts] = useState([]);
  const refresh = async () => { try { const [nextStats, nextContacts, nextHealth] = await Promise.all([request("/contacts/stats"), request("/contacts?q=") , request("/health")]); setStats(nextStats); setContacts(nextContacts.slice(0, 5)); setHealth(nextHealth); } catch (error) { onNotice({ type: "error", text: error.message }); } };
  useEffect(() => { refresh(); }, []);
  return <div className="content"><div className="welcome-row"><div><div className="section-kicker">MONDAY, SEPTEMBER 14, 2026</div><h2>Pipeline at a glance</h2><p className="muted">A quiet view of what needs your attention next.</p></div><button className="primary-button" onClick={() => onNavigate("contacts")}><Plus size={17} /> Add contact</button></div><HowItWorks stats={stats} /><div className="metric-grid"><Metric label="Total contacts" value={stats?.total ?? "--"} detail="across your workspace" icon={Users} /><Metric label="Ready to reach" value={stats ? Object.values(stats.by_intent || {}).reduce((sum, value) => sum + value, 0) : "--"} detail="classified signals" icon={Sparkles} accent /><Metric label="API status" value={health?.status === "healthy" ? "Live" : "--"} detail={health?.database === "ok" ? "database connected" : "checking services"} icon={Activity} /></div><div className="two-column"><section className="panel"><div className="panel-heading"><div><div className="section-kicker">RECENTLY ADDED</div><h3>Latest contacts</h3></div><button className="text-button" onClick={() => onNavigate("contacts")}>View all <ArrowUpRight size={15} /></button></div><ContactRows contacts={contacts} /></section><section className="panel signal-panel"><div className="panel-heading"><div><div className="section-kicker">SYSTEM PULSE</div><h3>Connected services</h3></div><button className="icon-button" onClick={refresh} aria-label="Refresh services"><RefreshCw size={17} /></button></div><Service status={health?.database === "ok"} icon={Database} label="PostgreSQL / SQLite" value={health?.database === "ok" ? "Connected" : "Degraded"} /><Service status={health?.gcs_available} icon={UploadCloud} label="Google Cloud Storage" value={health?.gcs_available ? "Available" : "Optional"} /><Service status={health?.google_signin_configured} icon={ShieldCheck} label="Google Sign-In" value={health?.google_signin_configured ? "Configured" : "Not configured"} /></section></div><SecurityTrust /></div>;
}

function Metric({ label, value, detail, icon: Icon, accent }) { return <div className={`metric ${accent ? "accent" : ""}`}><div className="metric-icon"><Icon size={18} /></div><div className="metric-label">{label}</div><div className="metric-value">{value}</div><div className="metric-detail">{detail}</div></div>; }
function Events({ onNotice }) {
  const [summary, setSummary] = useState(null);
  const [events, setEvents] = useState([]);
  const [recipients, setRecipients] = useState([]);
  const [messages, setMessages] = useState({ items: [], counts: {} });
  const [selectedId, setSelectedId] = useState(null);
  const [filters, setFilters] = useState({ q: "", status: "", mode: "" });
  const [picked, setPicked] = useState(() => new Set());
  const [recipientQuery, setRecipientQuery] = useState("");
  const [template, setTemplate] = useState("");
  const [preview, setPreview] = useState("");
  const [scheduledAt, setScheduledAt] = useState("");
  const [busy, setBusy] = useState(false);

  const selected = events.find((event) => event.id === selectedId) || null;

  const load = async () => {
    try {
      const params = new URLSearchParams();
      if (filters.q) params.set("q", filters.q);
      if (filters.status) params.set("status", filters.status);
      if (filters.mode) params.set("mode", filters.mode);
      const query = params.toString();
      const [nextSummary, nextEvents, nextRecipients, nextMessages] = await Promise.all([
        request("/events/summary"),
        request(query ? `/events?${query}` : "/events"),
        request("/events/recipients?limit=300"),
        request("/events/messages/all?limit=60"),
      ]);
      setSummary(nextSummary);
      setEvents(nextEvents);
      setRecipients(nextRecipients);
      setMessages(nextMessages);
      setSelectedId((current) => (nextEvents.some((event) => event.id === current) ? current : nextEvents[0]?.id ?? null));
    } catch (error) { onNotice({ type: "error", text: error.message }); }
  };

  useEffect(() => { load(); }, [filters]);
  useEffect(() => { if (selectedId) refreshTemplate(); }, [selectedId]);

  const importWorkbook = async (event) => {
    const files = Array.from(event.target.files || []);
    event.target.value = "";
    if (!files.length) return;
    setBusy(true);
    try {
      const body = new FormData();
      body.append("file", files[0]);
      const token = readToken();
      const response = await fetch(`${API}/events/import`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body,
      });
      if (!response.ok) {
        let message = "Workbook import failed";
        try { message = (await response.json()).detail || message; } catch { /* non-JSON error */ }
        throw new Error(message);
      }
      const result = await response.json();
      onNotice({
        type: "success",
        text: `Imported ${result.events_imported} events and ${result.contacts_imported} contacts (${result.events_updated + result.contacts_updated} updated).`,
      });
      load();
    } catch (error) { onNotice({ type: "error", text: error.message }); }
    finally { setBusy(false); }
  };

  const importLocal = async () => {
    setBusy(true);
    try {
      const body = new FormData();
      body.append("include_contacts", "true");
      const token = readToken();
      const response = await fetch(`${API}/events/import`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body,
      });
      if (!response.ok) {
        let message = "Workbook import failed";
        try { message = (await response.json()).detail || message; } catch { /* non-JSON error */ }
        throw new Error(message);
      }
      const result = await response.json();
      onNotice({ type: "success", text: `Loaded ${result.source}: ${result.events_imported} new events, ${result.contacts_imported} new contacts.` });
      load();
    } catch (error) { onNotice({ type: "error", text: error.message }); }
    finally { setBusy(false); }
  };

  const refreshTemplate = async (recipientId) => {
    if (!selectedId) return;
    const params = new URLSearchParams();
    if (recipientId) params.set("recipient_id", String(recipientId));
    try {
      const result = await request(`/events/${selectedId}/message-template?${params.toString()}`);
      setTemplate(result.template);
      setPreview(result.preview);
    } catch (error) { onNotice({ type: "error", text: error.message }); }
  };

  const previewFor = async (recipientId) => {
    if (!selectedId) return;
    const params = new URLSearchParams({ template });
    if (recipientId) params.set("recipient_id", String(recipientId));
    try {
      const result = await request(`/events/${selectedId}/message-template?${params.toString()}`);
      setPreview(result.preview);
    } catch (error) { onNotice({ type: "error", text: error.message }); }
  };

  const queueMessages = async () => {
    if (!selectedId || !picked.size) return onNotice({ type: "error", text: "Select at least one recipient." });
    setBusy(true);
    try {
      const body = { recipient_ids: [...picked], template };
      if (scheduledAt) body.scheduled_at = new Date(scheduledAt).toISOString();
      const result = await request(`/events/${selectedId}/schedule`, { method: "POST", body: JSON.stringify(body) });
      onNotice({
        type: "success",
        text: result.queued
          ? `Queued ${result.queued} message(s) for ${new Date(result.scheduled_at).toLocaleString()}. Review them before sending.`
          : "Nothing new to queue — these recipients are already queued for this event.",
      });
      setPicked(new Set());
      load();
    } catch (error) { onNotice({ type: "error", text: error.message }); }
    finally { setBusy(false); }
  };

  const sendMessage = async (message) => {
    if (!window.confirm(`Send this WhatsApp message to ${message.phone} now?`)) return;
    try {
      const result = await request(`/events/messages/${message.id}/send`, { method: "POST", body: "{}" });
      onNotice({ type: result.ok ? "success" : "error", text: result.ok ? `Message sent to ${message.phone}.` : result.error });
      load();
    } catch (error) { onNotice({ type: "error", text: error.message }); }
  };

  const cancelMessage = async (message) => {
    try {
      await request(`/events/messages/${message.id}/cancel`, { method: "POST", body: "{}" });
      onNotice({ type: "success", text: "Queued message cancelled." });
      load();
    } catch (error) { onNotice({ type: "error", text: error.message }); }
  };

  const sendDue = async () => {
    if (!window.confirm("Send every queued message whose schedule time has passed?")) return;
    setBusy(true);
    try {
      const result = await request("/events/messages/send-due", { method: "POST", body: "{}" });
      onNotice({ type: "success", text: `Dispatched ${result.sent} message(s); ${result.failed} failed.` });
      load();
    } catch (error) { onNotice({ type: "error", text: error.message }); }
    finally { setBusy(false); }
  };

  const togglePicked = (id) => setPicked((current) => {
    const next = new Set(current);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  const visibleRecipients = recipients.filter((recipient) => {
    const needle = recipientQuery.trim().toLowerCase();
    if (!needle) return true;
    return `${recipient.name} ${recipient.company} ${recipient.phone} ${recipient.notes}`.toLowerCase().includes(needle);
  });

  return (
    <div className="content">
      <div className="page-heading">
        <div>
          <div className="section-kicker">EVENTS &amp; OUTREACH</div>
          <h2>Events</h2>
          <p className="muted">Every exhibition, webinar and meetup from the event workbook, with WhatsApp outreach queued per recipient.</p>
        </div>
        <div className="button-row">
          <label className="secondary-button upload-button">
            <UploadCloud size={16} /> {busy ? "Importing..." : "Upload workbook"}
            <input type="file" accept=".xlsx" hidden onChange={importWorkbook} />
          </label>
          <button className="primary-button" onClick={importLocal} disabled={busy}><Database size={16} /> Load local workbook</button>
        </div>
      </div>

      <div className="metric-grid">
        <Metric icon={CalendarDays} label="Events tracked" value={String(summary?.events ?? 0)} detail={`${summary?.upcoming ?? 0} upcoming · ${summary?.past ?? 0} past`} />
        <Metric icon={Clock} label="Next 30 days" value={String(summary?.next_30_days ?? 0)} detail={`${summary?.unscheduled ?? 0} without a confirmed date`} />
        <Metric icon={Users} label="Recipients" value={String(summary?.recipients ?? 0)} detail="Contacts sheet from the workbook" />
        <Metric icon={Send} label="Queued messages" value={String(summary?.queued_messages ?? 0)} detail={`${summary?.sent_messages ?? 0} sent · ${summary?.failed_messages ?? 0} failed`} />
      </div>

      <div className="filter-grid">
        <label className="search-field"><Search size={15} /><input value={filters.q} onChange={(event) => setFilters({ ...filters, q: event.target.value })} placeholder="Search events, organiser, venue" /></label>
        <select value={filters.status} onChange={(event) => setFilters({ ...filters, status: event.target.value })}>
          <option value="">All statuses</option>
          <option value="upcoming">Upcoming</option>
          <option value="past">Past</option>
          <option value="unscheduled">Unscheduled</option>
        </select>
        <select value={filters.mode} onChange={(event) => setFilters({ ...filters, mode: event.target.value })}>
          <option value="">All formats</option>
          <option value="in_person">In person</option>
          <option value="online">Online</option>
          <option value="hybrid">Hybrid</option>
        </select>
      </div>

      <div className="two-column">
        <section className="panel">
          <div className="panel-heading">
            <div><div className="section-kicker">SHOWCASE</div><h3>{events.length} event(s)</h3></div>
            <button className="icon-button" onClick={load} aria-label="Refresh events"><RefreshCw size={17} /></button>
          </div>
          <div className="contact-list" role="list">
            {events.map((event) => (
              <button
                className={`contact-row event-row ${event.id === selectedId ? "selected" : ""}`}
                key={event.id}
                role="listitem"
                onClick={() => setSelectedId(event.id)}
              >
                <span className={`event-date-badge ${event.status}`}>
                  <b>{event.starts_at ? new Date(event.starts_at).getDate() : "--"}</b>
                  <small>{event.starts_at ? new Date(event.starts_at).toLocaleString("en", { month: "short" }) : "TBA"}</small>
                </span>
                <span className="contact-main">
                  <b>{event.title}</b>
                  <small>
                    {[
                      event.starts_at ? new Date(event.starts_at).toLocaleString() : event.when_text || "Date to be confirmed",
                      event.location,
                      event.mode === "in_person" ? "In person" : event.mode === "online" ? "Online" : event.mode === "hybrid" ? "Hybrid" : "",
                      event.attendance,
                    ].filter(Boolean).join(" · ")}
                  </small>
                </span>
                <span className={`event-status ${event.status}`}>{event.status}</span>
              </button>
            ))}
            {!events.length && (
              <div className="empty-state">
                <CalendarDays size={22} />
                <p>No events found.</p>
                <small>Upload the event workbook or adjust the filters.</small>
              </div>
            )}
          </div>
        </section>

        <section className="panel">
          {!selected ? (
            <div className="empty-state"><CalendarDays size={22} /><p>Select an event.</p><small>Event details and outreach appear here.</small></div>
          ) : (
            <EventSchedulePanel
              event={selected}
              recipients={visibleRecipients}
              recipientQuery={recipientQuery}
              setRecipientQuery={setRecipientQuery}
              picked={picked}
              togglePicked={togglePicked}
              template={template}
              setTemplate={setTemplate}
              preview={preview}
              onPreview={() => previewFor(visibleRecipients.find((recipient) => picked.has(recipient.id))?.id)}
              scheduledAt={scheduledAt}
              setScheduledAt={setScheduledAt}
              onQueue={queueMessages}
              busy={busy}
            />
          )}
        </section>
      </div>

      <section className="panel table-panel" style={{ marginTop: 14 }}>
        <div className="table-toolbar">
          <div><div className="section-kicker">OUTREACH QUEUE</div><h3>WhatsApp messages</h3></div>
          <div className="button-row">
            <button className="secondary-button" onClick={sendDue} disabled={busy || !messages.counts.queued}><RefreshCw size={15} /> Send due now</button>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Recipient</th><th>Message</th><th>Status</th><th>Scheduled (UTC)</th><th /></tr>
            </thead>
            <tbody>
              {messages.items.map((message) => {
                const due = message.scheduled_at && new Date(message.scheduled_at) <= new Date();
                return (
                  <tr key={message.id}>
                    <td className="table-person">{message.phone}</td>
                    <td><span className="message-snippet">{message.body}</span></td>
                    <td><span className={`event-status ${message.status}`}>{message.status}</span>{message.error && <small className="message-error">{message.error}</small>}</td>
                    <td>{message.scheduled_at ? new Date(message.scheduled_at).toLocaleString() : "—"}</td>
                    <td>
                      {message.status === "queued" && (
                        <div className="button-row">
                          <button className="text-button" onClick={() => sendMessage(message)} disabled={!due} title={due ? "Send now" : "Scheduled for later — cancel to change"}><Send size={14} /> Send</button>
                          <button className="text-button danger-button" onClick={() => cancelMessage(message)}><X size={14} /> Cancel</button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
              {!messages.items.length && (
                <tr><td colSpan={5}><div className="empty-state"><Send size={22} /><p>No messages queued yet.</p><small>Select an event and queue a WhatsApp message for your contacts.</small></div></td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function EventSchedulePanel({ event, recipients, recipientQuery, setRecipientQuery, picked, togglePicked, template, setTemplate, preview, onPreview, scheduledAt, setScheduledAt, onQueue, busy }) {
  return (
    <div className="event-detail">
      <div className="panel-heading">
        <div><div className="section-kicker">EVENT</div><h3>{event.title}</h3></div>
        <span className={`event-status ${event.status}`}>{event.status}</span>
      </div>
      <ul className="event-facts">
        <li><Clock size={14} /> {event.starts_at ? new Date(event.starts_at).toLocaleString() : event.when_text || "Date to be confirmed"}</li>
        {event.location && <li><MapPin size={14} /> {event.location}</li>}
        {event.organiser && <li><BriefcaseBusiness size={14} /> {event.organiser}</li>}
        {event.attendance && <li><Users size={14} /> {event.attendance}</li>}
        {event.event_url && <li><Link2 size={14} /> <a href={event.event_url} target="_blank" rel="noreferrer noopener">Event page</a></li>}
      </ul>
      {event.about && <p className="event-about">{event.about.slice(0, 420)}{event.about.length > 420 ? "…" : ""}</p>}
      {event.todo && <p className="event-todo"><b>To do:</b> {event.todo}</p>}

      <div className="form-heading" style={{ marginTop: 20 }}>
        <div><div className="section-kicker">STEP 1</div><h3>Choose recipients</h3></div>
        <span className="muted">{picked.size} selected</span>
      </div>
      <div className="search-field" style={{ width: "100%", margin: "11px 0" }}>
        <Search size={15} />
        <input value={recipientQuery} onChange={(event) => setRecipientQuery(event.target.value)} placeholder="Filter contacts" />
      </div>
      <div className="recipient-picker">
        {recipients.slice(0, 60).map((recipient) => (
          <label className="recipient-row" key={recipient.id}>
            <input type="checkbox" checked={picked.has(recipient.id)} onChange={() => togglePicked(recipient.id)} />
            <span className="contact-avatar">{(recipient.name || recipient.company || "?").slice(0, 1).toUpperCase()}</span>
            <span className="contact-main">
              <b>{recipient.name || recipient.company || "Unnamed contact"}</b>
              <small>{[recipient.company, recipient.phone].filter(Boolean).join(" · ")}</small>
            </span>
          </label>
        ))}
        {!recipients.length && <div className="empty-state"><Users size={20} /><p>No contacts match.</p><small>Import the workbook contacts sheet first.</small></div>}
      </div>

      <div className="form-heading" style={{ marginTop: 20 }}>
        <div><div className="section-kicker">STEP 2</div><h3>Message &amp; schedule</h3></div>
        <button className="text-button" onClick={onPreview}>Refresh preview</button>
      </div>
      <textarea className="event-template" value={template} onChange={(event) => setTemplate(event.target.value)} rows={9} />
      <div className="muted" style={{ margin: "7px 0 12px" }}>Variables: {"{{name}}"}, {"{{company}}"}, {"{{event_title}}"}, {"{{event_dates}}"}, {"{{where_lines}}"}</div>
      {preview && <pre className="message-preview">{preview}</pre>}
      <label className="switch-row" style={{ marginTop: 14 }}>
        Send at (UTC)
        <input className="inline-input" type="datetime-local" value={scheduledAt} onChange={(event) => setScheduledAt(event.target.value)} />
      </label>
      <button className="primary-button" style={{ width: "100%", justifyContent: "center", marginTop: 12 }} onClick={onQueue} disabled={busy || !picked.size}>
        <Send size={16} /> Queue {picked.size || ""} message(s)
      </button>
      <p className="muted" style={{ marginTop: 10 }}>Queued messages never send on their own — review each one, then use “Send” or “Send due now”.</p>
    </div>
  );
}

function Service({ status, icon: Icon, label, value }) { return <div className="service-row"><span className="service-icon"><Icon size={16} /></span><span className="service-name">{label}</span><span className={`status ${status ? "ok" : "muted-status"}`}><i />{value}</span></div>; }
function ContactRows({ contacts, compact = false, onDelete }) { if (!contacts.length) return <div className="empty-state"><Users size={22} /><p>No contacts yet.</p><small>Add your first contact to start building the pipeline.</small></div>; return <div className="contact-list">{contacts.map((contact) => <div className="contact-row" key={contact.id}><span className="contact-avatar">{(contact.name || contact.company || "?")[0].toUpperCase()}</span><span className="contact-main"><b>{contact.name || "Unnamed contact"}</b><small>{contact.company || contact.email}</small></span><span className="contact-tag">{contact.intent || "unclassified"}</span>{!compact && onDelete && <button className="icon-button danger-button" onClick={() => onDelete(contact.id)} aria-label="Delete contact"><Trash2 size={15} /></button>}</div>)}</div>; }

function Contacts({ onNotice }) {
  const [contacts, setContacts] = useState([]); const [query, setQuery] = useState(""); const [stats, setStats] = useState(null); const [showForm, setShowForm] = useState(false); const [busy, setBusy] = useState(false); const [uploadPrefix, setUploadPrefix] = useState("");
  const [form, setForm] = useState({ company: "", name: "", email: "", phone: "", intent: "", context: "" });
  const load = async () => { try { const params = query ? `?q=${encodeURIComponent(query)}` : ""; const [rows, nextStats] = await Promise.all([request(`/contacts${params}`), request("/contacts/stats")]); setContacts(rows); setStats(nextStats); } catch (error) { onNotice({ type: "error", text: error.message }); } };
  useEffect(() => { load(); }, [query]);
  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));
  const add = async (event) => { event.preventDefault(); setBusy(true); try { await request("/contacts", { method: "POST", body: JSON.stringify(form) }); setForm({ company: "", name: "", email: "", phone: "", intent: "", context: "" }); setShowForm(false); onNotice({ type: "success", text: "Contact added to your workspace." }); load(); } catch (error) { onNotice({ type: "error", text: error.message }); } finally { setBusy(false); } };
  const remove = async (id) => { if (!window.confirm("Remove this contact?")) return; try { await request(`/contacts/${id}`, { method: "DELETE" }); onNotice({ type: "success", text: "Contact removed." }); load(); } catch (error) { onNotice({ type: "error", text: error.message }); } };
  const importGcs = async () => { try { const result = await request("/contacts/import/gcs", { method: "POST" }); onNotice({ type: "success", text: `Imported ${result.imported}; skipped ${result.skipped}.` }); load(); } catch (error) { onNotice({ type: "error", text: error.message }); } };
  const uploadContacts = async (event) => { const files = Array.from(event.target.files || []); event.target.value = ""; if (!files.length && !uploadPrefix.trim()) return; const body = new FormData(); files.forEach((file) => body.append("files", file)); if (uploadPrefix.trim()) body.append("gcs_prefix", uploadPrefix.trim()); try { const token = readToken(); const response = await fetch(`${API}/contacts/upload`, { method: "POST", headers: token ? { Authorization: `Bearer ${token}` } : {}, body }); if (!response.ok) { let message = "Upload failed"; try { message = (await response.json()).detail || message; } catch { /* non-JSON error */ } throw new Error(message); } const result = await response.json(); onNotice({ type: "success", text: `Imported ${result.total_imported} contacts, skipped ${result.skipped + result.gcs_skipped}.` }); load(); } catch (error) { onNotice({ type: "error", text: error.message }); } };
  const syncGcsPath = async () => { if (!uploadPrefix.trim()) return onNotice({ type: "error", text: "Enter a GCS prefix first." }); const body = new FormData(); body.append("gcs_prefix", uploadPrefix.trim()); try { const token = readToken(); const response = await fetch(`${API}/contacts/upload`, { method: "POST", headers: token ? { Authorization: `Bearer ${token}` } : {}, body }); if (!response.ok) { let message = "GCS sync failed"; try { message = (await response.json()).detail || message; } catch { /* non-JSON error */ } throw new Error(message); } const result = await response.json(); onNotice({ type: "success", text: `Synced ${result.gcs_imported} from GCS, skipped ${result.gcs_skipped}.` }); load(); } catch (error) { onNotice({ type: "error", text: error.message }); } };
  return <div className="content"><div className="page-heading"><div><div className="section-kicker">YOUR PIPELINE</div><h2>Contacts</h2><p className="muted">Search, classify, and keep every relationship useful.</p></div><div className="button-row"><label className="secondary-button upload-button"><UploadCloud size={16} /> Upload files<input type="file" multiple accept=".csv,.xlsx,.xls,.vcf,.json" onChange={uploadContacts} hidden /></label><button className="secondary-button" onClick={importGcs}><Database size={16} /> Import GCS</button><button className="primary-button" onClick={() => setShowForm(!showForm)}><Plus size={17} /> New contact</button></div></div><div className="panel form-panel" style={{ marginBottom: 16 }}><div className="form-grid"><input placeholder="GCS prefix, e.g. all-sales-contacts-data/" value={uploadPrefix} onChange={(event) => setUploadPrefix(event.target.value)} /><button type="button" className="secondary-button" onClick={syncGcsPath}><Database size={16} /> Sync GCS path</button></div><small className="muted">Upload multiple CSV / Excel / VCF / JSON files above, or sync a GCS prefix into your workspace.</small></div>{stats && <div className="mini-stats"><span><b>{stats.total}</b> total</span><span><b>{Object.keys(stats.by_domain || {}).length}</b> domains</span><span><b>{Object.keys(stats.by_intent || {}).length}</b> intents</span></div>}{showForm && <form className="panel form-panel" onSubmit={add}><div className="form-heading"><div><div className="section-kicker">NEW RECORD</div><h3>Capture a contact</h3></div><button type="button" className="icon-button" onClick={() => setShowForm(false)} aria-label="Close"><X size={18} /></button></div><div className="form-grid"><input required placeholder="Email address *" type="email" value={form.email} onChange={(event) => update("email", event.target.value)} /><input placeholder="Full name" value={form.name} onChange={(event) => update("name", event.target.value)} /><input placeholder="Company" value={form.company} onChange={(event) => update("company", event.target.value)} /><input placeholder="Phone" value={form.phone} onChange={(event) => update("phone", event.target.value)} /><select value={form.intent} onChange={(event) => update("intent", event.target.value)}><option value="">Intent, auto-classify</option><option>procurement</option><option>sales</option><option>hiring</option><option>partnership</option><option>support</option><option>general</option></select><input placeholder="Context or note" value={form.context} onChange={(event) => update("context", event.target.value)} /></div><button className="primary-button" disabled={busy}>{busy ? "Saving..." : "Save contact"}<ArrowUpRight size={16} /></button></form>}<section className="panel table-panel"><div className="table-toolbar"><div className="search-field"><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search name, company, email" /></div><span className="muted">{contacts.length} shown</span></div><div className="table-wrap"><table><thead><tr><th>Contact</th><th>Company</th><th>Email</th><th>Signal</th><th>Source</th><th /></tr></thead><tbody>{contacts.map((contact) => <tr key={contact.id}><td><div className="table-person"><span className="contact-avatar small">{(contact.name || contact.company || "?")[0].toUpperCase()}</span><span><b>{contact.name || "Unnamed"}</b><small>{contact.domain || "Unclassified"}</small></span></div></td><td>{contact.company || "—"}</td><td>{contact.email}</td><td><span className="contact-tag">{contact.intent || "general"}</span></td><td className="muted">{contact.source}</td><td><button className="icon-button danger-button" onClick={() => remove(contact.id)} aria-label="Delete contact"><Trash2 size={15} /></button></td></tr>)}</tbody></table>{!contacts.length && <div className="empty-state"><Search size={22} /><p>No matching contacts.</p><small>Try another search or add a new record.</small></div>}</div></section></div>;
}

function LegacyEmailConnections({ onNotice }) { const [connections, setConnections] = useState([]); const [form, setForm] = useState({ email_address: "", imap_host: "imap.gmail.com", imap_port: 993, smtp_host: "smtp.gmail.com", smtp_port: 587, password: "" }); const [show, setShow] = useState(false); const load = () => request("/email/connections").then(setConnections).catch((error) => onNotice({ type: "error", text: error.message })); useEffect(() => { load(); }, []); const add = async (event) => { event.preventDefault(); try { await request("/email/connections", { method: "POST", body: JSON.stringify(form) }); setShow(false); setForm({ email_address: "", imap_host: "imap.gmail.com", imap_port: 993, smtp_host: "smtp.gmail.com", smtp_port: 587, password: "" }); onNotice({ type: "success", text: "Email connection saved encrypted." }); load(); } catch (error) { onNotice({ type: "error", text: error.message }); } }; const test = async (id) => { try { const result = await request(`/email/connections/${id}/test`, { method: "POST" }); onNotice({ type: result.is_connected ? "success" : "error", text: result.is_connected ? "IMAP and SMTP are connected." : "Connection test failed." }); load(); } catch (error) { onNotice({ type: "error", text: error.message }); } }; return <div className="content"><div className="page-heading"><div><div className="section-kicker">OUTREACH INFRASTRUCTURE</div><h2>Email connections</h2><p className="muted">Credentials are encrypted before they are stored.</p></div><button className="primary-button" onClick={() => setShow(!show)}><Plus size={17} /> Add mailbox</button></div>{show && <form className="panel form-panel" onSubmit={add}><div className="form-grid"><input required type="email" placeholder="Mailbox email" value={form.email_address} onChange={(event) => setForm({ ...form, email_address: event.target.value })} /><input required type="password" placeholder="App password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} /><input placeholder="IMAP host" value={form.imap_host} onChange={(event) => setForm({ ...form, imap_host: event.target.value })} /><input placeholder="SMTP host" value={form.smtp_host} onChange={(event) => setForm({ ...form, smtp_host: event.target.value })} /></div><button className="primary-button">Save encrypted connection</button></form>}<section className="panel"><div className="panel-heading"><div><div className="section-kicker">CONNECTED MAILBOXES</div><h3>Sender accounts</h3></div><Mail size={19} className="muted" /></div>{connections.length ? connections.map((connection) => <div className="connection-row" key={connection.id}><span className="mail-icon"><Mail size={17} /></span><span><b>{connection.email_address}</b><small>{connection.smtp_host} / {connection.imap_host}</small></span><span className={`status ${connection.is_connected ? "ok" : "muted-status"}`}><i />{connection.is_connected ? "Connected" : "Not tested"}</span><button className="secondary-button compact" onClick={() => test(connection.id)}><RefreshCw size={15} /> Test</button></div>) : <div className="empty-state"><Mail size={22} /><p>No mailboxes connected.</p><small>Use a Gmail app password, never your primary password.</small></div>}</section></div>; }

function EmailConnections({ onNotice, config }) {
  const emptyForm = { email_address: "", imap_host: "imap.gmail.com", imap_port: 993, smtp_host: "smtp.gmail.com", smtp_port: 587, password: "" };
  const initialOptions = { query: "", sender: "", intent: "", since: "", until: "", unread_only: false, include_context: true, include_body: false, context_chars: 280, limit: 15 };
  const [connections, setConnections] = useState([]);
  const [googleMailboxes, setGoogleMailboxes] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [show, setShow] = useState(false);
  const [selected, setSelected] = useState({ source: "imap", id: null });
  const [options, setOptions] = useState(initialOptions);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [gmailBusy, setGmailBusy] = useState(false);

  const load = async () => {
    try {
      const [nextConnections, nextMailboxes] = await Promise.all([
        request("/email/connections"),
        request("/email/google/mailboxes"),
      ]);
      setConnections(nextConnections);
      setGoogleMailboxes(nextMailboxes);
      setSelected((current) => current.id ? current : { source: "imap", id: nextConnections[0]?.id || null });
    } catch (error) { onNotice({ type: "error", text: error.message }); }
  };

  useEffect(() => {
    load();
    const status = new URLSearchParams(window.location.search).get("gmail");
    if (status) {
      window.history.replaceState({}, "", window.location.pathname);
      onNotice({ type: status === "connected" ? "success" : "error", text: status === "connected" ? "Gmail connected." : "Gmail connection was not completed." });
      load();
    }
  }, []);

  const updateOption = (key, value) => setOptions((current) => ({ ...current, [key]: value }));
  const add = async (event) => {
    event.preventDefault();
    try {
      await request("/email/connections", { method: "POST", body: JSON.stringify(form) });
      setShow(false);
      setForm(emptyForm);
      onNotice({ type: "success", text: "Email connection saved encrypted." });
      load();
    } catch (error) { onNotice({ type: "error", text: error.message }); }
  };
  const test = async (id) => {
    try {
      const response = await request(`/email/connections/${id}/test`, { method: "POST" });
      onNotice({ type: response.is_connected ? "success" : "error", text: response.is_connected ? "IMAP and SMTP are connected." : "Connection test failed." });
      load();
    } catch (error) { onNotice({ type: "error", text: error.message }); }
  };
  const connectGmail = async () => {
    setGmailBusy(true);
    try {
      const response = await request("/email/google/authorize");
      window.open(response.authorization_url, "_blank", "noopener,noreferrer");
    } catch (error) { onNotice({ type: "error", text: error.message }); }
    finally { setGmailBusy(false); }
  };
  const runFetch = async () => {
    if (!selected.id) return onNotice({ type: "error", text: "Select a mailbox first." });
    setBusy(true);
    setResult(null);
    try {
      const path = selected.source === "gmail" ? `/email/google/mailboxes/${selected.id}/fetch` : `/email/connections/${selected.id}/fetch`;
      const response = await request(path, { method: "POST", body: JSON.stringify({ ...options, since: options.since || null, until: options.until || null }) });
      setResult(response);
    } catch (error) { onNotice({ type: "error", text: error.message }); }
    finally { setBusy(false); }
  };
  const selectedLabel = selected.source === "gmail" ? googleMailboxes.find((mailbox) => mailbox.id === selected.id)?.email_address : connections.find((connection) => connection.id === selected.id)?.email_address;

  return <div className="content">
    <div className="page-heading"><div><div className="section-kicker">OUTREACH INFRASTRUCTURE</div><h2>Email connections</h2><p className="muted">Test a mailbox, filter a small sample, and keep only the context you need.</p></div><button className="primary-button" onClick={() => setShow(!show)}><Plus size={17} /> Add IMAP mailbox</button></div>
    {show && <form className="panel form-panel" onSubmit={add}><div className="form-heading"><div><div className="section-kicker">IMAP / SMTP</div><h3>Add an encrypted mailbox</h3></div><button type="button" className="icon-button" onClick={() => setShow(false)} aria-label="Close"><X size={18} /></button></div><div className="form-grid"><input required type="email" placeholder="Mailbox email" value={form.email_address} onChange={(event) => setForm({ ...form, email_address: event.target.value })} /><input required type="password" placeholder="App password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} /><input placeholder="IMAP host" value={form.imap_host} onChange={(event) => setForm({ ...form, imap_host: event.target.value })} /><input type="number" placeholder="IMAP port" value={form.imap_port} onChange={(event) => setForm({ ...form, imap_port: Number(event.target.value) })} /><input placeholder="SMTP host" value={form.smtp_host} onChange={(event) => setForm({ ...form, smtp_host: event.target.value })} /><input type="number" placeholder="SMTP port" value={form.smtp_port} onChange={(event) => setForm({ ...form, smtp_port: Number(event.target.value) })} /></div><small className="muted">Use a Google app password for Gmail IMAP/SMTP. It is encrypted before storage.</small><button className="primary-button" type="submit">Save mailbox</button></form>}
    <section className="panel email-source-panel"><div className="panel-heading"><div><div className="section-kicker">MAILBOX SOURCES</div><h3>Choose a source to inspect</h3></div><span className="muted">Read-only test mode</span></div><div className="mailbox-source-list">{connections.map((connection) => <button key={`imap-${connection.id}`} className={`mailbox-source ${selected.source === "imap" && selected.id === connection.id ? "active" : ""}`} onClick={() => { setSelected({ source: "imap", id: connection.id }); setResult(null); }}><Mail size={16} /><span><b>{connection.email_address}</b><small>IMAP · {connection.is_connected ? "connected" : "not tested"}</small></span><ArrowUpRight size={15} /></button>)}{googleMailboxes.map((mailbox) => <button key={`gmail-${mailbox.id}`} className={`mailbox-source ${selected.source === "gmail" && selected.id === mailbox.id ? "active" : ""}`} onClick={() => { setSelected({ source: "gmail", id: mailbox.id }); setResult(null); }}><ShieldCheck size={16} /><span><b>{mailbox.email_address}</b><small>Gmail OAuth · {mailbox.is_connected ? "connected" : "reconnect"}</small></span><ArrowUpRight size={15} /></button>)}</div><div className="button-row"><button className="secondary-button" onClick={connectGmail} disabled={gmailBusy || !config.google_gmail_oauth_configured}><ShieldCheck size={16} /> {gmailBusy ? "Opening Google..." : "Connect Gmail with OAuth"}</button>{selected.source === "imap" && selected.id && <button className="secondary-button" onClick={() => test(selected.id)}><Activity size={16} /> Test IMAP / SMTP</button>}</div>{!config.google_gmail_oauth_configured && <small className="muted">Gmail OAuth is available after the server client secret and redirect URI are configured.</small>}</section>
    {selected.id && <EmailFetchInspector selectedLabel={selectedLabel} options={options} updateOption={updateOption} runFetch={runFetch} busy={busy} result={result} />}
  </div>;
}

function EmailFetchInspector({ selectedLabel, options, updateOption, runFetch, busy, result }) {
  return <section className="panel email-inspector"><div className="panel-heading"><div><div className="section-kicker">FILTERED MAIL TEST</div><h3>{selectedLabel || "Select a mailbox"}</h3><p className="muted">Returns at most 50 messages. Full bodies stay hidden unless explicitly enabled.</p></div><button className="primary-button" onClick={runFetch} disabled={busy}><Search size={16} /> {busy ? "Fetching..." : "Fetch context"}</button></div><div className="filter-grid"><label>Search text<input value={options.query} onChange={(event) => updateOption("query", event.target.value)} placeholder="e.g. quotation" /></label><label>Sender contains<input value={options.sender} onChange={(event) => updateOption("sender", event.target.value)} placeholder="name or company" /></label><label>Intent<select value={options.intent} onChange={(event) => updateOption("intent", event.target.value)}><option value="">Any intent</option><option value="procurement">Procurement</option><option value="sales">Sales</option><option value="hiring">Hiring</option><option value="partnership">Partnership</option><option value="support">Support</option><option value="general">General</option></select></label><label>From date<input type="date" value={options.since} onChange={(event) => updateOption("since", event.target.value)} /></label><label>To date<input type="date" value={options.until} onChange={(event) => updateOption("until", event.target.value)} /></label><label>Limit<input type="number" min="1" max="50" value={options.limit} onChange={(event) => updateOption("limit", Math.min(50, Math.max(1, Number(event.target.value))))} /></label></div><div className="switch-row"><label><input type="checkbox" checked={options.unread_only} onChange={(event) => updateOption("unread_only", event.target.checked)} /> Unread only</label><label><input type="checkbox" checked={options.include_context} onChange={(event) => updateOption("include_context", event.target.checked)} /> Show short context</label><label><input type="checkbox" checked={options.include_body} onChange={(event) => updateOption("include_body", event.target.checked)} /> Include full body</label><label>Context chars<input type="number" min="80" max="1000" value={options.context_chars} onChange={(event) => updateOption("context_chars", Math.min(1000, Math.max(80, Number(event.target.value))))} /></label></div>{result && <div className="fetch-result"><div className="result-summary"><b>{result.count} matched</b><span>{result.scanned} scanned · {result.source}</span></div>{result.messages.length ? result.messages.map((message) => <article className="message-card" key={message.uid}><div className="message-heading"><b>{message.subject || "(no subject)"}</b><span className="contact-tag">{message.intent}</span></div><small>{message.sender || "Unknown sender"} · {message.date || "No date"}</small>{message.context && <p>{message.context}</p>}{message.body && <details><summary>Full body requested</summary><pre>{message.body}</pre></details>}</article>) : <div className="empty-state"><Search size={20} /><p>No messages matched these filters.</p></div>}</div>}</section>;
}

function Signals({ onNotice }) { const [output, setOutput] = useState(null); const [busy, setBusy] = useState(false); const run = async (path, body, label) => { setBusy(true); try { setOutput({ label, data: await request(path, { method: "POST", body: JSON.stringify(body) }) }); } catch (error) { onNotice({ type: "error", text: error.message }); } finally { setBusy(false); } }; return <div className="content"><div className="page-heading"><div><div className="section-kicker">MARKET INTELLIGENCE</div><h2>Signal desk</h2><p className="muted">Queue the searches and background work that sharpen your next move.</p></div></div><div className="signal-actions"><button className="signal-action" onClick={() => run("/social/linkedin/search", { keywords: ["procurement", "scm", "hiring"] }, "LinkedIn hiring search")}><span><BriefcaseBusiness size={20} /></span><b>LinkedIn hiring search</b><small>Find hiring signals in procurement and SCM.</small><ArrowUpRight size={16} /></button><button className="signal-action" onClick={() => run("/social/reddit/search", {}, "Reddit hiring search")}><span><Search size={20} /></span><b>Reddit hiring search</b><small>Scan communities for useful conversations.</small><ArrowUpRight size={16} /></button><button className="signal-action" onClick={() => run("/social/youtube/search", { queries: ["hiring procurement", "supply chain"], max_results: 10 }, "YouTube signal scan")}><span><Video size={20} /></span><b>YouTube signal scan</b><small>Google-secured Data API v3 company/tech signals.</small><ArrowUpRight size={16} /></button><button className="signal-action" onClick={() => run("/scheduler/run", {}, "Cron sweep")}><span><RefreshCw size={20} /></span><b>Run cron sweep</b><small>Queue the scheduled pipeline tasks.</small><ArrowUpRight size={16} /></button></div>{busy && <div className="panel loading-inline"><RefreshCw size={18} className="spin" /> Working through the signal stream...</div>}{output && <section className="panel output-panel"><div className="panel-heading"><h3>{output.label}</h3><button className="icon-button" onClick={() => setOutput(null)} aria-label="Close"><X size={17} /></button></div><pre>{JSON.stringify(output.data, null, 2)}</pre></section>}</div>; }

function Scheduler({ onNotice }) {
  const [status, setStatus] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [busy, setBusy] = useState(false);
  const load = async () => {
    try {
      const [nextStatus, nextTasks] = await Promise.all([request("/scheduler/status"), request("/scheduler/tasks")]);
      setStatus(nextStatus);
      setTasks(nextTasks.tasks || []);
    } catch (error) { onNotice({ type: "error", text: error.message }); }
  };
  useEffect(() => { load(); }, []);
  const runNow = async () => {
    setBusy(true);
    try {
      const result = await request("/scheduler/run", { method: "POST", body: JSON.stringify({ notify_email: true }) });
      const mailStatus = result.notification?.status === "sent"
        ? ` Email sent to ${result.notification.to}.`
        : result.notification?.status === "not_configured"
          ? " Add an SMTP connection to receive the run details by email."
          : "";
      onNotice({ type: "success", text: `Enqueued ${result.enqueued} tasks (${result.backend}).${mailStatus}` });
      load();
    } catch (error) { onNotice({ type: "error", text: error.message }); }
    finally { setBusy(false); }
  };
  const clearQueue = async () => {
    if (!window.confirm("Clear this workspace's queued tasks?")) return;
    setBusy(true);
    try {
      const result = await request("/scheduler/clear", { method: "POST", body: "{}" });
      onNotice({ type: "success", text: `Cleared ${result.cleared} queued tasks.` });
      load();
    } catch (error) { onNotice({ type: "error", text: error.message }); }
    finally { setBusy(false); }
  };
  return (
    <div className="content">
      <div className="page-heading">
        <div><div className="section-kicker">AUTOMATION</div><h2>Scheduler</h2><p className="muted">Customized cron queue, scoped to your workspace. Cloud Scheduler triggers the same endpoint in production.</p></div>
        <div className="button-row">
          <button className="secondary-button" onClick={clearQueue} disabled={busy}><Trash2 size={16} /> Clear queue</button>
          <button className="primary-button" onClick={runNow} disabled={busy}><Clock size={16} /> {busy ? "Queueing..." : "Run now"}</button>
        </div>
      </div>
      <div className="two-column">
        <section className="panel">
          <div className="panel-heading"><div><div className="section-kicker">REGISTERED</div><h3>Recurring tasks</h3></div><button className="icon-button" onClick={load} aria-label="Refresh scheduler"><RefreshCw size={17} /></button></div>
          <div className="contact-list" role="list">
            {tasks.map((task) => (
              <div className="contact-row" key={task.name} role="listitem">
                <span className="contact-main"><b>{task.name}</b><small>{task.description}</small></span>
                <span className="contact-tag" title="Cron expression">{task.cron}</span>
              </div>
            ))}
            {!tasks.length && <div className="empty-state"><Clock size={22} /><p>No tasks registered.</p></div>}
          </div>
        </section>
        <section className="panel signal-panel">
          <div className="panel-heading"><div><div className="section-kicker">QUEUE</div><h3>Status</h3></div></div>
          <Service status={status?.scheduler === "running"} icon={Clock} label="Scheduler" value={status?.scheduler || "--"} />
          <Service status={status?.backend === "redis"} icon={Database} label="Queue backend" value={status?.backend || "--"} />
          <Service status icon={RefreshCw} label="Queued (you)" value={String(status?.queued_count ?? 0)} />
          <Service status icon={BriefcaseBusiness} label="Registered tasks" value={String(status?.registered_tasks ?? 0)} />
          {!!status?.queued_tasks?.length && <pre style={{ marginTop: 10, maxHeight: 220, overflow: "auto" }}>{JSON.stringify(status.queued_tasks, null, 2)}</pre>}
        </section>
      </div>
    </div>
  );
}

function Kpis({ onNotice }) {
  const [overview, setOverview] = useState(null);
  const [pipeline, setPipeline] = useState(null);
  const [outreach, setOutreach] = useState(null);
  const [costs, setCosts] = useState(null);
  const [web, setWeb] = useState(null);
  const load = async () => {
    try {
      const [o, p, out, c, w] = await Promise.all([request("/kpi/overview"), request("/kpi/pipeline"), request("/kpi/outreach"), request("/kpi/costs"), request("/kpi/website")]);
      setOverview(o); setPipeline(p); setOutreach(out); setCosts(c); setWeb(w);
    } catch (error) { onNotice({ type: "error", text: error.message }); }
  };
  useEffect(() => { load(); }, []);
  const rate = outreach?.delivery_rate == null ? "--" : `${Math.round(outreach.delivery_rate * 100)}%`;
  return (
    <div className="content">
      <div className="page-heading">
        <div><div className="section-kicker">BUSINESS KPI MONITORING</div><h2>Business KPIs</h2><p className="muted">Workspace-level funnel, outreach performance, and AI cost control.</p></div>
        <button className="icon-button" onClick={load} aria-label="Refresh KPIs"><RefreshCw size={17} /></button>
      </div>
      <div className="metric-grid">
        <Metric label="Total contacts" value={overview?.contacts_total ?? "--"} detail={`+${pipeline?.new_last_7_days ?? 0} last 7 days`} icon={Users} />
        <Metric label="Signals captured" value={overview ? overview.signals.linkedin + overview.signals.reddit : "--"} detail={`LinkedIn ${overview?.signals?.linkedin ?? 0} · Reddit ${overview?.signals?.reddit ?? 0}`} icon={Sparkles} accent />
        <Metric label="Messages sent" value={overview?.messages_sent ?? "--"} detail={`delivery ${rate}`} icon={Send} />
        <Metric label="AI spend" value={costs ? `$${costs.total_cost_usd}` : "--"} detail="all-time, micro-USD ledger" icon={BarChart3} />
      </div>
      <div className="two-column">
        <section className="panel">
          <div className="panel-heading"><div><div className="section-kicker">PIPELINE FUNNEL</div><h3>Contacts by intent</h3></div></div>
          <div className="contact-list" role="list">
            {Object.entries(pipeline?.by_intent || {}).map(([intent, count]) => (
              <div className="contact-row" key={intent} role="listitem"><span className="contact-main"><b>{intent}</b></span><span className="contact-tag">{count}</span></div>
            ))}
            {!Object.keys(pipeline?.by_intent || {}).length && <div className="empty-state"><Users size={22} /><p>No contacts yet.</p></div>}
          </div>
        </section>
        <section className="panel">
          <div className="panel-heading"><div><div className="section-kicker">OUTREACH & COST</div><h3>Campaign funnel</h3></div></div>
          <div className="contact-list" role="list">
            {Object.entries(outreach?.campaigns_by_status || {}).map(([status, count]) => (
              <div className="contact-row" key={status} role="listitem"><span className="contact-main"><b>{status}</b></span><span className="contact-tag">{count}</span></div>
            ))}
            {!Object.keys(outreach?.campaigns_by_status || {}).length && <div className="empty-state"><Send size={22} /><p>No campaigns yet.</p></div>}
          </div>
          {!!Object.keys(costs?.by_task || {}).length && (
            <pre style={{ marginTop: 10, maxHeight: 180, overflow: "auto" }}>{JSON.stringify(costs.by_task, null, 2)}</pre>
          )}
        </section>
      </div>
      <section className="panel" style={{ marginTop: 16 }} aria-label="Website traffic">
        <div className="panel-heading">
          <div><div className="section-kicker">WEBSITE TRAFFIC · GA4</div><h3>kalisoftai.com at a glance</h3></div>
          <span className="muted">{web?.available ? `${web.period.start} → ${web.period.end}` : "snapshot unavailable"}</span>
        </div>
        {!web?.available && <div className="empty-state"><BarChart3 size={22} /><p>No GA4 snapshot found.</p><small>Drop a Reports snapshot CSV in the GCS bucket to light this panel up.</small></div>}
        {web?.available && (
          <>
            <div className="metric-grid" style={{ marginBottom: 14 }}>
              <Metric label="Active users" value={web.totals.active_users} detail={`${web.totals.new_users} new`} icon={Users} accent />
              <Metric label="Engagement" value={`${web.totals.avg_engagement_seconds}s`} detail="avg per active user" icon={Activity} />
              <Metric label="Event count" value={web.totals.event_count} detail="all interactions" icon={Sparkles} />
              <Metric label="Top city" value={web.cities[0]?.city || "—"} detail={`${web.cities[0]?.active_users ?? 0} active users`} icon={Search} />
            </div>
            <div className="two-column">
              <div className="contact-list" role="list" aria-label="Top pages">
                <div className="section-kicker" style={{ padding: "4px 2px" }}>TOP PAGES</div>
                {web.pages.slice(0, 5).map((p) => (
                  <div className="contact-row" key={p.title} role="listitem">
                    <span className="contact-main"><b>{p.title}</b><small>{p.active_users} users · bounce {Math.round(p.bounce_rate * 100)}%</small></span>
                    <span className="contact-tag">{p.views} views</span>
                  </div>
                ))}
              </div>
              <div className="contact-list" role="list" aria-label="Traffic sources">
                <div className="section-kicker" style={{ padding: "4px 2px" }}>TRAFFIC SOURCES</div>
                {web.sources.slice(0, 5).map((s) => (
                  <div className="contact-row" key={s.source} role="listitem">
                    <span className="contact-main"><b>{s.source}</b></span>
                    <span className="contact-tag">{s.active_users} users</span>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </section>
    </div>
  );
}

function Outreach({ onNotice }) {
  const [templates, setTemplates] = useState([]);
  const [campaigns, setCampaigns] = useState([]);
  const [meta, setMeta] = useState({ channels: [], strategies: [], funnel_stages: [] });
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ name: "Outreach campaign", channel: "email", strategy: "cold_outreach", limit: 10, intent: "" });

  const load = async () => {
    try {
      const [tpls, camps, m] = await Promise.all([request("/templates"), request("/campaigns"), request("/templates/meta")]);
      setTemplates(tpls); setCampaigns(camps); setMeta(m);
    } catch (error) { onNotice({ type: "error", text: error.message }); }
  };
  useEffect(() => { load(); }, []);
  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));

  const seed = async () => { setBusy(true); try { const result = await request("/templates/seed", { method: "POST" }); onNotice({ type: "success", text: `Seeded ${result.created} templates.` }); load(); } catch (error) { onNotice({ type: "error", text: error.message }); } finally { setBusy(false); } };
  const pickTemplate = (template) => { setSelected(template); setForm((current) => ({ ...current, channel: template.channel, strategy: template.strategy })); };
  const createCampaign = async () => {
    if (!selected) return onNotice({ type: "error", text: "Select a template first." });
    setBusy(true);
    try {
      const body = { name: form.name, channel: form.channel, strategy: form.strategy, template_id: selected.id, use_ai: true, filter: { limit: Number(form.limit) || 10, intent: form.intent } };
      const campaign = await request("/campaigns", { method: "POST", body: JSON.stringify(body) });
      setDetail(campaign); onNotice({ type: "success", text: `Generated ${campaign.total} messages for review.` }); load();
    } catch (error) { onNotice({ type: "error", text: error.message }); } finally { setBusy(false); }
  };
  const openCampaign = async (id) => { try { setDetail(await request(`/campaigns/${id}`)); } catch (error) { onNotice({ type: "error", text: error.message }); } };
  const approve = async () => { if (!detail) return; setBusy(true); try { setDetail(await request(`/campaigns/${detail.id}/approve`, { method: "POST" })); onNotice({ type: "success", text: "Approved — ready to send." }); } catch (error) { onNotice({ type: "error", text: error.message }); } finally { setBusy(false); } };
  const send = async () => { if (!detail) return; setBusy(true); try { const result = await request(`/campaigns/${detail.id}/send`, { method: "POST" }); onNotice({ type: "success", text: `Sent ${result.sent}, failed ${result.failed}, queued ${result.skipped}.` }); setDetail(await request(`/campaigns/${detail.id}`)); load(); } catch (error) { onNotice({ type: "error", text: error.message }); } finally { setBusy(false); } };

  return (
    <div className="content">
      <div className="page-heading">
        <div>
          <div className="section-kicker">TEMPLATES & BULK OUTREACH</div>
          <h2>Outreach</h2>
          <p className="muted">Pick a sales strategy, personalise with Gemma, review, then send by email, WhatsApp or WeChat.</p>
        </div>
        <button className="secondary-button" onClick={seed} disabled={busy}><Sparkles size={16} /> Seed templates</button>
      </div>

      <section className="panel" aria-label="Templates">
        <div className="panel-heading"><h3>Templates ({templates.length})</h3><span className="muted">Channel &amp; funnel strategy</span></div>
        <div className="contact-list" role="list">
          {templates.map((template) => (
            <button key={template.id} role="listitem" className={`contact-row ${selected?.id === template.id ? "selected" : ""}`} style={{ width: "100%", textAlign: "left", border: 0, background: selected?.id === template.id ? "#eef6ef" : "transparent" }} onClick={() => pickTemplate(template)} aria-pressed={selected?.id === template.id}>
              <span className="contact-main"><b>{template.name}</b><small>{template.subject || template.body.slice(0, 70)}</small></span>
              <span className="contact-tag">{template.channel}</span>
              <span className="contact-tag">{template.strategy}</span>
            </button>
          ))}
          {!templates.length && <div className="empty-state"><Sparkles size={22} /><p>No templates yet.</p><small>Click "Seed templates" to load Kalisoft defaults.</small></div>}
        </div>
      </section>

      <section className="panel" style={{ marginTop: 16 }} aria-label="Build campaign">
        <div className="panel-heading"><h3>Build a campaign</h3><span className="muted">{selected ? `Using: ${selected.name}` : "Select a template above"}</span></div>
        <div className="form-grid">
          <label>Campaign name<input value={form.name} onChange={(event) => update("name", event.target.value)} /></label>
          <label>Channel
            <select value={form.channel} onChange={(event) => update("channel", event.target.value)}>
              {(meta.channels.length ? meta.channels : ["email", "whatsapp", "linkedin", "wechat"]).map((option) => <option key={option}>{option}</option>)}
            </select>
          </label>
          <label>Strategy
            <select value={form.strategy} onChange={(event) => update("strategy", event.target.value)}>
              {(meta.strategies.length ? meta.strategies : ["cold_outreach", "follow_up", "nurture"]).map((option) => <option key={option}>{option}</option>)}
            </select>
          </label>
          <label>Intent filter<input placeholder="e.g. procurement" value={form.intent} onChange={(event) => update("intent", event.target.value)} /></label>
          <label>How many contacts<input type="number" min="1" max="500" value={form.limit} onChange={(event) => update("limit", event.target.value)} /></label>
          <button className="primary-button" onClick={createCampaign} disabled={busy || !selected}>{busy ? "Working..." : "Generate for review"}</button>
        </div>
        <small className="muted">Messages are generated for human review first. Nothing sends until you approve.</small>
      </section>

      {detail && (
        <section className="panel" style={{ marginTop: 16 }} aria-label="Review and send">
          <div className="panel-heading">
            <h3>Review — {detail.name} (#{detail.id})</h3>
            <span className="contact-tag">{detail.status}</span>
          </div>
          <div className="button-row" style={{ marginBottom: 10 }}>
            <button className="secondary-button" onClick={approve} disabled={busy}>Approve all</button>
            <button className="primary-button" onClick={send} disabled={busy}><Send size={16} /> Send approved</button>
          </div>
          <div className="contact-list" role="list">
            {detail.messages.map((message) => (
              <div className="contact-row" key={message.id} role="listitem">
                <span className="contact-main">
                  <b>{message.to_address || "(no address)"}</b>
                  <small>{message.rendered_subject || "(no subject)"}</small>
                  <small>{message.rendered_body.slice(0, 160)}</small>
                </span>
                <span className="contact-tag">{message.status}</span>
                {message.error && <span className="contact-tag" title={message.error}>error</span>}
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="panel" style={{ marginTop: 16 }} aria-label="Campaign history">
        <div className="panel-heading"><h3>Campaign history ({campaigns.length})</h3><button className="icon-button" onClick={load} aria-label="Refresh campaigns"><RefreshCw size={16} /></button></div>
        <div className="contact-list" role="list">
          {campaigns.map((campaign) => (
            <button key={campaign.id} role="listitem" className="contact-row" style={{ width: "100%", textAlign: "left", border: 0, background: "transparent" }} onClick={() => openCampaign(campaign.id)}>
              <span className="contact-main"><b>{campaign.name}</b><small>{campaign.channel} · {campaign.strategy} · {campaign.total} messages</small></span>
              <span className="contact-tag">{campaign.status}</span>
              <span className="contact-tag">sent {campaign.sent_count}/{campaign.failed_count} failed</span>
            </button>
          ))}
          {!campaigns.length && <div className="empty-state"><Send size={22} /><p>No campaigns yet.</p><small>Build your first campaign above.</small></div>}
        </div>
      </section>
    </div>
  );
}

function Feedback({ onNotice }) {
  const [form, setForm] = useState({ category: "general", rating: 5, message: "" });
  const [items, setItems] = useState([]);
  const [busy, setBusy] = useState(false);
  const load = async () => { try { setItems(await request("/feedback")); } catch (error) { onNotice({ type: "error", text: error.message }); } };
  useEffect(() => { load(); }, []);
  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      const saved = await request("/feedback", { method: "POST", body: JSON.stringify({ ...form, page: "feedback" }) });
      onNotice({ type: "success", text: saved.notified ? "Thanks! Feedback sent and our team was notified by mail." : "Thanks! Feedback saved (mail notification not configured here)." });
      setForm({ category: "general", rating: 5, message: "" });
      load();
    } catch (error) { onNotice({ type: "error", text: error.message }); }
    finally { setBusy(false); }
  };
  return (
    <div className="content">
      <div className="page-heading">
        <div><div className="section-kicker">WE LISTEN</div><h2>Feedback</h2><p className="muted">Tell us what to improve — every submission notifies the team by mail.</p></div>
      </div>
      <div className="two-column">
        <form className="panel form-panel" onSubmit={submit}>
          <div className="form-heading"><div><div className="section-kicker">NEW</div><h3>Share feedback</h3></div></div>
          <div className="form-grid">
            <label>Category
              <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                <option value="general">General</option><option value="bug">Bug report</option><option value="feature">Feature request</option><option value="ux">Experience</option>
              </select>
            </label>
            <label>Rating
              <span style={{ display: "flex", gap: 6, padding: "8px 0" }}>
                {[1, 2, 3, 4, 5].map((n) => (
                  <button type="button" key={n} onClick={() => setForm({ ...form, rating: n })} aria-label={`Rate ${n}`} style={{ background: "none", border: 0, cursor: "pointer", color: n <= form.rating ? "#e6a817" : "#c8cdd6" }}><Star size={20} fill={n <= form.rating ? "#e6a817" : "none"} /></button>
                ))}
              </span>
            </label>
            <label style={{ gridColumn: "1 / -1" }}>Message
              <textarea required rows={4} value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} placeholder="What's working? What's missing?" style={{ width: "100%", resize: "vertical" }} />
            </label>
          </div>
          <button className="primary-button" disabled={busy}><Send size={16} /> {busy ? "Sending..." : "Send feedback"}</button>
        </form>
        <section className="panel">
          <div className="panel-heading"><div><div className="section-kicker">HISTORY</div><h3>Your feedback ({items.length})</h3></div><button className="icon-button" onClick={load} aria-label="Refresh feedback"><RefreshCw size={17} /></button></div>
          <div className="contact-list" role="list">
            {items.map((item) => (
              <div className="contact-row" key={item.id} role="listitem">
                <span className="contact-main"><b>{item.category} · {item.rating}/5</b><small>{item.message.slice(0, 90)}</small></span>
                <span className="contact-tag">{item.notified ? "mailed" : "saved"}</span>
                <span className="contact-tag">{item.status}</span>
              </div>
            ))}
            {!items.length && <div className="empty-state"><MessageSquarePlus size={22} /><p>No feedback yet.</p><small>Your suggestions shape the roadmap.</small></div>}
          </div>
        </section>
      </div>
    </div>
  );
}

const TOUR_KEY = "kalisoft_tour_done";
const TOUR_STEPS = [
  { icon: UploadCloud, title: "1. Import your contacts", text: "Bring CSV / Excel / VCF files or sync the GCS bucket (kalisoftai-datahub). Real exports with blank first rows are handled automatically — sector, turnover and exporter fields land as tags." },
  { icon: Sparkles, title: "2. Auto-classification", text: "Every contact is segregated by domain, intent (hiring / procurement / sales) and context the moment it enters your workspace." },
  { icon: Search, title: "3. Catch live signals", text: "LinkedIn, Reddit and YouTube scans surface hiring and procurement cues — secured by your Google account (ADC)." },
  { icon: Send, title: "4. Review, approve, send", text: "Gemma-personalised campaigns stay human-in-the-loop: nothing sends until you approve. Email, WhatsApp, LinkedIn or WeChat." },
  { icon: BarChart3, title: "5. Watch the KPIs", text: "Funnel, delivery rate and AI spend update in real time on the KPIs tab. Nightly snapshots keep the history." },
];

function Walkthrough({ onClose }) {
  const [step, setStep] = useState(0);
  const current = TOUR_STEPS[step];
  const last = step === TOUR_STEPS.length - 1;
  const finish = () => { sessionStorage.setItem(TOUR_KEY, "1"); onClose(); };
  return (
    <div className="scrim" style={{ display: "grid", placeItems: "center", zIndex: 50 }} role="dialog" aria-modal="true" aria-label="Product walkthrough">
      <div className="panel" style={{ maxWidth: 440, padding: 24, background: "var(--panel, #fff)" }}>
        <div className="panel-heading">
          <div><div className="section-kicker">WELCOME TOUR</div><h3>How Kalisoft AI works</h3></div>
          <button className="icon-button" onClick={finish} aria-label="Skip tour"><X size={17} /></button>
        </div>
        <div style={{ textAlign: "center", padding: "8px 0 4px" }}>
          <div className="metric-icon" style={{ margin: "0 auto 10px" }}><current.icon size={22} /></div>
          <h3 style={{ margin: "0 0 6px" }}>{current.title}</h3>
          <p className="muted" style={{ minHeight: 66 }}>{current.text}</p>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 8 }}>
          <span style={{ display: "flex", gap: 5 }}>
            {TOUR_STEPS.map((s, i) => <span key={s.title} style={{ width: 8, height: 8, borderRadius: 99, background: i <= step ? "#1d4fa3" : "#d5dae3" }} />)}
          </span>
          <span style={{ display: "flex", gap: 8 }}>
            {step > 0 && <button className="secondary-button" onClick={() => setStep(step - 1)}>Back</button>}
            <button className="primary-button" onClick={() => (last ? finish() : setStep(step + 1))}>{last ? "Start working" : "Next"}</button>
          </span>
        </div>
      </div>
    </div>
  );
}

function SecurityTrust() {
  const [data, setData] = useState(null);
  useEffect(() => { request("/security/status").then(setData).catch(() => setData(null)); }, []);
  if (!data) return null;
  return (
    <section className="panel" style={{ marginTop: 16 }} aria-label="Data security">
      <div className="panel-heading"><div><div className="section-kicker">DATA SECURITY</div><h3>Your data, guarded</h3></div><ShieldCheck size={18} /></div>
      <div className="contact-list" role="list">
        {data.guardrails.map((g) => (
          <div className="contact-row" key={g.key} role="listitem">
            <span className="service-icon" style={{ color: g.on ? "#187a2f" : "#8a5a00" }}>{g.on ? <ShieldCheck size={16} /> : <CircleAlert size={16} />}</span>
            <span className="contact-main"><b>{g.label}</b></span>
            <span className={`status ${g.on ? "ok" : "muted-status"}`}><i />{g.on ? "On" : "Off"}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

const FUTURE_SCOPE = [
  { icon: Sparkles, title: "Gemma 4 personalisation", text: "Every outreach message written by gemma-4-27b-it, tuned to each contact's intent and history." },
  { icon: Database, title: "Knowledge catalog + graph DB", text: "Contacts, companies, signals and outcomes connected as a queryable entity graph." },
  { icon: Video, title: "YouTube signal scan", text: "Google-secured Data API v3 watches for company and tech signals in your market." },
  { icon: Bell, title: "Smart mail notifications", text: "Hot leads and KPI changes pushed to your inbox the moment they happen." },
  { icon: BarChart3, title: "BigQuery KPI warehouse", text: "Nightly analytics snapshots power trend lines and forecasts on your dashboard." },
  { icon: ShieldCheck, title: "Multi-tenant RLS", text: "PostgreSQL row-level security for enterprise workspaces and audit export." },
  { icon: BriefcaseBusiness, title: "Account catalog + billing", text: "Gemma 4-assisted service matching, quote drafts, and invoice templates from the project matrices." },
];

function FutureScope() {
  return (
    <section className="pricing" aria-label="What's next">
      <div className="pricing-head">
        <div className="section-kicker">NEXT SCOPE</div>
        <h2>Where Kalisoft AI is heading</h2>
        <p className="muted">A preview of what's already in build — secured by your Google account (ADC), guarded end to end.</p>
      </div>
      <div className="plan-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))" }}>
        {FUTURE_SCOPE.map((f) => (
          <article key={f.title} className="plan-card">
            <div className="metric-icon" style={{ marginBottom: 8 }}><f.icon size={18} /></div>
            <h3>{f.title}</h3>
            <p className="muted">{f.text}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

const PLANS = [
  { name: "Free", price: 0, period: "forever", tagline: "Start with 2 AI users", features: ["2 AI users", "250 contacts", "50 AI credits / month", "Email + WhatsApp templates", "CSV / Excel / GCS import"], cta: "Create free account" },
  { name: "Starter", price: 499, period: "/ month", tagline: "Small tier-2 teams", features: ["5 users", "5,000 contacts", "1,000 AI credits / month", "Automated follow-ups", "1 WhatsApp number"], cta: "Choose Starter" },
  { name: "Growth", price: 1499, period: "/ month", tagline: "Most popular", popular: true, features: ["15 users", "50,000 contacts", "10,000 AI credits / month", "Sales funnels + A/B templates", "3 WhatsApp numbers", "Priority support"], cta: "Choose Growth" },
  { name: "Scale", price: 3999, period: "/ month", tagline: "High volume", features: ["Unlimited users", "Unlimited contacts", "50,000 AI credits / month", "SSO + audit export", "10 WhatsApp numbers"], cta: "Choose Scale" },
];

const WHATSAPP_RATES = [
  { category: "Marketing", rate: 0.8631, note: "Promotions, offers, re-engagement" },
  { category: "Utility", rate: 0.115, note: "Order / delivery / payment updates" },
  { category: "Authentication", rate: 0.115, note: "OTP / login verification (domestic)" },
  { category: "Authentication (international)", rate: 2.3, note: "OTP to non-India numbers" },
  { category: "Service", rate: 0, note: "Replies inside the 24h window — free" },
];

const PLATFORM_FEE_PER_MESSAGE = 0.05;
const inr = (value) => "₹" + Number(value).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function SignInPage({ config, onLogin, onNotice }) {
  return (
    <div className="signin-shell">
      <Login config={config} onLogin={onLogin} onNotice={onNotice} />
      <PricingSection />
      <FutureScope />
    </div>
  );
}

function PricingSection() {
  const [annual, setAnnual] = useState(false);
  const displayPrice = (plan) => (plan.price === 0 ? "₹0" : inr(annual ? plan.price * 10 : plan.price).replace(".00", ""));
  const displayPeriod = (plan) => (plan.price === 0 ? plan.period : annual ? "/ year" : plan.period);
  return (
    <section className="pricing" aria-label="Plans and pricing">
      <div className="pricing-head">
        <div className="section-kicker">PLANS &amp; PRICING</div>
        <h2>Built for tier-2 Indian businesses</h2>
        <p className="muted">Nashik · Ahmedabad · Indore · Coimbatore · Nagpur · Ahmednagar. Prices in INR, exclusive of 18% GST. Annual billing gives 2 months free.</p>
        <div className="billing-toggle" role="group" aria-label="Billing period">
          <button className={!annual ? "active" : ""} onClick={() => setAnnual(false)}>Monthly</button>
          <button className={annual ? "active" : ""} onClick={() => setAnnual(true)}>Annual (2 months free)</button>
        </div>
      </div>
      <div className="plan-grid">
        {PLANS.map((plan) => (
          <article key={plan.name} className={`plan-card ${plan.popular ? "popular" : ""}`}>
            {plan.popular && <span className="plan-badge">Most popular</span>}
            <h3>{plan.name}</h3>
            <p className="muted">{plan.tagline}</p>
            <div className="plan-price"><b>{displayPrice(plan)}</b><span>{displayPeriod(plan)}</span></div>
            <ul>{plan.features.map((feature) => <li key={feature}><Check size={14} />{feature}</li>)}</ul>
            <button className={plan.popular ? "primary-button" : "secondary-button"}>{plan.cta}</button>
          </article>
        ))}
      </div>
      <p className="muted plan-note">WhatsApp usage is billed at Meta's published rate (pass-through) plus a {inr(PLATFORM_FEE_PER_MESSAGE)} / message platform fee. Email is included. AI credits cover Gemma-powered personalisation.</p>
      <WhatsAppCosts />
    </section>
  );
}

function WhatsAppCosts() {
  const [volume, setVolume] = useState(1000);
  const marketingRate = WHATSAPP_RATES[0].rate;
  const meta = marketingRate * volume;
  const gst = meta * 0.18;
  const fee = PLATFORM_FEE_PER_MESSAGE * volume;
  const total = meta + gst + fee;
  return (
    <section className="wa-costs" aria-label="WhatsApp cost transparency">
      <div className="section-kicker">FUTURE SCOPE · COST TRANSPARENCY</div>
      <h3>What one WhatsApp message really costs</h3>
      <p className="muted">
        Meta charges <b>per delivered template message</b> (not per conversation) and the price is set by the
        recipient's country. Official India INR rate card, effective 1 January 2026. Source:{" "}
        <a href="https://developers.facebook.com/docs/whatsapp/pricing" target="_blank" rel="noreferrer">developers.facebook.com/docs/whatsapp/pricing</a>.
      </p>
      <table className="wa-table">
        <caption>Meta India per-message rates (INR), exclusive of 18% GST</caption>
        <thead><tr><th>Category</th><th>Meta rate / message</th><th>When it applies</th></tr></thead>
        <tbody>
          {WHATSAPP_RATES.map((row) => (
            <tr key={row.category}>
              <td>{row.category}</td>
              <td>{row.rate === 0 ? "Free" : "₹" + row.rate.toFixed(4)}</td>
              <td>{row.note}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="wa-calc">
        <label htmlFor="wa-volume">Marketing messages / month
          <input id="wa-volume" type="number" min="1" max="1000000" value={volume} onChange={(event) => setVolume(Math.max(1, Number(event.target.value) || 1))} />
        </label>
        <ul>
          <li><span>Meta marketing charge ({volume.toLocaleString("en-IN")} × ₹{marketingRate.toFixed(4)})</span><b>{inr(meta)}</b></li>
          <li><span>18% GST</span><b>{inr(gst)}</b></li>
          <li><span>Kalisoft platform fee ({inr(PLATFORM_FEE_PER_MESSAGE)}/message)</span><b>{inr(fee)}</b></li>
          <li className="wa-total"><span>Total you pay</span><b>{inr(total)}</b></li>
          <li className="wa-per"><span>All-in per message</span><b>{inr(total / volume)}</b></li>
        </ul>
      </div>
      <table className="wa-table">
        <caption>Channel cost per message (transparency)</caption>
        <thead><tr><th>Channel</th><th>Per message</th><th>Notes</th></tr></thead>
        <tbody>
          <tr><td>WhatsApp — marketing</td><td>₹0.8631 + GST</td><td>Meta pass-through</td></tr>
          <tr><td>WhatsApp — utility / auth</td><td>₹0.1150 + GST</td><td>Utility free inside the 24h window</td></tr>
          <tr><td>Email (SMTP)</td><td>Included</td><td>Your mailbox, no per-message fee</td></tr>
          <tr><td>WeChat / WhatsApp (Wechaty)</td><td>Infra only</td><td>Self-hosted gateway</td></tr>
          <tr><td>LinkedIn</td><td>Manual</td><td>Queued for human action</td></tr>
        </tbody>
      </table>
      <p className="muted">Rates are Meta's published India rate card and may change quarterly; verify before budgeting. Volume tiers discount utility / authentication by up to 30% at scale.</p>
    </section>
  );
}

function FeedbackPipeline({ onNotice }) {
  const [segments, setSegments] = useState([]);
  const [segment, setSegment] = useState("");
  const [templates, setTemplates] = useState([]);
  const [templateId, setTemplateId] = useState("");
  const [limit, setLimit] = useState(25);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);

  const loadSegments = async () => {
    try {
      const rows = await request("/pipeline/segments");
      setSegments(rows);
      setSegment((current) => current || rows[0]?.id || "");
    } catch (error) { onNotice({ type: "error", text: error.message }); }
  };
  useEffect(() => { loadSegments(); }, []);

  useEffect(() => {
    if (!segment) return;
    setPreview(null);
    request(`/pipeline/templates?segment=${encodeURIComponent(segment)}`)
      .then((rows) => { setTemplates(rows); setTemplateId(rows[0]?.id || ""); })
      .catch((error) => onNotice({ type: "error", text: error.message }));
  }, [segment]);

  const runPreview = async () => {
    if (!segment || !templateId) return;
    setBusy(true);
    try {
      const result = await request("/pipeline/preview", { method: "POST", body: JSON.stringify({ segment, template_id: templateId, limit }) });
      setPreview(result);
      if (!result.count) onNotice({ type: "error", text: "No audience rows for this segment yet." });
    } catch (error) { onNotice({ type: "error", text: error.message }); }
    finally { setBusy(false); }
  };

  const queueAll = async () => {
    if (!segment || !templateId) return;
    if (!window.confirm("Queue personalised WhatsApp messages for every audience row that has a phone number?")) return;
    setBusy(true);
    try {
      const result = await request("/pipeline/queue", { method: "POST", body: JSON.stringify({ segment, template_id: templateId, limit }) });
      onNotice({ type: "success", text: `Queued ${result.queued} message(s); skipped ${result.skipped_no_phone} without phone.` });
    } catch (error) { onNotice({ type: "error", text: error.message }); }
    finally { setBusy(false); }
  };

  const selectedTemplate = templates.find((t) => t.id === templateId);
  const activeSegment = segments.find((s) => s.id === segment);

  return (
    <div className="content">
      <div className="page-heading">
        <div>
          <div className="section-kicker">TRIGGERING PIPELINE</div>
          <h2>Customer feedback messages</h2>
          <p className="muted">Pick a segment, choose a template, preview the personalised messages, then send each one through WhatsApp (wa.me opens with the message ready — you tap Send). QR-based sharing comes in the next scope.</p>
        </div>
        <button className="icon-button" onClick={loadSegments} aria-label="Refresh segments"><RefreshCw size={17} /></button>
      </div>

      <div className="metric-grid">
        {segments.map((s) => (
          <button key={s.id} className={`metric segment-card ${segment === s.id ? "accent selected" : ""}`} onClick={() => setSegment(s.id)}>
            <div className="metric-icon"><Zap size={18} /></div>
            <div className="metric-label">{s.label}</div>
            <div className="metric-value">{s.with_phone}<small className="metric-sub"> / {s.audience}</small></div>
            <div className="metric-detail">{s.description}</div>
            <small className="muted">reachable with phone · {s.source}</small>
          </button>
        ))}
      </div>

      <section className="panel form-panel" style={{ marginBottom: 16 }}>
        <div className="form-heading">
          <div><div className="section-kicker">STEP 1 · TEMPLATE</div><h3>Choose message template</h3></div>
          {selectedTemplate && <span className="contact-tag">{selectedTemplate.intent}</span>}
        </div>
        <div className="form-grid">
          <select value={templateId} onChange={(event) => setTemplateId(event.target.value)}>
            {templates.map((t) => <option key={t.id} value={t.id}>{t.id} — {t.name}</option>)}
          </select>
          <select value={limit} onChange={(event) => setLimit(Number(event.target.value))}>
            {[10, 25, 50, 100, 200].map((n) => <option key={n} value={n}>Preview {n} rows</option>)}
          </select>
        </div>
        {selectedTemplate && <pre className="message-preview">{selectedTemplate.text}</pre>}
        <div className="button-row" style={{ marginTop: 10 }}>
          <button className="primary-button" onClick={runPreview} disabled={busy || !templateId}><Sparkles size={16} /> {busy ? "Working..." : "Personalise & preview"}</button>
          <button className="secondary-button" onClick={queueAll} disabled={busy || !templateId}><Send size={15} /> Queue all with phone</button>
        </div>
      </section>

      {preview && (
        <section className="panel table-panel">
          <div className="table-toolbar">
            <div><div className="section-kicker">STEP 2 · REVIEW & SEND</div><h3>{preview.template_name} — {preview.count} personalised message(s)</h3></div>
            <span className="muted">{activeSegment?.label}</span>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Customer / lead</th><th>Context</th><th>Message (personalised)</th><th>Send</th></tr>
              </thead>
              <tbody>
                {preview.items.map((item, index) => (
                  <tr key={index}>
                    <td className="table-person"><b>{item.name || item.company || "—"}</b><br /><small className="muted">{item.company && item.name ? item.company : ""} {item.phone || "no phone"}</small></td>
                    <td><small>{[item.order_no && `Order ${item.order_no}`, item.amount && `Rs. ${item.amount}`, item.status, item.call_status && `call: ${item.call_status}`].filter(Boolean).join(" · ") || "—"}</small></td>
                    <td><span className="message-snippet">{item.message}</span></td>
                    <td>
                      {item.wa_link
                        ? <a className="text-button wa-send-btn" href={item.wa_link} target="_blank" rel="noreferrer noopener"><Send size={14} /> Open WhatsApp</a>
                        : <small className="muted">no phone</small>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted" style={{ marginTop: 8 }}>Each "Open WhatsApp" opens WhatsApp (app or web) with the personalised message ready in the send box — review and tap Send. Queued messages appear under Outreach / WhatsApp pending for the reviewed send path.</p>
        </section>
      )}
    </div>
  );
}

function ErpDashboard({ onNotice }) {
  const [status, setStatus] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [dispatch, setDispatch] = useState([]);
  const [forecast, setForecast] = useState(null);
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState(false);
  const [yt, setYt] = useState(null);
  const [ytForm, setYtForm] = useState({ youtube_api_key: "", youtube_channel_id: "" });
  const [calc, setCalc] = useState({ polymer_rate: 92, micron: 23, width_mm: 500, length_m: 1000, waste_pct: 2, conversion_cost_per_kg: 18, margin_pct: 8 });
  const [calcOut, setCalcOut] = useState(null);

  const load = async () => {
    try {
      const [s, a, d, f, y] = await Promise.all([
        request("/erp/status"), request("/erp/analytics"),
        request(`/erp/dispatch${filter ? `?status=${encodeURIComponent(filter)}` : ""}`),
        request("/erp/forecast?months=6"), request("/erp/youtube/status"),
      ]);
      setStatus(s); setAnalytics(a); setDispatch(d); setForecast(f); setYt(y);
      setYtForm((cur) => ({ ...cur, youtube_channel_id: cur.youtube_channel_id || y.channel_id || "" }));
    } catch (error) { onNotice({ type: "error", text: error.message }); }
  };
  useEffect(() => { load(); }, [filter]);

  const syncErp = async () => {
    setBusy(true);
    try {
      const r = await request("/erp/sync", { method: "POST" });
      onNotice({ type: "success", text: `ERP synced (${r.report_date}): ${r.dispatch.created} dispatches, ${r.orders.created} orders.` });
      load();
    } catch (error) { onNotice({ type: "error", text: error.message }); }
    finally { setBusy(false); }
  };

  const saveYt = async () => {
    setBusy(true);
    try {
      await request("/erp/settings", { method: "PUT", body: JSON.stringify(ytForm) });
      onNotice({ type: "success", text: "YouTube settings saved." });
      load();
    } catch (error) { onNotice({ type: "error", text: error.message }); }
    finally { setBusy(false); }
  };

  const syncYt = async () => {
    setBusy(true);
    try {
      const r = await request("/erp/youtube/sync", { method: "POST", body: JSON.stringify({ channel_id: ytForm.youtube_channel_id || null }) });
      onNotice({ type: "success", text: `YouTube: ${r.title} — ${r.subscribers} subs, ${r.views} views.` });
      load();
    } catch (error) { onNotice({ type: "error", text: error.message }); }
    finally { setBusy(false); }
  };

  const runCalc = async (event) => {
    event.preventDefault();
    try {
      setCalcOut(await request("/erp/rate-calculator", { method: "POST", body: JSON.stringify(calc) }));
    } catch (error) { onNotice({ type: "error", text: error.message }); }
  };

  const d = status?.dispatch || {};
  const o = status?.orders || {};
  const series = forecast?.series || [];
  const maxVal = Math.max(1, ...series.map((s) => s.value), forecast?.projected_next_month || 0);
  const upd = (k, v) => setCalc((c) => ({ ...c, [k]: Number(v) }));

  return (
    <div className="content">
      <div className="page-heading">
        <div>
          <div className="section-kicker">ERP-THROUGH-SALES · DAILY SYNC</div>
          <h2>ERP & sales forecast</h2>
          <p className="muted">Dispatch and orders mirrored from the ERP report every morning at 06:00 — read-only for field executives, sync controls for admins.</p>
        </div>
        <div className="button-row">
          <button className="icon-button" onClick={load} aria-label="Refresh"><RefreshCw size={17} /></button>
          {status?.is_admin && <button className="primary-button" onClick={syncErp} disabled={busy}><Database size={16} /> {busy ? "Syncing..." : "Sync ERP now"}</button>}
        </div>
      </div>

      <div className="kpi-strip">
        <div className="kpi brand"><div className="k-label">Orders value</div><div className="k-value">₹{((o.total_value || 0) / 1e5).toFixed(1)}L</div><div className="k-sub">{o.records || 0} orders · report {status?.report_date || "—"}</div></div>
        <div className="kpi"><div className="k-label">Dispatch completion</div><div className="k-value">{d.completion_pct || 0}%</div><div className="k-sub">{(d.dispatched_qty || 0).toLocaleString()} / {(d.scheduled_qty || 0).toLocaleString()} qty</div></div>
        <div className="kpi"><div className="k-label">Pending dispatch</div><div className="k-value">{analytics?.pending_followup ?? 0}</div><div className="k-sub">records to follow up</div></div>
        <div className="kpi"><div className="k-label">Customers served</div><div className="k-value">{d.customers || 0}</div><div className="k-sub">{Object.entries(d.by_status || {}).map(([k, v]) => `${k}: ${v}`).join(" · ") || "—"}</div></div>
      </div>

      <div className="funnel">
        <div className="funnel-step"><small>Orders</small><b>{analytics?.funnel?.orders ?? 0}</b></div>
        <ArrowUpRight size={14} className="muted" />
        <div className="funnel-step"><small>Value</small><b>₹{(((analytics?.funnel?.orders_value) || 0) / 1e5).toFixed(1)}L</b></div>
        <ArrowUpRight size={14} className="muted" />
        <div className="funnel-step"><small>Scheduled qty</small><b>{(analytics?.funnel?.scheduled_qty || 0).toLocaleString()}</b></div>
        <ArrowUpRight size={14} className="muted" />
        <div className="funnel-step hot"><small>Dispatched qty</small><b>{(analytics?.funnel?.dispatched_qty || 0).toLocaleString()}</b></div>
      </div>

      <div className="two-column">
        <section className="panel">
          <div className="panel-heading"><div><div className="section-kicker">FORECAST</div><h3>Monthly orders value & next-month projection</h3></div><TrendingUp size={17} className="muted" /></div>
          <div className="bars">
            {series.map((s) => (
              <div className="bar" key={s.period} title={`${s.period}: ₹${s.value.toLocaleString()}`}>
                <i style={{ height: `${Math.max(4, (s.value / maxVal) * 100)}%` }} />
                <small>{s.period.slice(5)}</small>
              </div>
            ))}
            <div className="bar" title={`Projected: ₹${(forecast?.projected_next_month || 0).toLocaleString()}`}>
              <i className="proj" style={{ height: `${Math.max(4, ((forecast?.projected_next_month || 0) / maxVal) * 100)}%` }} />
              <small>proj.</small>
            </div>
          </div>
          <p className="muted" style={{ marginTop: 8, fontSize: 11 }}>{forecast?.method || "Baseline projection"} · projected ₹{(((forecast?.projected_next_month) || 0) / 1e5).toFixed(1)}L next month</p>
          <div className="section-kicker" style={{ marginTop: 14 }}>TOP CUSTOMERS BY DISPATCHED QTY</div>
          <div className="contact-list">
            {(analytics?.top_customers || []).slice(0, 6).map((c) => (
              <div className="contact-row" key={c.customer}>
                <span className="contact-avatar">{c.customer.slice(0, 1)}</span>
                <span className="contact-main"><b>{c.customer}</b><small>{c.dispatched_qty.toLocaleString()} qty dispatched</small></span>
              </div>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="panel-heading"><div><div className="section-kicker">DAILY RATE CALCULATOR</div><h3>Film costing</h3></div><Calculator size={17} className="muted" /></div>
          <form onSubmit={runCalc}>
            <div className="calc-grid">
              <label>Polymer ₹/kg<input type="number" step="0.5" value={calc.polymer_rate} onChange={(e) => upd("polymer_rate", e.target.value)} /></label>
              <label>Micron<input type="number" step="1" value={calc.micron} onChange={(e) => upd("micron", e.target.value)} /></label>
              <label>Width (mm)<input type="number" step="10" value={calc.width_mm} onChange={(e) => upd("width_mm", e.target.value)} /></label>
              <label>Length (m)<input type="number" step="50" value={calc.length_m} onChange={(e) => upd("length_m", e.target.value)} /></label>
              <label>Waste %<input type="number" step="0.5" value={calc.waste_pct} onChange={(e) => upd("waste_pct", e.target.value)} /></label>
              <label>Conversion ₹/kg<input type="number" step="1" value={calc.conversion_cost_per_kg} onChange={(e) => upd("conversion_cost_per_kg", e.target.value)} /></label>
              <label>Margin %<input type="number" step="0.5" value={calc.margin_pct} onChange={(e) => upd("margin_pct", e.target.value)} /></label>
              <label>&nbsp;<button className="primary-button" type="submit" style={{ width: "100%" }}>Calculate</button></label>
            </div>
          </form>
          {calcOut && (
            <div className="calc-result">
              <div><small>Weight</small><b>{calcOut.weight_kg} kg</b></div>
              <div><small>Cost</small><b>₹{calcOut.total_cost}</b></div>
              <div><small>Price (incl. margin)</small><b>₹{calcOut.price}</b></div>
              <div><small>Price / kg</small><b>₹{calcOut.price_per_kg}</b></div>
            </div>
          )}
          <p className="muted" style={{ marginTop: 8, fontSize: 11 }}>weight = width(m) × length(m) × micron/1000 × density(0.92) + waste; price = (material + conversion) × (1 + margin).</p>

          <div className="panel-heading" style={{ marginTop: 18 }}>
            <div><div className="section-kicker">CHANNEL SYNC</div><h3><Video size={16} style={{ verticalAlign: "-3px" }} /> YouTube</h3></div>
            <span className={yt?.data_api_configured ? "pill-ok" : "pill-warn"}>{yt?.data_api_configured ? "Data API ready" : "Not configured"}</span>
          </div>
          {status?.is_admin ? (
            <div className="form-grid" style={{ marginTop: 8 }}>
              <input placeholder="YouTube Data API key" value={ytForm.youtube_api_key} onChange={(e) => setYtForm({ ...ytForm, youtube_api_key: e.target.value })} />
              <input placeholder="Channel ID (UC...)" value={ytForm.youtube_channel_id} onChange={(e) => setYtForm({ ...ytForm, youtube_channel_id: e.target.value })} />
              <button className="secondary-button" onClick={saveYt} disabled={busy}><Save size={15} /> Save keys</button>
              <button className="primary-button" onClick={syncYt} disabled={busy}><RefreshCw size={15} /> Sync now</button>
            </div>
          ) : (
            <p className="muted" style={{ fontSize: 12 }}>An admin adds the API key and channel in ERP settings; channel stats then refresh daily at 07:00.</p>
          )}
          {yt?.cached_stats && (
            <div className="calc-result" style={{ gridTemplateColumns: "repeat(3, 1fr)" }}>
              <div><small>Channel</small><b style={{ fontSize: 13 }}>{yt.cached_stats.title}</b></div>
              <div><small>Subscribers</small><b>{yt.cached_stats.subscribers.toLocaleString()}</b></div>
              <div><small>Views</small><b>{yt.cached_stats.views.toLocaleString()}</b></div>
            </div>
          )}
          <p className="muted" style={{ marginTop: 6, fontSize: 11 }}>Analytics API (watch time, traffic sources) requires OAuth — next scope.</p>
        </section>
      </div>

      <section className="panel table-panel" style={{ marginTop: 14 }}>
        <div className="table-toolbar">
          <div><div className="section-kicker">DISPATCH</div><h3>{dispatch.length} records · {status?.report_date || "—"}</h3></div>
          <select value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="">All statuses</option>
            <option value="Completed">Completed</option>
            <option value="Partially Dispatched">Partially dispatched</option>
          </select>
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Dispatch</th><th>Customer</th><th>Plant</th><th className="num">Scheduled</th><th className="num">Dispatched</th><th className="num">Balance</th><th>%</th><th>Status</th></tr></thead>
            <tbody>
              {dispatch.map((row) => (
                <tr key={row.dispatch_no}>
                  <td className="table-person">{row.dispatch_no}</td>
                  <td>{row.customer}</td>
                  <td>{row.plant}</td>
                  <td className="num">{row.schedule_qty.toLocaleString()}</td>
                  <td className="num">{row.dispatched_qty.toLocaleString()}</td>
                  <td className="num">{row.balance_qty.toLocaleString()}</td>
                  <td><span className={row.pct_complete >= 100 ? "pill-ok" : "pill-warn"}>{row.pct_complete}%</span></td>
                  <td>{row.status}</td>
                </tr>
              ))}
              {!dispatch.length && <tr><td colSpan={8}><div className="empty-state"><Truck size={22} /><p>No dispatch rows yet.</p><small>{status?.is_admin ? "Run “Sync ERP now” to pull the latest report." : "Ask an admin to run the ERP sync."}</small></div></td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function UatOps({ onNotice }) {
  const [uat, setUat] = useState(null);
  const [models, setModels] = useState(null);
  const [prompts, setPrompts] = useState(null);
  const [selectedPrompt, setSelectedPrompt] = useState("");
  const [stories, setStories] = useState([]);
  const [beh, setBeh] = useState(null);
  const [logs, setLogs] = useState(null);
  const [preflight, setPreflight] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      const [u, m, p, s, b, l] = await Promise.all([
        request("/ops/uat"), request("/ops/models"), request("/ops/prompt-samples"),
        request("/journey/stories?limit=8"), request("/journey/behaviours?days=30"),
        request("/ops/logs?limit=12"),
      ]);
      setUat(u); setModels(m); setPrompts(p); setStories(s); setBeh(b); setLogs(l);
      setSelectedPrompt((cur) => cur || p.prompts?.[0]?.id || "");
    } catch (error) { onNotice({ type: "error", text: error.message }); }
  };
  useEffect(() => { load(); }, []);

  const runChecks = async () => {
    setBusy(true);
    try {
      const r = await request("/ops/run-checks", { method: "POST" });
      setPreflight(r);
      onNotice({ type: r.summary.ready ? "success" : "error",
        text: `Checks: ${r.summary.pass} pass · ${r.summary.warn} warn · ${r.summary.fail} fail` });
      load();
    } catch (error) { onNotice({ type: "error", text: error.message }); }
    finally { setBusy(false); }
  };

  const prompt = prompts?.prompts?.find((p) => p.id === selectedPrompt);

  return (
    <div className="content">
      <div className="page-heading">
        <div>
          <div className="section-kicker">PHASE · ERP-UAT</div>
          <h2>UAT &amp; operations</h2>
          <p className="muted">One-week UAT window on preprod with ERP master in production (read-only). Guardrail checks, model selection, prompt samples, journey stories and logs.</p>
        </div>
        <div className="button-row">
          <button className="icon-button" onClick={load} aria-label="Refresh"><RefreshCw size={17} /></button>
          {uat?.is_admin && <button className="primary-button" onClick={runChecks} disabled={busy}><ShieldCheck size={16} /> {busy ? "Checking..." : "Run guardrail checks"}</button>}
        </div>
      </div>

      {uat && (
        <div className="panel" style={{ marginBottom: 14 }}>
          <div className="panel-heading">
            <div><div className="section-kicker">ROLLOUT</div><h3>{uat.uat_active ? "UAT active" : "UAT closed"} · {uat.deploy_env} · {uat.erp_master}</h3></div>
            <span className={uat.uat_active ? "pill-ok" : "pill-warn"}>{uat.days_left ?? "?"} day(s) left · until {uat.enabled_until}</span>
          </div>
          <div className="funnel" style={{ marginTop: 6 }}>
            {uat.features.map((f) => (
              <div className="funnel-step" key={f.name} style={f.status === "enabled" ? undefined : { opacity: .65 }}>
                <small>{f.status}</small><b style={{ fontSize: 12.5 }}>{f.name}</b>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="two-column">
        <section className="panel">
          <div className="panel-heading"><div><div className="section-kicker">MODEL SELECTION</div><h3>Models &amp; human review</h3></div><Sparkles size={16} className="muted" /></div>
          <p className="muted" style={{ fontSize: 11, marginTop: -4 }}>Default: <b>{models?.default}</b> · human review {models?.human_review_required ? "required" : "optional"}</p>
          <div className="contact-list">
            {(models?.models || []).map((m) => (
              <div className="contact-row" key={m.id}>
                <span className="contact-avatar">{m.provider.slice(0, 1).toUpperCase()}</span>
                <span className="contact-main">
                  <b>{m.label}</b>
                  <small>{m.tier} · {m.best_for.slice(0, 2).join(" · ")}</small>
                </span>
                <span className={m.human_review ? "pill-warn" : "pill-ok"}>{m.human_review ? "review" : "auto"}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="panel-heading"><div><div className="section-kicker">PROMPT SAMPLES · {prompts?.version}</div><h3>Weekly prompts (20:00–22:00 IST)</h3></div><Database size={16} className="muted" /></div>
          <select value={selectedPrompt} onChange={(e) => setSelectedPrompt(e.target.value)}>
            {(prompts?.prompts || []).map((p) => <option key={p.id} value={p.id}>{p.id} — {p.task}</option>)}
          </select>
          {prompt && (
            <>
              <div className="muted" style={{ fontSize: 11, margin: "8px 0 4px" }}>
                model <b>{prompt.model}</b> · {prompt.tier} · json {prompt.json_mode ? "yes" : "no"} · human review {prompt.human_review ? "yes" : "no"}
              </div>
              <pre className="message-preview" style={{ maxHeight: 140, overflow: "auto" }}>{prompt.template}</pre>
              <div className="section-kicker" style={{ marginTop: 8 }}>SAMPLE INPUT</div>
              <pre className="message-preview" style={{ maxHeight: 110, overflow: "auto", fontSize: 11 }}>{JSON.stringify(prompt.sample_input, null, 1)}</pre>
              <div className="section-kicker" style={{ marginTop: 8 }}>EXPECTED OUTPUT</div>
              <pre className="message-preview" style={{ maxHeight: 130, overflow: "auto", fontSize: 11 }}>{JSON.stringify(prompt.expected_output, null, 1)}</pre>
            </>
          )}
        </section>
      </div>

      {preflight && (
        <section className="panel table-panel" style={{ marginTop: 14 }}>
          <div className="table-toolbar">
            <div><div className="section-kicker">GUARDRAIL CHECKS</div><h3>{preflight.summary.pass} pass · {preflight.summary.warn} warn · {preflight.summary.fail} fail</h3></div>
            <span className={preflight.summary.ready ? "pill-ok" : "pill-warn"}>{preflight.summary.ready ? "ready to deploy" : "needs attention"}</span>
          </div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Layer</th><th>Check</th><th>Status</th><th>Detail</th><th>Remediation</th></tr></thead>
              <tbody>
                {preflight.checks.map((c) => (
                  <tr key={c.layer + c.id}>
                    <td>{c.layer}</td><td className="table-person">{c.id}</td>
                    <td><span className={c.status === "pass" ? "pill-ok" : "pill-warn"}>{c.status}</span></td>
                    <td><small>{c.detail}</small></td>
                    <td><small className="muted">{c.remediation || "—"}</small></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <div className="two-column" style={{ marginTop: 14 }}>
        <section className="panel">
          <div className="panel-heading"><div><div className="section-kicker">CUSTOMER JOURNEY</div><h3>Recent stories</h3></div><span className="muted">{beh?.total ?? 0} events / {beh?.days ?? 30}d</span></div>
          <div className="contact-list">
            {stories.map((s) => (
              <div className="contact-row" key={s.contact_id}>
                <span className="contact-avatar">{(s.customer_type_label || "?")[0]}</span>
                <span className="contact-main">
                  <b>{s.customer_type_label} · contact #{s.contact_id}</b>
                  <small>{s.current_stage} · next: {s.next_action_template || "—"} · {s.timeline.length} events</small>
                  <small className="muted">{s.feedback_prompt}</small>
                </span>
              </div>
            ))}
            {!stories.length && <div className="empty-state"><Users size={20} /><p>No journey events yet.</p><small>Events are recorded from the feedback pipeline and manual logging.</small></div>}
          </div>
        </section>

        <section className="panel table-panel">
          <div className="table-toolbar"><div><div className="section-kicker">LOGS</div><h3>Sync runs &amp; model usage</h3></div></div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Type</th><th>Job / model</th><th>Status</th><th>When</th></tr></thead>
              <tbody>
                {(logs?.sync_runs || []).slice(0, 6).map((r) => (
                  <tr key={"s" + r.id}><td>sync</td><td className="table-person">{r.job}</td><td>{r.status}</td><td><small>{r.finished_at || r.started_at}</small></td></tr>
                ))}
                {(logs?.model_usage || []).slice(0, 6).map((u) => (
                  <tr key={"u" + u.id}><td>llm</td><td className="table-person">{u.model} · {u.task}</td><td>{u.fallback_used === "True" ? "fallback" : "ok"}</td><td><small>{u.created_at}</small></td></tr>
                ))}
                {!(logs?.sync_runs?.length || logs?.model_usage?.length) && <tr><td colSpan={4}><small className="muted">No logs yet — run checks or use the pipeline.</small></td></tr>}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- Kalika command center
const fmtNum = (v) => Number(v || 0).toLocaleString("en-IN");
const fmtInr = (v) => "₹" + Number(v || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });

function KalikaDash({ onNavigate, onNotice }) {
  const [dash, setDash] = useState(null);
  const [team, setTeam] = useState(null);
  const [chatBody, setChatBody] = useState("");
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      const [d, t] = await Promise.all([request("/dashboard/summary"), request("/team/messages?limit=30")]);
      setDash(d); setTeam(t);
    } catch (error) { onNotice({ type: "error", text: error.message }); }
  };
  useEffect(() => { load(); const timer = setInterval(load, 60000); return () => clearInterval(timer); }, []);

  const postChat = async (event) => {
    event.preventDefault();
    if (!chatBody.trim()) return;
    setBusy(true);
    try {
      await request("/team/messages", { method: "POST", body: JSON.stringify({ kind: "general", body: chatBody.trim() }) });
      setChatBody("");
      load();
    } catch (error) { onNotice({ type: "error", text: error.message }); }
    finally { setBusy(false); }
  };

  if (!dash) return <div className="content"><div className="loading-inline"><RefreshCw size={18} className="spin" /> Loading command center...</div></div>;

  const p = dash.platform, erp = dash.erp, social = dash.social, voice = dash.voice, comms = dash.comms;
  const erpLastSync = p.erp_last_sync ? `${p.erp_last_sync.status} · ${String(p.erp_last_sync.finished_at).slice(0, 16)}` : "never";
  return (
    <div className="content dash">
      <div className="page-heading">
        <div><div className="section-kicker">KALIKA × KALISOFT · LIVE</div>
          <h2>Command center</h2>
          <p className="muted">ERP sales data, platform health, social signals and field updates — one screen. Refreshes every minute.</p>
        </div>
        <button className="secondary-button" onClick={load}><RefreshCw size={15} /> Refresh</button>
      </div>

      <div className="metric-grid dash-grid">
        <Metric icon={Database} label="API endpoints live" value={p.api_endpoints} detail={`env: ${p.env} · ERP sync ${erpLastSync}`} />
        <Metric icon={ShieldCheck} label="GCP services healthy" value={`${p.gcp_healthy}/${p.gcp_services.length}`} detail={p.gcp_services.map((s) => s.service).join(" · ")} accent />
        <Metric icon={Truck} label="Dispatch completion" value={`${erp.funnel.completion_pct}%`} detail={`${fmtNum(erp.funnel.dispatched_qty)} / ${fmtNum(erp.funnel.scheduled_qty)} kg · ${erp.report_date}`} />
        <Metric icon={BriefcaseBusiness} label="Orders value" value={fmtInr(erp.funnel.orders_value)} detail={`${erp.funnel.orders} orders · ${erp.customers} companies`} accent />
        <Metric icon={Mic} label="Voice transcripts" value={voice.total} detail={`${voice.done} analysed · ${voice.pending_review} field updates pending`} />
        <Metric icon={Send} label="Outreach queued" value={social.whatsapp_queued} detail={`${comms.campaigns} campaigns · ${comms.campaign_messages_sent} messages sent`} accent />
      </div>

      <div className="two-column">
        <section className="panel">
          <div className="panel-heading"><div><div className="section-kicker">ERP · SALES DISPATCH</div><h3>Top companies by dispatched qty</h3></div><Truck size={19} className="muted" /></div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Company</th><th>Dispatched (kg)</th><th>Share</th></tr></thead>
              <tbody>
                {erp.top_customers.map((c) => (
                  <tr key={c.customer}><td className="table-person"><b>{c.customer}</b></td><td>{fmtNum(c.dispatched_qty)}</td>
                    <td><div className="bar-track"><div className="bar-fill" style={{ width: `${Math.min(100, (c.dispatched_qty / (erp.top_customers[0]?.dispatched_qty || 1)) * 100)}%` }} /></div></td></tr>
                ))}
                {!erp.top_customers.length && <tr><td colSpan={3}><small className="muted">No ERP data — run ERP sync from the ERP tab.</small></td></tr>}
              </tbody>
            </table>
          </div>
          <div className="mini-stats" style={{ marginTop: 14 }}>
            {Object.entries(erp.status_breakdown).map(([k, v]) => <span key={k}><b>{v}</b> {k}</span>)}
            <span><b>{erp.pending_followup}</b> pending follow-up</span>
          </div>
        </section>

        <section className="panel">
          <div className="panel-heading"><div><div className="section-kicker">TODAY · RECOMMENDED</div><h3>Daily actions</h3></div><Sparkles size={19} className="muted" /></div>
          <div className="rec-list">
            {dash.recommendations.map((r, i) => (
              <div className={`rec-item rec-${r.priority}`} key={i}>
                <span className="rec-badge">{r.priority}</span>
                <div><b>{r.area}</b><p>{r.text}</p></div>
              </div>
            ))}
          </div>
          <div className="panel-heading" style={{ marginTop: 18 }}><div><div className="section-kicker">SOCIAL · DAILY METRICS</div><h3>Channels</h3></div><Video size={19} className="muted" /></div>
          <Service status={!!social.youtube.cached_stats} icon={Video} label="YouTube channel views" value={social.youtube.cached_stats ? fmtNum(social.youtube.cached_stats.views || social.youtube.cached_stats.subscriberCount || 0) : "sync pending"} />
          <Service status={social.linkedin_profiles > 0} icon={BriefcaseBusiness} label="LinkedIn profiles tracked" value={fmtNum(social.linkedin_profiles)} />
          <Service status={social.reddit_posts > 0} icon={Search} label="Reddit hiring posts" value={fmtNum(social.reddit_posts)} />
          <Service status icon={BarChart3} label="6-month order forecast" value={fmtInr(erp.forecast.projected_next_month)} />
        </section>
      </div>

      <div className="two-column" style={{ marginTop: 14 }}>
        <section className="panel">
          <div className="panel-heading"><div><div className="section-kicker">INTERNAL TEAM · DAILY REVIEW</div><h3>Team chat</h3></div><MessageSquarePlus size={19} className="muted" /></div>
          <div className="chat-thread">
            {(team?.messages || []).map((m) => (
              <div className={`chat-row kind-${m.kind}`} key={m.id}>
                <span className="contact-avatar small">{(m.author_name || "?")[0].toUpperCase()}</span>
                <div className="chat-main"><div className="chat-head"><b>{m.author_name}</b><small>{m.kind.replace("_", " ")} · {String(m.created_at).slice(5, 16)}</small>{m.status !== "posted" && <span className={`status-pill ${m.status}`}>{m.status}</span>}</div>
                  <p>{m.body}</p>
                  {m.meta?.transcript && <small className="chat-transcript">🎙 {m.meta.transcript.slice(0, 160)}</small>}
                </div>
              </div>
            ))}
            {!(team?.messages || []).length && <div className="empty-state"><MessageSquarePlus size={22} /><p>No team messages yet.</p><small>Post the daily rate review or a field update.</small></div>}
          </div>
          <form className="chat-input" onSubmit={postChat}>
            <input value={chatBody} onChange={(e) => setChatBody(e.target.value)} placeholder="Update the team — rate change, order note, review..." />
            <button className="primary-button" disabled={busy}><Send size={15} /> Post</button>
          </form>
        </section>

        <section className="panel">
          <div className="panel-heading"><div><div className="section-kicker">VOICE · RECENT FIELD AUDIO</div><h3>Latest transcripts</h3></div><Mic size={19} className="muted" /></div>
          {voice.recent.map((t) => (
            <div className="connection-row" key={t.id}>
              <span className="mail-icon"><Mic size={16} /></span>
              <span><b>{t.file_name}</b><small>{t.status}{t.tone ? ` · tone: ${t.tone}` : ""}</small></span>
              <span className={`status ${t.status === "done" || t.status === "done_heuristic" ? "ok" : "muted-status"}`}><i />{t.status}</span>
            </div>
          ))}
          {!voice.recent.length && <div className="empty-state"><Mic size={22} /><p>No voice notes yet.</p><small>Field desk lets executives record updates.</small></div>}
          <div className="button-row" style={{ marginTop: 14 }}>
            <button className="secondary-button" onClick={() => onNavigate("field")}><Mic size={15} /> Open field desk</button>
            <button className="secondary-button" onClick={() => onNavigate("erp")}><Calculator size={15} /> Rate calculator</button>
          </div>
        </section>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- Field desk (voice -> text -> approve)
function FieldDesk({ onNotice, user }) {
  const [team, setTeam] = useState(null);
  const [note, setNote] = useState("");
  const [recording, setRecording] = useState(false);
  const [recSupported, setRecSupported] = useState(true);
  const [busy, setBusy] = useState(false);
  const recogRef = React.useRef(null);

  const load = async () => {
    try { setTeam(await request("/team/messages?limit=40")); }
    catch (error) { onNotice({ type: "error", text: error.message }); }
  };
  useEffect(() => { load(); }, []);

  const startVoice = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { setRecSupported(false); onNotice({ type: "error", text: "Speech-to-text not supported in this browser — type the update instead." }); return; }
    const recog = new SR();
    recog.lang = "en-IN"; recog.interimResults = true; recog.continuous = true;
    recog.onresult = (event) => {
      let text = "";
      for (const result of event.results) text += result[0].transcript + " ";
      setNote(text.trim());
    };
    recog.onerror = () => { setRecording(false); };
    recog.onend = () => setRecording(false);
    recogRef.current = recog;
    recog.start();
    setRecording(true);
  };
  const stopVoice = () => { recogRef.current?.stop(); setRecording(false); };

  const submit = async (event) => {
    event.preventDefault();
    if (!note.trim()) return;
    setBusy(true);
    try {
      await request("/team/messages", { method: "POST", body: JSON.stringify({ kind: "field_update", body: note.trim(), meta: { source: "field_desk", via: recording ? "voice" : "voice-or-text" } }) });
      setNote("");
      onNotice({ type: "success", text: "Field update sent for approval." });
      load();
    } catch (error) { onNotice({ type: "error", text: error.message }); }
    finally { setBusy(false); }
  };

  const review = async (id, decision) => {
    try {
      await request(`/team/messages/${id}/review`, { method: "POST", body: JSON.stringify({ decision }) });
      onNotice({ type: "success", text: `Update ${decision}.` });
      load();
    } catch (error) { onNotice({ type: "error", text: error.message }); }
  };

  const isField = (user?.email || "").startsWith("field@");
  const pending = (team?.messages || []).filter((m) => m.status === "pending");
  const reviewed = (team?.messages || []).filter((m) => m.status !== "pending");

  return (
    <div className="content dash">
      <div className="page-heading">
        <div><div className="section-kicker">FIELD → SALES · VOICE ENABLED</div>
          <h2>Field desk</h2>
          <p className="muted">Record a voice update from the field — it converts to text, then a sales executive approves or rejects it before it reaches the team.</p>
        </div>
        <button className="secondary-button" onClick={load}><RefreshCw size={15} /> Refresh</button>
      </div>

      <div className="two-column">
        <section className="panel">
          <div className="panel-heading"><div><div className="section-kicker">NEW FIELD UPDATE</div><h3>Voice note → text</h3></div><Mic size={19} className="muted" /></div>
          <form onSubmit={submit}>
            <div className="voice-recorder">
              <button type="button" className={`record-button ${recording ? "recording" : ""}`} onClick={recording ? stopVoice : startVoice}>
                {recording ? <Square size={20} /> : <Mic size={20} />}
              </button>
              <div>
                <b>{recording ? "Listening... speak now" : "Tap to record"}</b>
                <p className="muted">{recSupported ? "Speech converts to text below — edit before sending." : "Browser speech-to-text unavailable — type below."}</p>
              </div>
            </div>
            <textarea className="voice-text" rows={5} value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Visited Mahindra Accelo, Supa — met SCM head, they need 2,000 kg HDPE rolls by next Friday..." />
            <div className="button-row">
              <button className="primary-button" disabled={busy || !note.trim()}><Send size={15} /> Send for approval</button>
              <button type="button" className="secondary-button" onClick={() => setNote("")}>Clear</button>
            </div>
          </form>

          <div className="panel-heading" style={{ marginTop: 22 }}><div><div className="section-kicker">REVIEW QUEUE · TWO-OPTION</div><h3>Pending approval ({pending.length})</h3></div><ShieldCheck size={19} className="muted" /></div>
          {pending.map((m) => (
            <div className="review-card" key={m.id}>
              <div className="chat-head"><b>{m.author_name}</b><small>{String(m.created_at).slice(5, 16)}</small></div>
              <p>{m.body}</p>
              {m.meta?.transcript && <small className="chat-transcript">🎙 {m.meta.transcript.slice(0, 200)}</small>}
              <div className="button-row" style={{ marginTop: 10 }}>
                <button className="primary-button" onClick={() => review(m.id, "approved")}><Check size={15} /> Approve</button>
                <button className="secondary-button danger-button" onClick={() => review(m.id, "rejected")}><X size={15} /> Reject</button>
              </div>
            </div>
          ))}
          {!pending.length && <div className="empty-state"><Check size={22} /><p>Queue is clear.</p><small>{isField ? "Your updates will appear here until approved." : "New field updates land here for your review."}</small></div>}
        </section>

        <section className="panel">
          <div className="panel-heading"><div><div className="section-kicker">TEAM FEED</div><h3>Reviewed updates</h3></div><Users size={19} className="muted" /></div>
          <div className="chat-thread">
            {reviewed.map((m) => (
              <div className={`chat-row kind-${m.kind}`} key={m.id}>
                <span className="contact-avatar small">{(m.author_name || "?")[0].toUpperCase()}</span>
                <div className="chat-main">
                  <div className="chat-head"><b>{m.author_name}</b><small>{String(m.created_at).slice(5, 16)}</small><span className={`status-pill ${m.status}`}>{m.status}</span></div>
                  <p>{m.body}</p>
                  {m.reviewed_by && <small className="muted">reviewed by {m.reviewed_by}</small>}
                </div>
              </div>
            ))}
            {!reviewed.length && <div className="empty-state"><Users size={22} /><p>Nothing reviewed yet.</p></div>}
          </div>
        </section>
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
