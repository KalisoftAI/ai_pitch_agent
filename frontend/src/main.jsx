import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity, ArrowUpRight, BriefcaseBusiness, Check, ChevronDown, CircleAlert,
  Database, LogOut, Mail, Menu, Plus, RefreshCw, Search, Send, Settings2,
  ShieldCheck, Sparkles, Trash2, UploadCloud, Users, X,
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
  if (!user) return <Login config={config} onLogin={setUser} onNotice={setNotice} />;

  const logout = () => { sessionStorage.removeItem("sales_token"); setUser(null); };
  return (
    <div className="shell">
      <aside className={`sidebar ${mobileNav ? "open" : ""}`}>
        <div className="brand"><div className="brand-mark"><Sparkles size={17} /></div><span>Kalisoft <b>AI</b></span></div>
        <div className="workspace-label">Revenue workspace</div>
        <nav>
          <NavItem icon={Activity} label="Overview" active={tab === "overview"} onClick={() => { setTab("overview"); setMobileNav(false); }} />
          <NavItem icon={Users} label="Contacts" active={tab === "contacts"} onClick={() => { setTab("contacts"); setMobileNav(false); }} />
          <NavItem icon={Mail} label="Email connections" active={tab === "email"} onClick={() => { setTab("email"); setMobileNav(false); }} />
          <NavItem icon={BriefcaseBusiness} label="Signal desk" active={tab === "signals"} onClick={() => { setTab("signals"); setMobileNav(false); }} />
          <NavItem icon={Send} label="Outreach" active={tab === "outreach"} onClick={() => { setTab("outreach"); setMobileNav(false); }} />
        </nav>
        <div className="sidebar-bottom">
          <div className="security-note"><ShieldCheck size={16} /><span>Private workspace<br /><small>Google verified access</small></span></div>
          <button className="profile-row" onClick={logout}><span className="avatar">{user.name?.[0] || user.email[0]}</span><span className="profile-copy"><b>{user.name || "Workspace user"}</b><small>{user.email}</small></span><LogOut size={16} /></button>
        </div>
      </aside>
      {mobileNav && <button className="scrim" aria-label="Close menu" onClick={() => setMobileNav(false)} />}
      <main className="main">
        <header className="topbar"><button className="icon-button menu-button" onClick={() => setMobileNav(true)} aria-label="Open menu"><Menu size={20} /></button><div><div className="eyebrow">KALISOFT AI / SALES PIPELINE</div><h1>{tab === "overview" ? "Good work starts with a clear signal." : tab === "contacts" ? "Contacts" : tab === "email" ? "Email connections" : tab === "signals" ? "Signal desk" : "Outreach"}</h1></div><div className="topbar-actions"><span className="live-dot"><i /> API healthy</span><button className="icon-button" aria-label="Settings"><Settings2 size={18} /></button></div></header>
        {tab === "overview" && <Overview onNavigate={setTab} onNotice={setNotice} health={health} setHealth={setHealth} />}
        {tab === "contacts" && <Contacts onNotice={setNotice} />}
        {tab === "email" && <EmailConnections onNotice={setNotice} />}
        {tab === "signals" && <Signals onNotice={setNotice} />}
        {tab === "outreach" && <Outreach onNotice={setNotice} />}
      </main>
      {notice && <div className={`toast ${notice.type === "error" ? "error" : ""}`}><span>{notice.type === "error" ? <CircleAlert size={17} /> : <Check size={17} />}</span>{notice.text}<button onClick={() => setNotice(null)} aria-label="Dismiss"><X size={15} /></button></div>}
    </div>
  );
}

async function requestPublicConfig() { const response = await fetch(`${API}/config`); if (!response.ok) throw new Error("API configuration unavailable"); return response.json(); }

function LoadingScreen() { return <div className="loading-screen"><div className="brand-mark"><Sparkles size={18} /></div><span>Preparing your workspace...</span></div>; }

