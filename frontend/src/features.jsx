import React, { useEffect, useState } from "react";
import {
  Activity, BarChart3, Bot, BriefcaseBusiness, Building2, CalendarDays, Calculator, Check, Clock,
  Database, FileDown, Link2, MapPin, Mic, Package, Plus, RefreshCw, Save, Search, Send, ShieldCheck,
  Sparkles, TrendingUp, Truck, UploadCloud, Users, Video, X,
} from "lucide-react";

const API = "/api";
const readToken = () => sessionStorage.getItem("sales_token") || "";

async function request(path, options = {}) {
  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  const headers = { ...(options.body && !isFormData ? { "Content-Type": "application/json" } : {}), ...(options.headers || {}) };
  const token = readToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${API}${path}`, { ...options, headers });
  if (response.status === 401) {
    sessionStorage.removeItem("sales_token");
    window.dispatchEvent(new Event("auth-expired"));
  }
  if (!response.ok) {
    let message = "Request failed";
    try { message = (await response.json()).detail || message; } catch { /* not JSON */ }
    throw new Error(typeof message === "string" ? message : JSON.stringify(message));
  }
  return response.status === 204 ? null : response.json();
}

const fmtNum = (value) => Number(value || 0).toLocaleString("en-IN");
const fmtMoney = (value) => `Rs ${Number(value || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

function Metric({ label, value, detail, icon: Icon, accent }) {
  return <div className={`metric ${accent ? "accent" : ""}`}><div className="metric-icon"><Icon size={18} /></div><div className="metric-label">{label}</div><div className="metric-value">{value}</div><div className="metric-detail">{detail}</div></div>;
}

function Service({ status, icon: Icon, label, value }) {
  return <div className="connection-row"><span className="mail-icon"><Icon size={16} /></span><span><b>{label}</b><small>{value}</small></span><span className={`status ${status ? "ok" : "muted-status"}`}><i />{status ? "ready" : "setup"}</span></div>;
}

// ---------------------------------------------------------------- Sales BI
export function SalesBi({ onNotice }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = async () => {
    setBusy(true);
    try {
      const [overview, companies, delivery] = await Promise.all([
        request("/sales/overview"), request("/sales/companies?limit=25"), request("/sales/delivery"),
      ]);
      setData({ overview, companies, delivery });
    } catch (error) { onNotice({ type: "error", text: error.message }); }
    finally { setBusy(false); }
  };
  useEffect(() => { load(); }, []);
  const download = async (dataset, format) => {
    try {
      const response = await fetch(`${API}/sales/export?dataset=${dataset}&format=${format}`, {
        headers: { Authorization: `Bearer ${readToken()}` },
      });
      if (!response.ok) throw new Error("Export failed");
      const blob = await response.blob();
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `kalika-${dataset}.${format}`;
      link.click();
      URL.revokeObjectURL(link.href);
    } catch (error) { onNotice({ type: "error", text: error.message }); }
  };
  if (!data) return <div className="content"><div className="loading-inline"><RefreshCw size={18} className="spin" /> Loading sales analytics...</div></div>;
  const { overview, companies, delivery } = data;
  const totals = overview.totals || {};
  const maxValue = Math.max(...(companies || []).map((row) => row.orders_value || 0), 1);
  return (
    <div className="content dash">
      <div className="page-heading">
        <div><div className="section-kicker">REAL ERP DATA / SALES INTELLIGENCE</div><h2>Sales analytics &amp; BI</h2>
          <p className="muted">Orders, value, dispatch completion and company mix from the latest synced ERP report.</p></div>
        <div className="button-row">
          <button className="secondary-button" onClick={load} disabled={busy}><RefreshCw size={15} className={busy ? "spin" : ""} /> Refresh</button>
          <button className="secondary-button" onClick={() => download("companies", "xlsx")}><FileDown size={15} /> XLSX</button>
          <button className="secondary-button" onClick={() => download("companies", "pdf")}><FileDown size={15} /> PDF</button>
        </div>
      </div>
      {!overview.data_available && <div className="empty-state"><Database size={22} /><p>No ERP report synced yet.</p><small>Run ERP sync from the ERP tab to populate real analytics.</small></div>}
      <div className="metric-grid dash-grid">
        <Metric icon={BriefcaseBusiness} label="Orders" value={fmtNum(totals.orders)} detail={`${fmtNum(totals.customers)} companies`} accent />
        <Metric icon={TrendingUp} label="Orders value" value={fmtMoney(totals.orders_value)} detail={`avg ${fmtMoney(totals.average_order_value)}`} />
        <Metric icon={Truck} label="Dispatched" value={fmtNum(totals.dispatched_qty)} detail={`${fmtNum(totals.scheduled_qty)} scheduled`} />
        <Metric icon={BarChart3} label="Completion" value={`${totals.completion_pct || 0}%`} detail={`${totals.pending_dispatch || 0} pending lines`} accent />
      </div>
      <div className="two-column">
        <section className="panel">
          <div className="panel-heading"><div><div className="section-kicker">COMPANY MIX</div><h3>Top companies by order value</h3></div><BriefcaseBusiness size={19} className="muted" /></div>
          <div className="table-wrap"><table><thead><tr><th>Company</th><th>Orders</th><th>Value</th><th>Completion</th></tr></thead><tbody>
            {(companies || []).map((row) => <tr key={row.company}><td className="table-person"><b>{row.company}</b><div className="bar-track"><div className="bar-fill" style={{ width: `${Math.min(100, (row.orders_value / maxValue) * 100)}%` }} /></div></td><td>{fmtNum(row.orders)}</td><td>{fmtMoney(row.orders_value)}</td><td>{row.completion_pct}%</td></tr>)}
            {!(companies || []).length && <tr><td colSpan={4}><small className="muted">No companies in the latest report.</small></td></tr>}
          </tbody></table></div>
        </section>
        <section className="panel">
          <div className="panel-heading"><div><div className="section-kicker">DELIVERY / PLANT VIEW</div><h3>Dispatch status</h3></div><Truck size={19} className="muted" /></div>
          <div className="mini-stats">{(delivery.plants || []).map((plant) => <span key={plant.plant}><b>{plant.completion_pct}%</b> {plant.plant} / {fmtNum(plant.dispatched_qty)} kg</span>)}</div>
          {(delivery.pending || []).slice(0, 8).map((row) => <div className="connection-row" key={row.dispatch_no}><span className="mail-icon"><Truck size={16} /></span><span><b>{row.customer}</b><small>{row.dispatch_no} / balance {fmtNum(row.balance_qty)} kg / {row.plant}</small></span><span className="status"><i />{row.status}</span></div>)}
          {!(delivery.pending || []).length && <div className="empty-state"><Check size={22} /><p>No pending dispatch lines.</p></div>}
        </section>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- Catalogue and rates
export function Catalogue({ onNotice }) {
  const [products, setProducts] = useState([]);
  const [summary, setSummary] = useState(null);
  const [rates, setRates] = useState({ today: [], pending: [], pending_count: 0 });
  const [form, setForm] = useState({ name: "", code: "", category: "", unit: "kg", description: "" });
  const [rateForm, setRateForm] = useState({ product_id: "", rate: "", effective_date: "", notes: "" });
  const [quoteForm, setQuoteForm] = useState({ product_id: "", micron: 50, width_mm: 500, length_m: 1000, waste_pct: 2, conversion_cost_per_kg: 18, margin_pct: 8 });
  const [quote, setQuote] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = async () => {
    try {
      const [nextProducts, nextSummary, nextRates] = await Promise.all([
        request("/catalog/products"), request("/catalog/summary"), request("/catalog/rate-today"),
      ]);
      setProducts(nextProducts); setSummary(nextSummary); setRates(nextRates);
      if (nextProducts.length) {
        setRateForm((current) => ({ ...current, product_id: current.product_id || String(nextProducts[0].id) }));
        setQuoteForm((current) => ({ ...current, product_id: current.product_id || String(nextProducts[0].id) }));
      }
    } catch (error) { onNotice({ type: "error", text: error.message }); }
  };
  useEffect(() => { load(); }, []);
  const createProduct = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      await request("/catalog/products", { method: "POST", body: JSON.stringify(form) });
      setForm({ name: "", code: "", category: "", unit: "kg", description: "" });
      onNotice({ type: "success", text: "Product added to the shared catalogue." });
      await load();
    } catch (error) { onNotice({ type: "error", text: error.message }); }
    finally { setBusy(false); }
  };
  const submitRate = async (event) => {
    event.preventDefault();
    if (!rateForm.product_id) return;
    setBusy(true);
    try {
      await request("/catalog/rates", { method: "POST", body: JSON.stringify({ ...rateForm, product_id: Number(rateForm.product_id), rate: Number(rateForm.rate) }) });
      setRateForm((current) => ({ ...current, rate: "", notes: "" }));
      onNotice({ type: "success", text: "Rate submitted for approval." });
      await load();
    } catch (error) { onNotice({ type: "error", text: error.message }); }
    finally { setBusy(false); }
  };
  const review = async (id, decision) => {
    try {
      await request(`/catalog/rates/${id}/review`, { method: "POST", body: JSON.stringify({ decision }) });
      onNotice({ type: "success", text: `Rate ${decision}.` });
      await load();
    } catch (error) { onNotice({ type: "error", text: error.message }); }
  };
  const calculate = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      const result = await request("/catalog/quote", { method: "POST", body: JSON.stringify({ ...quoteForm, product_id: Number(quoteForm.product_id) }) });
      setQuote(result);
    } catch (error) { onNotice({ type: "error", text: error.message }); }
    finally { setBusy(false); }
  };
  const productName = (id) => products.find((product) => product.id === id)?.name || `Product ${id}`;
  return (
    <div className="content dash">
      <div className="page-heading">
        <div><div className="section-kicker">PRICING / DAILY REVIEW</div><h2>Catalogue &amp; rates</h2>
          <p className="muted">Shared product master, daily rate submissions with approval, and film costing.</p></div>
        <button className="secondary-button" onClick={load}><RefreshCw size={15} /> Refresh</button>
      </div>
      <div className="metric-grid">
        <Metric icon={Package} label="Products" value={summary?.products ?? "--"} detail={`${summary?.active_products ?? 0} active`} accent />
        <Metric icon={Clock} label="Pending rates" value={summary?.pending_rates ?? "--"} detail="awaiting approval" />
        <Metric icon={Check} label="Approved rates" value={summary?.approved_rates ?? "--"} detail={summary?.latest_rate_date || "no rate date"} />
      </div>
      <div className="two-column">
        <section className="panel">
          <div className="panel-heading"><div><div className="section-kicker">PRODUCT MASTER</div><h3>Add a product</h3></div><Package size={19} className="muted" /></div>
          <form onSubmit={createProduct}><div className="form-grid">
            <input required placeholder="Product name *" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
            <input placeholder="Code (auto if blank)" value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value })} />
            <input placeholder="Category" value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} />
            <input placeholder="Unit" value={form.unit} onChange={(event) => setForm({ ...form, unit: event.target.value })} />
          </div><input placeholder="Description" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /><button className="primary-button" disabled={busy}><Plus size={15} /> Add product</button></form>
          <div className="panel-heading" style={{ marginTop: 22 }}><div><div className="section-kicker">SUBMIT A RATE</div><h3>Daily rate</h3></div><Calculator size={19} className="muted" /></div>
          <form onSubmit={submitRate}><div className="form-grid">
            <select value={rateForm.product_id} onChange={(event) => setRateForm({ ...rateForm, product_id: event.target.value })}><option value="">Select product</option>{products.map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}</select>
            <input required type="number" step="0.01" placeholder="Rate *" value={rateForm.rate} onChange={(event) => setRateForm({ ...rateForm, rate: event.target.value })} />
            <input type="date" value={rateForm.effective_date} onChange={(event) => setRateForm({ ...rateForm, effective_date: event.target.value })} />
            <input placeholder="Notes" value={rateForm.notes} onChange={(event) => setRateForm({ ...rateForm, notes: event.target.value })} />
          </div><button className="secondary-button" disabled={busy || !products.length}><Save size={15} /> Submit for approval</button></form>
        </section>
        <section className="panel">
          <div className="panel-heading"><div><div className="section-kicker">APPROVAL QUEUE</div><h3>Pending rates ({rates.pending_count || 0})</h3></div><ShieldCheck size={19} className="muted" /></div>
          {(rates.pending || []).map((rate) => <div className="review-card" key={rate.id}><div className="chat-head"><b>{rate.product_name || productName(rate.product_id)}</b><small>{rate.currency} {fmtNum(rate.rate)} / {rate.unit}</small></div><p>{rate.notes || "No notes"}</p><small className="muted">by {rate.submitted_by || "team"} / {rate.effective_date}</small><div className="button-row" style={{ marginTop: 10 }}><button className="primary-button" onClick={() => review(rate.id, "approved")}><Check size={15} /> Approve</button><button className="secondary-button danger-button" onClick={() => review(rate.id, "rejected")}><X size={15} /> Reject</button></div></div>)}
          {!(rates.pending || []).length && <div className="empty-state"><Check size={22} /><p>No rates pending.</p></div>}
          <div className="panel-heading" style={{ marginTop: 18 }}><div><div className="section-kicker">QUOTE CALCULATOR</div><h3>Film costing</h3></div><Calculator size={19} className="muted" /></div>
          <form onSubmit={calculate}><div className="form-grid">
            <select value={quoteForm.product_id} onChange={(event) => setQuoteForm({ ...quoteForm, product_id: event.target.value })}><option value="">Select product</option>{products.map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}</select>
            <input type="number" placeholder="Micron" value={quoteForm.micron} onChange={(event) => setQuoteForm({ ...quoteForm, micron: Number(event.target.value) })} />
            <input type="number" placeholder="Width mm" value={quoteForm.width_mm} onChange={(event) => setQuoteForm({ ...quoteForm, width_mm: Number(event.target.value) })} />
            <input type="number" placeholder="Length m" value={quoteForm.length_m} onChange={(event) => setQuoteForm({ ...quoteForm, length_m: Number(event.target.value) })} />
            <input type="number" placeholder="Waste %" value={quoteForm.waste_pct} onChange={(event) => setQuoteForm({ ...quoteForm, waste_pct: Number(event.target.value) })} />
            <input type="number" placeholder="Conversion cost/kg" value={quoteForm.conversion_cost_per_kg} onChange={(event) => setQuoteForm({ ...quoteForm, conversion_cost_per_kg: Number(event.target.value) })} />
          </div><button className="secondary-button" disabled={busy || !products.length}><Calculator size={15} /> Calculate quote</button></form>
          {quote && <div className="mini-stats" style={{ marginTop: 14 }}><span><b>{fmtMoney(quote.price)}</b> price</span><span><b>{fmtMoney(quote.total_cost)}</b> cost</span><span><b>{quote.gross_weight_kg}</b> kg</span><span><b>{fmtMoney(quote.price_per_kg)}</b> per kg</span></div>}
        </section>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- Company visits
