import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity, ArrowUpRight, BarChart3, Bell, BriefcaseBusiness, CalendarDays, Check, ChevronDown,
  CircleAlert, Clock, Database, Link2, LogOut, Mail, MapPin, Menu, MessageSquarePlus, Plus, RefreshCw,
  Search, Send, Settings2, ShieldCheck, Sparkles, Star, Trash2, UploadCloud, Users, Video, X,
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
  const [tab, setTab] = useState("overview");
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
          <NavItem icon={Activity} label="Overview" active={tab === "overview"} onClick={() => { setTab("overview"); setMobileNav(false); }} />
          <NavItem icon={Users} label="Contacts" active={tab === "contacts"} onClick={() => { setTab("contacts"); setMobileNav(false); }} />
          <NavItem icon={CalendarDays} label="Events" active={tab === "events"} onClick={() => { setTab("events"); setMobileNav(false); }} />
          <NavItem icon={Mail} label="Email connections" active={tab === "email"} onClick={() => { setTab("email"); setMobileNav(false); }} />
          <NavItem icon={BriefcaseBusiness} label="Signal desk" active={tab === "signals"} onClick={() => { setTab("signals"); setMobileNav(false); }} />
          <NavItem icon={Send} label="Outreach" active={tab === "outreach"} onClick={() => { setTab("outreach"); setMobileNav(false); }} />
          <NavItem icon={Clock} label="Scheduler" active={tab === "scheduler"} onClick={() => { setTab("scheduler"); setMobileNav(false); }} />
          <NavItem icon={BarChart3} label="KPIs" active={tab === "kpis"} onClick={() => { setTab("kpis"); setMobileNav(false); }} />
          <NavItem icon={MessageSquarePlus} label="Feedback" active={tab === "feedback"} onClick={() => { setTab("feedback"); setMobileNav(false); }} />
        </nav>
        <div className="sidebar-bottom">
          <div className="security-note"><ShieldCheck size={16} /><span>Private workspace<br /><small>Google verified access</small></span></div>
          <button className="profile-row" onClick={logout}><span className="avatar">{user.name?.[0] || user.email[0]}</span><span className="profile-copy"><b>{user.name || "Workspace user"}</b><small>{user.email}</small></span><LogOut size={16} /></button>
        </div>
      </aside>
      {mobileNav && <button className="scrim" aria-label="Close menu" onClick={() => setMobileNav(false)} />}
      <main className="main">
        <header className="topbar"><button className="icon-button menu-button" onClick={() => setMobileNav(true)} aria-label="Open menu"><Menu size={20} /></button><div><div className="eyebrow">KALISOFT AI / SALES PIPELINE</div><h1>{tab === "overview" ? "Good work starts with a clear signal." : tab === "contacts" ? "Contacts" : tab === "email" ? "Email connections" : tab === "events" ? "Events" : tab === "signals" ? "Signal desk" : tab === "scheduler" ? "Scheduler" : tab === "kpis" ? "Business KPIs" : tab === "feedback" ? "Feedback" : "Outreach"}</h1></div><div className="topbar-actions"><EnvBadge env={health?.env} /><button className="text-button" onClick={() => setTour(true)}><Sparkles size={15} /> Take the tour</button><span className="live-dot"><i /> API healthy</span><button className="icon-button" aria-label="Settings"><Settings2 size={18} /></button></div></header>
        {tab === "overview" && <Overview onNavigate={setTab} onNotice={setNotice} health={health} setHealth={setHealth} />}
        {tab === "contacts" && <Contacts onNotice={setNotice} />}
        {tab === "email" && <EmailConnections onNotice={setNotice} config={config} />}
        {tab === "events" && <Events onNotice={setNotice} />}
        {tab === "signals" && <Signals onNotice={setNotice} />}
        {tab === "outreach" && <Outreach onNotice={setNotice} />}
        {tab === "scheduler" && <Scheduler onNotice={setNotice} />}
        {tab === "kpis" && <Kpis onNotice={setNotice} />}
        {tab === "feedback" && <Feedback onNotice={setNotice} />}
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
  const login = async (idToken) => {
    setBusy(true);
    try { const result = await request("/auth/google", { method: "POST", body: JSON.stringify({ id_token: idToken }) }); sessionStorage.setItem("sales_token", result.access_token); onLogin(await request("/auth/me")); }
    catch (error) { onNotice({ type: "error", text: error.message }); }
    finally { setBusy(false); }
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
  return <div className="login-page"><div className="login-art"><div className="art-grid" /><div className="art-copy"><div className="brand"><img src="/KalisoftAI-logo.png" alt="Kalisoft AI" className="brand-logo" /><span>Kalisoft <b>AI</b></span></div><h1>Turn scattered signals into your next best conversation.</h1><p>A focused workspace for the people, companies, and market cues that move your pipeline forward.</p><div className="art-stat"><span><b>01</b> verified workspace</span><span><b>02</b> live signal streams</span></div></div></div><section className="login-panel"><div className="panel-inner"><div className="eyebrow">PRIVATE SALES WORKSPACE</div><h2>Welcome back.</h2><p className="muted">Sign in with your verified Google account to continue.</p><div id="google-button" className={config.google_client_id ? "google-button" : "hidden"} />{!config.google_client_id && <div className="config-warning"><CircleAlert size={18} /><span>Google Sign-In is not configured on this environment.</span></div>}{config.dev_mode && <div className="dev-login"><label>Local development access</label><div className="input-action"><input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@company.com" /><button onClick={() => login(`dev:${email}`)} disabled={busy}>{busy ? "Checking..." : "Enter"}<ArrowUpRight size={16} /></button></div><small>Enabled only when AUTH_DEV_MODE is true.</small></div>}<div className="login-footer"><ShieldCheck size={16} /> Your session is protected with short-lived tokens.</div></div></section></div>;
}

function NavItem({ icon: Icon, label, active, onClick }) { return <button className={`nav-item ${active ? "active" : ""}`} onClick={onClick}><Icon size={18} /><span>{label}</span>{active && <ChevronDown size={15} className="nav-caret" />}</button>; }

function EnvBadge({ env }) {
  const normalized = (env || "development").toLowerCase();
  const style = normalized === "production" ? { background: "#e5f6e5", color: "#187a2f", borderColor: "#187a2f" } : normalized === "staging" ? { background: "#fff4d6", color: "#8a5a00", borderColor: "#8a5a00" } : { background: "#e0ecff", color: "#1d4fa3", borderColor: "#1d4fa3" };
  const label = normalized === "production" ? "PROD" : normalized === "staging" ? "UAT" : "DEV";
  return <span title={`Environment: ${normalized}`} style={{ ...style, border: "1px solid", borderRadius: 999, padding: "2px 10px", fontSize: 11, fontWeight: 700, letterSpacing: 0.5 }}>{label}</span>;
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

createRoot(document.getElementById("root")).render(<App />);