function Login({ config, onLogin, onNotice }) {
  const [email, setEmail] = useState("owner@kalisoftai.com");
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
  return <div className="login-page"><div className="login-art"><div className="art-grid" /><div className="art-copy"><div className="brand"><div className="brand-mark"><Sparkles size={17} /></div><span>Kalisoft <b>AI</b></span></div><h1>Turn scattered signals into your next best conversation.</h1><p>A focused workspace for the people, companies, and market cues that move your pipeline forward.</p><div className="art-stat"><span><b>01</b> verified workspace</span><span><b>02</b> live signal streams</span></div></div></div><section className="login-panel"><div className="panel-inner"><div className="eyebrow">PRIVATE SALES WORKSPACE</div><h2>Welcome back.</h2><p className="muted">Sign in with your verified Google account to continue.</p><div id="google-button" className={config.google_client_id ? "google-button" : "hidden"} />{!config.google_client_id && <div className="config-warning"><CircleAlert size={18} /><span>Google Sign-In is not configured on this environment.</span></div>}{config.dev_mode && <div className="dev-login"><label>Local development access</label><div className="input-action"><input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@company.com" /><button onClick={() => login(`dev:${email}`)} disabled={busy}>{busy ? "Checking..." : "Enter"}<ArrowUpRight size={16} /></button></div><small>Enabled only when AUTH_DEV_MODE is true.</small></div>}<div className="login-footer"><ShieldCheck size={16} /> Your session is protected with short-lived tokens.</div></div></section></div>;
}

function NavItem({ icon: Icon, label, active, onClick }) { return <button className={`nav-item ${active ? "active" : ""}`} onClick={onClick}><Icon size={18} /><span>{label}</span>{active && <ChevronDown size={15} className="nav-caret" />}</button>; }

function Overview({ onNavigate, onNotice, health, setHealth }) {
  const [stats, setStats] = useState(null);
  const [contacts, setContacts] = useState([]);
  const refresh = async () => { try { const [nextStats, nextContacts, nextHealth] = await Promise.all([request("/contacts/stats"), request("/contacts?q=") , request("/health")]); setStats(nextStats); setContacts(nextContacts.slice(0, 5)); setHealth(nextHealth); } catch (error) { onNotice({ type: "error", text: error.message }); } };
  useEffect(() => { refresh(); }, []);
  return <div className="content"><div className="welcome-row"><div><div className="section-kicker">MONDAY, SEPTEMBER 14, 2026</div><h2>Pipeline at a glance</h2><p className="muted">A quiet view of what needs your attention next.</p></div><button className="primary-button" onClick={() => onNavigate("contacts")}><Plus size={17} /> Add contact</button></div><div className="metric-grid"><Metric label="Total contacts" value={stats?.total ?? "--"} detail="across your workspace" icon={Users} /><Metric label="Ready to reach" value={stats ? Object.values(stats.by_intent || {}).reduce((sum, value) => sum + value, 0) : "--"} detail="classified signals" icon={Sparkles} accent /><Metric label="API status" value={health?.status === "healthy" ? "Live" : "--"} detail={health?.database === "ok" ? "database connected" : "checking services"} icon={Activity} /></div><div className="two-column"><section className="panel"><div className="panel-heading"><div><div className="section-kicker">RECENTLY ADDED</div><h3>Latest contacts</h3></div><button className="text-button" onClick={() => onNavigate("contacts")}>View all <ArrowUpRight size={15} /></button></div><ContactRows contacts={contacts} /></section><section className="panel signal-panel"><div className="panel-heading"><div><div className="section-kicker">SYSTEM PULSE</div><h3>Connected services</h3></div><button className="icon-button" onClick={refresh} aria-label="Refresh services"><RefreshCw size={17} /></button></div><Service status={health?.database === "ok"} icon={Database} label="PostgreSQL / SQLite" value={health?.database === "ok" ? "Connected" : "Degraded"} /><Service status={health?.gcs_available} icon={UploadCloud} label="Google Cloud Storage" value={health?.gcs_available ? "Available" : "Optional"} /><Service status={health?.google_signin_configured} icon={ShieldCheck} label="Google Sign-In" value={health?.google_signin_configured ? "Configured" : "Not configured"} /></section></div></div>;
}

function Metric({ label, value, detail, icon: Icon, accent }) { return <div className={`metric ${accent ? "accent" : ""}`}><div className="metric-icon"><Icon size={18} /></div><div className="metric-label">{label}</div><div className="metric-value">{value}</div><div className="metric-detail">{detail}</div></div>; }
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

function EmailConnections({ onNotice }) { const [connections, setConnections] = useState([]); const [form, setForm] = useState({ email_address: "", imap_host: "imap.gmail.com", imap_port: 993, smtp_host: "smtp.gmail.com", smtp_port: 587, password: "" }); const [show, setShow] = useState(false); const load = () => request("/email/connections").then(setConnections).catch((error) => onNotice({ type: "error", text: error.message })); useEffect(() => { load(); }, []); const add = async (event) => { event.preventDefault(); try { await request("/email/connections", { method: "POST", body: JSON.stringify(form) }); setShow(false); setForm({ email_address: "", imap_host: "imap.gmail.com", imap_port: 993, smtp_host: "smtp.gmail.com", smtp_port: 587, password: "" }); onNotice({ type: "success", text: "Email connection saved encrypted." }); load(); } catch (error) { onNotice({ type: "error", text: error.message }); } }; const test = async (id) => { try { const result = await request(`/email/connections/${id}/test`, { method: "POST" }); onNotice({ type: result.is_connected ? "success" : "error", text: result.is_connected ? "IMAP and SMTP are connected." : "Connection test failed." }); load(); } catch (error) { onNotice({ type: "error", text: error.message }); } }; return <div className="content"><div className="page-heading"><div><div className="section-kicker">OUTREACH INFRASTRUCTURE</div><h2>Email connections</h2><p className="muted">Credentials are encrypted before they are stored.</p></div><button className="primary-button" onClick={() => setShow(!show)}><Plus size={17} /> Add mailbox</button></div>{show && <form className="panel form-panel" onSubmit={add}><div className="form-grid"><input required type="email" placeholder="Mailbox email" value={form.email_address} onChange={(event) => setForm({ ...form, email_address: event.target.value })} /><input required type="password" placeholder="App password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} /><input placeholder="IMAP host" value={form.imap_host} onChange={(event) => setForm({ ...form, imap_host: event.target.value })} /><input placeholder="SMTP host" value={form.smtp_host} onChange={(event) => setForm({ ...form, smtp_host: event.target.value })} /></div><button className="primary-button">Save encrypted connection</button></form>}<section className="panel"><div className="panel-heading"><div><div className="section-kicker">CONNECTED MAILBOXES</div><h3>Sender accounts</h3></div><Mail size={19} className="muted" /></div>{connections.length ? connections.map((connection) => <div className="connection-row" key={connection.id}><span className="mail-icon"><Mail size={17} /></span><span><b>{connection.email_address}</b><small>{connection.smtp_host} / {connection.imap_host}</small></span><span className={`status ${connection.is_connected ? "ok" : "muted-status"}`}><i />{connection.is_connected ? "Connected" : "Not tested"}</span><button className="secondary-button compact" onClick={() => test(connection.id)}><RefreshCw size={15} /> Test</button></div>) : <div className="empty-state"><Mail size={22} /><p>No mailboxes connected.</p><small>Use a Gmail app password, never your primary password.</small></div>}</section></div>; }

function Signals({ onNotice }) { const [output, setOutput] = useState(null); const [busy, setBusy] = useState(false); const run = async (path, body, label) => { setBusy(true); try { setOutput({ label, data: await request(path, { method: "POST", body: JSON.stringify(body) }) }); } catch (error) { onNotice({ type: "error", text: error.message }); } finally { setBusy(false); } }; return <div className="content"><div className="page-heading"><div><div className="section-kicker">MARKET INTELLIGENCE</div><h2>Signal desk</h2><p className="muted">Queue the searches and background work that sharpen your next move.</p></div></div><div className="signal-actions"><button className="signal-action" onClick={() => run("/social/linkedin/search", { keywords: ["procurement", "scm", "hiring"] }, "LinkedIn hiring search")}><span><BriefcaseBusiness size={20} /></span><b>LinkedIn hiring search</b><small>Find hiring signals in procurement and SCM.</small><ArrowUpRight size={16} /></button><button className="signal-action" onClick={() => run("/social/reddit/search", {}, "Reddit hiring search")}><span><Search size={20} /></span><b>Reddit hiring search</b><small>Scan communities for useful conversations.</small><ArrowUpRight size={16} /></button><button className="signal-action" onClick={() => run("/cron/run", {}, "Cron sweep")}><span><RefreshCw size={20} /></span><b>Run cron sweep</b><small>Queue the scheduled pipeline tasks.</small><ArrowUpRight size={16} /></button></div>{busy && <div className="panel loading-inline"><RefreshCw size={18} className="spin" /> Working through the signal stream...</div>}{output && <section className="panel output-panel"><div className="panel-heading"><h3>{output.label}</h3><button className="icon-button" onClick={() => setOutput(null)} aria-label="Close"><X size={17} /></button></div><pre>{JSON.stringify(output.data, null, 2)}</pre></section>}</div>; }

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

createRoot(document.getElementById("root")).render(<App />);