export function CompanyVisits({ onNotice }) {
  const today = new Date().toISOString().slice(0, 10);
  const [visits, setVisits] = useState([]);
  const [stats, setStats] = useState(null);
  const [form, setForm] = useState({ company: "", contact_name: "", contact_phone: "", visit_date: today, outcome: "", follow_up_date: "", notes: "", next_action: "" });
  const [uploading, setUploading] = useState(0);
  const load = async () => {
    try {
      const [nextVisits, nextStats] = await Promise.all([request("/visits"), request("/visits/stats")]);
      setVisits(nextVisits); setStats(nextStats);
    } catch (error) { onNotice({ type: "error", text: error.message }); }
  };
  useEffect(() => { load(); }, []);
  const create = async (event) => {
    event.preventDefault();
    try {
      await request("/visits", { method: "POST", body: JSON.stringify(form) });
      setForm({ company: "", contact_name: "", contact_phone: "", visit_date: today, outcome: "", follow_up_date: "", notes: "", next_action: "" });
      onNotice({ type: "success", text: "Visit saved." });
      await load();
    } catch (error) { onNotice({ type: "error", text: error.message }); }
  };
  const upload = async (visit, file) => {
    if (!file) return;
    setUploading(visit.id);
    try {
      const body = new FormData();
      body.append("file", file);
      body.append("kind", file.type.startsWith("video/") ? "video" : "photo");
      await request(`/visits/${visit.id}/media`, { method: "POST", body });
      onNotice({ type: "success", text: "Attachment uploaded to GCS." });
      await load();
    } catch (error) { onNotice({ type: "error", text: error.message }); }
    finally { setUploading(0); }
  };
  return (
    <div className="content dash">
      <div className="page-heading">
        <div><div className="section-kicker">FIELD / COMPANY HISTORY</div><h2>Company visits</h2>
          <p className="muted">Log visits, outcomes, follow-ups and attach photo/video evidence in GCS.</p></div>
        <button className="secondary-button" onClick={load}><RefreshCw size={15} /> Refresh</button>
      </div>
      <div className="metric-grid">
        <Metric icon={MapPin} label="Visits" value={stats?.visits ?? "--"} detail={`${stats?.companies ?? 0} companies`} accent />
        <Metric icon={CalendarDays} label="This month" value={stats?.this_month ?? "--"} detail="logged visits" />
        <Metric icon={Clock} label="Follow-ups" value={stats?.pending_followups ?? "--"} detail="due or upcoming" />
        <Metric icon={UploadCloud} label="Attachments" value={stats?.media ?? "--"} detail="photos & videos" />
      </div>
      <div className="two-column">
        <section className="panel">
          <div className="panel-heading"><div><div className="section-kicker">NEW VISIT</div><h3>Capture the meeting</h3></div><MapPin size={19} className="muted" /></div>
          <form onSubmit={create}><div className="form-grid">
            <input required placeholder="Company *" value={form.company} onChange={(event) => setForm({ ...form, company: event.target.value })} />
            <input placeholder="Contact name" value={form.contact_name} onChange={(event) => setForm({ ...form, contact_name: event.target.value })} />
            <input placeholder="Phone" value={form.contact_phone} onChange={(event) => setForm({ ...form, contact_phone: event.target.value })} />
            <input type="date" value={form.visit_date} onChange={(event) => setForm({ ...form, visit_date: event.target.value })} />
            <input placeholder="Outcome (e.g. quote_requested)" value={form.outcome} onChange={(event) => setForm({ ...form, outcome: event.target.value })} />
            <input type="date" placeholder="Follow-up date" value={form.follow_up_date} onChange={(event) => setForm({ ...form, follow_up_date: event.target.value })} />
          </div>
          <textarea className="voice-text" rows={3} placeholder="Visit notes" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} />
          <input placeholder="Next action" value={form.next_action} onChange={(event) => setForm({ ...form, next_action: event.target.value })} />
          <button className="primary-button"><Plus size={15} /> Save visit</button></form>
        </section>
        <section className="panel">
          <div className="panel-heading"><div><div className="section-kicker">VISIT HISTORY</div><h3>Recent meetings</h3></div><Building2 size={19} className="muted" /></div>
          <div className="table-wrap"><table><thead><tr><th>Company</th><th>Date</th><th>Outcome</th><th>Follow-up</th><th>Media</th></tr></thead><tbody>
            {visits.map((visit) => <tr key={visit.id}><td className="table-person"><b>{visit.company}</b><small>{visit.contact_name || visit.notes?.slice(0, 50)}</small></td><td>{visit.visit_date}</td><td>{visit.outcome || visit.status}</td><td>{visit.follow_up_date || "-"}</td><td><label className="text-button">{uploading === visit.id ? "Uploading..." : `${(visit.media || []).length} file(s) +`}<input type="file" accept="image/*,video/*" hidden onChange={(event) => upload(visit, event.target.files?.[0])} /></label></td></tr>)}
            {!visits.length && <tr><td colSpan={5}><div className="empty-state"><MapPin size={22} /><p>No visits yet.</p><small>Log the first field meeting.</small></div></td></tr>}
          </tbody></table></div>
        </section>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- Social & AI
export function SocialAi({ onNotice }) {
  const [social, setSocial] = useState(null);
  const [recs, setRecs] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = async () => {
    try {
      const [nextSocial, nextRecs, nextAnalytics, nextStatus] = await Promise.all([
        request("/social/overview"), request("/ai/recommendations?limit=12"),
        request("/ai/communication-analytics"), request("/ai/status"),
      ]);
      setSocial(nextSocial); setRecs(nextRecs); setAnalytics(nextAnalytics); setStatus(nextStatus);
    } catch (error) { onNotice({ type: "error", text: error.message }); }
  };
  useEffect(() => { load(); }, []);
  const syncInstagram = async () => {
    setBusy(true);
    try {
      const result = await request("/social/instagram/sync", { method: "POST" });
      onNotice({ type: result.configured ? "success" : "error", text: result.message || "Instagram synced." });
      await load();
    } catch (error) { onNotice({ type: "error", text: error.message }); }
    finally { setBusy(false); }
  };
  const instagram = social?.instagram || {};
  return (
    <div className="content dash">
      <div className="page-heading">
        <div><div className="section-kicker">SOCIAL SIGNALS / RECOMMENDATIONS</div><h2>Social &amp; AI insights</h2>
          <p className="muted">Real Instagram/YouTube/LinkedIn status, communication analytics and data-driven next actions.</p></div>
        <button className="secondary-button" onClick={load}><RefreshCw size={15} /> Refresh</button>
      </div>
      <div className="metric-grid">
        <Metric icon={Bot} label="Recommendation engine" value={recs?.engine || "--"} detail={`${recs?.recommendations?.length || 0} actions / ${status?.llm_configured ? "LLM ready" : "rules only"}`} accent />
        <Metric icon={Send} label="Campaign messages" value={analytics?.email?.campaign_messages ?? "--"} detail={`${analytics?.email?.sent || 0} sent / ${analytics?.email?.failed || 0} failed`} />
        <Metric icon={Mic} label="Voice analysed" value={analytics?.voice?.transcripts ?? "--"} detail={`${Object.keys(analytics?.voice?.sentiment || {}).length || 0} sentiment labels`} />
        <Metric icon={BarChart3} label="Instagram" value={instagram.configured ? "Configured" : "Setup needed"} detail={instagram.profile?.username || "add Instagram credentials"} />
      </div>
      <div className="two-column">
        <section className="panel">
          <div className="panel-heading"><div><div className="section-kicker">NEXT BEST ACTIONS</div><h3>Recommendations</h3></div><Sparkles size={19} className="muted" /></div>
          <div className="rec-list">
            {(recs?.recommendations || []).map((rec, index) => <div className={`rec-item rec-${rec.priority}`} key={index}><span className="rec-badge">{rec.priority}</span><div><b>{rec.area}</b><p>{rec.text}</p><small className="muted">{rec.action}</small></div></div>)}
            {!(recs?.recommendations || []).length && <div className="empty-state"><Check size={22} /><p>No actions right now.</p></div>}
          </div>
        </section>
        <section className="panel">
          <div className="panel-heading"><div><div className="section-kicker">SOCIAL CHANNELS</div><h3>Live configuration status</h3></div><Link2 size={19} className="muted" /></div>
          <Service status={!!instagram.configured} icon={Video} label="Instagram" value={instagram.configured ? (instagram.profile?.username || "configured") : "credentials required"} />
          <Service status={!!social?.youtube?.configured} icon={Video} label="YouTube" value={social?.youtube?.configured ? "snapshot cached" : "not synced"} />
          <Service status={!!social?.linkedin?.configured} icon={BriefcaseBusiness} label="LinkedIn" value={social?.linkedin?.configured ? `${social.linkedin.profiles} profiles` : "token required"} />
          <Service status={!!social?.reddit?.configured} icon={Search} label="Reddit" value={social?.reddit?.configured ? `${social.reddit.posts} posts` : "credentials required"} />
          <Service status={!!social?.whatsapp?.configured} icon={Send} label="WhatsApp" value={social?.whatsapp?.configured ? `${social.whatsapp.messages} messages` : "not configured"} />
          <div className="button-row" style={{ marginTop: 14 }}><button className="primary-button" onClick={syncInstagram} disabled={busy}>{busy ? "Syncing..." : "Sync Instagram"}</button></div>
          <small className="muted">{instagram.configured ? `Last sync: ${instagram.last_sync || "never"}` : "Set INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_ACCOUNT_ID, then sync."}</small>
          {(instagram.media || []).slice(0, 4).map((item) => <div className="connection-row" key={item.id}><span className="mail-icon"><Video size={16} /></span><span><b>{item.caption ? item.caption.slice(0, 60) : item.media_type}</b><small>{item.like_count || 0} likes / {item.comments_count || 0} comments</small></span><a className="text-button" href={item.permalink} target="_blank" rel="noreferrer">Open</a></div>)}
        </section>
      </div>
      <div className="two-column" style={{ marginTop: 14 }}>
        <section className="panel">
          <div className="panel-heading"><div><div className="section-kicker">COMMUNICATION MIX</div><h3>Channel activity</h3></div><Activity size={19} className="muted" /></div>
          <div className="mini-stats">
            <span><b>{analytics?.whatsapp?.messages || 0}</b> WhatsApp</span><span><b>{analytics?.team?.messages || 0}</b> team messages</span>
            <span><b>{analytics?.feedback?.responses || 0}</b> feedback</span><span><b>{analytics?.feedback?.average_rating || 0}</b> avg rating</span>
          </div>
          <div className="table-wrap"><table><thead><tr><th>Email status</th><th>Count</th></tr></thead><tbody>{Object.entries(analytics?.email?.by_status || {}).map(([key, value]) => <tr key={key}><td>{key}</td><td>{value}</td></tr>)}{!Object.keys(analytics?.email?.by_status || {}).length && <tr><td colSpan={2}><small className="muted">No campaign messages yet.</small></td></tr>}</tbody></table></div>
        </section>
        <section className="panel">
          <div className="panel-heading"><div><div className="section-kicker">VOICE / TONE</div><h3>Customer sentiment</h3></div><Mic size={19} className="muted" /></div>
          <div className="mini-stats">{Object.entries(analytics?.voice?.sentiment || {}).map(([key, value]) => <span key={key}><b>{value}</b> {key}</span>)}{!Object.keys(analytics?.voice?.sentiment || {}).length && <span>No analysed calls</span>}</div>
          <div className="mini-stats" style={{ marginTop: 10 }}>{Object.entries(analytics?.voice?.intent || {}).map(([key, value]) => <span key={key}><b>{value}</b> intent: {key}</span>)}</div>
          <div className="button-row" style={{ marginTop: 14 }}><button className="secondary-button" onClick={load}><RefreshCw size={15} /> Refresh analytics</button></div>
        </section>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- Users and access
export function Access({ onNotice, user }) {
  const [users, setUsers] = useState([]);
  const [activity, setActivity] = useState(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ email: "", name: "", password: "", role: "sales" });
  const [busy, setBusy] = useState(false);
  const load = async () => {
    try {
      const [nextUsers, nextActivity] = await Promise.all([request("/users/detail"), request("/users/activity")]);
      setUsers(nextUsers); setActivity(nextActivity); setError("");
    } catch (err) { setError(err.message); }
  };
  useEffect(() => { load(); }, []);
  const create = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      await request("/users", { method: "POST", body: JSON.stringify(form) });
      setForm({ email: "", name: "", password: "", role: "sales" });
      onNotice({ type: "success", text: "User created." });
      await load();
    } catch (err) { onNotice({ type: "error", text: err.message }); }
    finally { setBusy(false); }
  };
  const update = async (id, patch) => {
    try {
      await request(`/users/${id}`, { method: "PATCH", body: JSON.stringify(patch) });
      onNotice({ type: "success", text: "User updated." });
      await load();
    } catch (err) { onNotice({ type: "error", text: err.message }); }
  };
  return (
    <div className="content dash">
      <div className="page-heading">
        <div><div className="section-kicker">SECURITY / ROLES</div><h2>Users &amp; access</h2>
          <p className="muted">Admin-only user management. Each account keeps its own contacts, voice, visits and campaigns.</p></div>
        <button className="secondary-button" onClick={load}><RefreshCw size={15} /> Refresh</button>
      </div>
      {error && <div className="config-warning"><ShieldCheck size={18} /><span>{error}</span></div>}
      {!error && <>
        <div className="panel form-panel">
          <div className="panel-heading"><div><div className="section-kicker">NEW ACCOUNT</div><h3>Create a user</h3></div><Users size={19} className="muted" /></div>
          <form onSubmit={create}><div className="form-grid">
            <input required placeholder="Email or username *" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} />
            <input placeholder="Full name" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
            <input required type="password" minLength={8} placeholder="Temporary password *" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} />
            <select value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })}><option value="sales">Sales</option><option value="field">Field executive</option><option value="admin">Admin</option></select>
          </div><button className="primary-button" disabled={busy}><Plus size={15} /> Create user</button></form>
        </div>
        <section className="panel">
          <div className="panel-heading"><div><div className="section-kicker">WORKSPACE ACCOUNTS</div><h3>{users.length} users</h3></div><ShieldCheck size={19} className="muted" /></div>
          <div className="table-wrap"><table><thead><tr><th>User</th><th>Role</th><th>Status</th><th>Contacts</th><th>Visits</th><th>Voice</th><th>Last login</th><th>Actions</th></tr></thead><tbody>
            {users.map((row) => <tr key={row.id}><td className="table-person"><b>{row.name || row.email}</b><small>{row.email}</small></td><td><select value={row.role} onChange={(event) => update(row.id, { role: event.target.value })}><option value="admin">admin</option><option value="sales">sales</option><option value="field">field</option></select></td><td><span className={`status-pill ${row.is_active ? "approved" : "rejected"}`}>{row.is_active ? "active" : "inactive"}</span>{row.admin_by_email && <small className="muted"> admin email</small>}</td><td>{activity?.users?.find((item) => item.id === row.id)?.contacts ?? 0}</td><td>{activity?.users?.find((item) => item.id === row.id)?.visits ?? 0}</td><td>{activity?.users?.find((item) => item.id === row.id)?.voice ?? 0}</td><td>{row.last_login_at ? String(row.last_login_at).slice(0, 16) : "never"}</td><td>{row.id !== user?.id && <button className="text-button" onClick={() => update(row.id, { is_active: !row.is_active })}>{row.is_active ? "Deactivate" : "Activate"}</button>}</td></tr>)}
            {!users.length && <tr><td colSpan={8}><div className="empty-state"><Users size={22} /><p>No users found.</p></div></td></tr>}
          </tbody></table></div>
        </section>
      </>}
    </div>
  );
}
