import React, { useEffect, useState } from "react";
import {
  Activity, BarChart3, Bot, BriefcaseBusiness, Building2, CalendarDays, Calculator, Check, Clock,
  Copy, Database, FileDown, Link2, Mail, MapPin, Mic, Package, Plus, RefreshCw, Save, Search, Send, ShieldCheck,
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

// ---------------------------------------------------------------- Tally sales
export function TallySalesPanel({ onNotice, compact = false }) {
  const [status, setStatus] = useState(null);
  const [sales, setSales] = useState([]);
  const [period, setPeriod] = useState("");
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);

  const load = async (nextPeriod = period) => {
    const query = nextPeriod ? `?period=${encodeURIComponent(nextPeriod)}` : "";
    const salesQuery = `?limit=${compact ? 8 : 20}${nextPeriod ? `&period=${encodeURIComponent(nextPeriod)}` : ""}`;
    const [nextStatus, nextSales] = await Promise.all([
      request(`/tally/status${query}`), request(`/tally/sales${salesQuery}`),
    ]);
    setStatus(nextStatus);
    setSales(nextSales);
    setPeriod((current) => current || nextStatus.period || "");
  };

  useEffect(() => {
    load().catch((error) => onNotice({ type: "error", text: error.message }));
  }, []);

  const changePeriod = async (value) => {
    setPeriod(value);
    try { await load(value); }
    catch (error) { onNotice({ type: "error", text: error.message }); }
  };

  const sync = async () => {
    setBusy(true);
    try {
      const result = await request("/tally/sync", { method: "POST" });
      onNotice({
        type: result.ok ? "success" : "error",
        text: `Tally sync: ${result.created} new, ${result.updated} updated, ${result.deleted} removed${result.errors?.length ? `; ${result.errors.length} file error(s)` : ""}.`,
      });
      await load(period);
    } catch (error) { onNotice({ type: "error", text: error.message }); }
    finally { setBusy(false); }
  };

  const upload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const body = new FormData();
      body.append("file", file);
      const result = await request("/tally/upload", { method: "POST", body });
      const nextPeriod = result.periods?.[result.periods.length - 1] || "";
      onNotice({
        type: result.ok ? "success" : "error",
        text: `${result.uploaded} synced: ${result.created} new, ${result.updated} updated${result.gcs_uploaded ? " (GCS copy saved)" : " (local copy saved)"}.`,
      });
      if (nextPeriod) setPeriod(nextPeriod);
      await load(nextPeriod);
    } catch (error) { onNotice({ type: "error", text: error.message }); }
    finally { setUploading(false); event.target.value = ""; }
  };

  const stats = status || {};
  const buyers = (stats.top_buyers || []).slice(0, compact ? 4 : 8);
  const maxValue = Math.max(...buyers.map((row) => row.value || 0), 1);
  return (
    <section className={`panel tally-panel ${compact ? "tally-compact" : ""}`}>
      <div className="panel-heading">
        <div>
          <div className="section-kicker">TALLY SALES / KALIKA_SALES2026</div>
          <h3>{compact ? "Latest buyer sales" : "Tally sales register"}</h3>
          <p className="muted" style={{ margin: "4px 0 0" }}>
            {stats.data_available ? `${stats.period || "latest"} / ${fmtNum(stats.invoices)} invoices / ${fmtNum(stats.customers)} buyers` : "No Sales Register synced yet."}
          </p>
        </div>
        <div className="button-row">
          {stats.periods?.length > 0 && (
            <select value={period || stats.period || ""} onChange={(event) => changePeriod(event.target.value)}>
              {stats.periods.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          )}
          {!compact && stats.is_admin && (
            <>
              <button className="secondary-button" onClick={sync} disabled={busy}>
                <RefreshCw size={15} className={busy ? "spin" : ""} /> {busy ? "Syncing..." : "Sync GCS"}
              </button>
              <label className="secondary-button" style={{ cursor: "pointer" }}>
                <UploadCloud size={15} /> {uploading ? "Uploading..." : "Upload XLS"}
                <input type="file" accept=".xls,.xlsx" onChange={upload} disabled={uploading} style={{ display: "none" }} />
              </label>
            </>
          )}
        </div>
      </div>
      {!stats.data_available && (
        <div className="empty-state">
          <Database size={22} />
          <p>No Tally sales data.</p>
          <small>{stats.is_admin ? `Sync gs://${stats.bucket}/${stats.prefix} or upload a Sales Register.` : "Ask an admin to sync the Tally Sales Register."}</small>
        </div>
      )}
      {stats.data_available && (
        <>
          <div className="mini-stats" style={{ marginBottom: 12 }}>
            <span><b>{fmtMoney(stats.total_value)}</b> sales value</span>
            <span><b>{fmtNum(stats.invoices)}</b> invoices</span>
            <span><b>{fmtNum(stats.customers)}</b> buyers</span>
            <span><b>{fmtNum(stats.total_quantity)}</b> quantity</span>
            <span><b>{stats.last_sync?.status || "not synced"}</b> last sync</span>
          </div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Buyer</th><th>Invoices</th><th>Value</th><th>Share</th></tr></thead>
              <tbody>
                {buyers.map((row) => (
                  <tr key={row.buyer}>
                    <td className="table-person"><b>{row.buyer}</b><div className="bar-track"><div className="bar-fill" style={{ width: `${Math.min(100, (row.value / maxValue) * 100)}%` }} /></div></td>
                    <td>{fmtNum(row.invoices)}</td>
                    <td>{fmtMoney(row.value)}</td>
                    <td>{Math.round((row.value / (stats.total_value || 1)) * 100)}%</td>
                  </tr>
                ))}
                {!buyers.length && <tr><td colSpan={4}><small className="muted">No buyer rows for this period.</small></td></tr>}
              </tbody>
            </table>
          </div>
          {!compact && sales.length > 0 && (
            <>
              <div className="section-kicker" style={{ marginTop: 14 }}>LATEST INVOICE LINES</div>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Date</th><th>Buyer</th><th>Item</th><th>Qty</th><th>Value</th></tr></thead>
                  <tbody>
                    {sales.map((row) => (
                      <tr key={row.id}>
                        <td><small>{row.sale_date}</small></td>
                        <td className="table-person"><b>{row.buyer}</b><small>{row.voucher_no}</small></td>
                        <td><small>{row.item_name || "Sales line"}</small></td>
                        <td>{fmtNum(row.quantity)}</td>
                        <td>{fmtMoney(row.value)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </>
      )}
    </section>
  );
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
      <TallySalesPanel onNotice={onNotice} />
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
export function CompanyVisits({ onNotice, user }) {
  const today = new Date().toISOString().slice(0, 10);
  const [visits, setVisits] = useState([]);
  const [stats, setStats] = useState(null);
  const emptyVisit = { company: "", contact_name: "", contact_phone: "", visit_date: today, outcome: "", follow_up_date: "", notes: "", next_action: "", meet_person: "", meet_home_location: "", previous_discussion: "", mail_chat_details: "", map_location: "" };
  const [form, setForm] = useState(emptyVisit);
  const [uploading, setUploading] = useState(0);
  const userName = user?.name || user?.email?.split("@")[0] || "there";
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
      setForm({ ...emptyVisit, visit_date: today });
      onNotice({ type: "success", text: "Visit saved." });
      await load();
    } catch (error) { onNotice({ type: "error", text: error.message }); }
  };
  const syncSamples = async () => {
    try {
      const result = await request("/visits/samples", { method: "POST" });
      onNotice({ type: "success", text: `Field samples synced: ${result.created} new, ${result.existing} already present.` });
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
  const followUpText = (visit) => {
    const action = visit.next_action || visit.purpose || "follow-up";
    return `Follow-up: ${visit.company} (${visit.meet_person || visit.contact_name || "contact"}) on ${visit.follow_up_date || "next visit"} - ${action}. Notes: ${visit.notes || "-"}`.slice(0, 900);
  };
  const copyFollowUp = async (visit) => {
    try {
      await navigator.clipboard.writeText(followUpText(visit));
      onNotice({ type: "success", text: `Follow-up for ${visit.company} copied.` });
    } catch { onNotice({ type: "error", text: "Clipboard unavailable - select and copy manually." }); }
  };
  const whatsappLink = (visit) => {
    const digits = String(visit.contact_phone || "").replace(/\D/g, "");
    if (!digits) return "";
    const phone = digits.length === 10 ? `91${digits}` : digits;
    return `https://wa.me/${phone}?text=${encodeURIComponent(followUpText(visit))}`;
  };
  return (
    <div className="content dash">
      <div className="greeting-banner">
        <span className="greeting-emoji">👋</span>
        <div>
          <h3>Hola!! {userName} 🎉</h3>
          <p className="muted">Welcome to your field dashboard. Keep up the great work! ✨</p>
        </div>
      </div>
      <div className="page-heading">
        <div><div className="section-kicker">FIELD / COMPANY HISTORY</div><h2>Company visits</h2>
          <p className="muted">Log visits, outcomes, follow-ups and attach photo/video evidence in GCS.</p></div>
        <div className="button-row">
          <button className="secondary-button" onClick={load}><RefreshCw size={15} /> Refresh</button>
          <button className="secondary-button" onClick={syncSamples}><Users size={15} /> Sync samples</button>
        </div>
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
            <input placeholder="Person met" value={form.meet_person} onChange={(event) => setForm({ ...form, meet_person: event.target.value })} />
            <input placeholder="Meeting home location (plant/office)" value={form.meet_home_location} onChange={(event) => setForm({ ...form, meet_home_location: event.target.value })} />
            <input placeholder="Map link (Google Maps URL)" value={form.map_location} onChange={(event) => setForm({ ...form, map_location: event.target.value })} />
          </div>
          <textarea className="voice-text" rows={2} placeholder="Previous discussion point" value={form.previous_discussion} onChange={(event) => setForm({ ...form, previous_discussion: event.target.value })} />
          <textarea className="voice-text" rows={2} placeholder="Mail / chat details (subject, date, sender)" value={form.mail_chat_details} onChange={(event) => setForm({ ...form, mail_chat_details: event.target.value })} />
          <textarea className="voice-text" rows={3} placeholder="Visit notes" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} />
          <input placeholder="Next action" value={form.next_action} onChange={(event) => setForm({ ...form, next_action: event.target.value })} />
          <button className="primary-button"><Plus size={15} /> Save visit</button></form>
        </section>
        <section className="panel">
          <div className="panel-heading"><div><div className="section-kicker">VISIT HISTORY</div><h3>Recent meetings</h3></div><Building2 size={19} className="muted" /></div>
          <div className="table-wrap"><table><thead><tr><th>Company / person</th><th>Date</th><th>Where &amp; previous point</th><th>Outcome</th><th>Follow-up</th><th>Media</th></tr></thead><tbody>
            {visits.map((visit) => <tr key={visit.id}><td className="table-person"><b>{visit.company}</b><small>{visit.contact_name || visit.notes?.slice(0, 50)}</small></td><td>{visit.visit_date}</td><td><small><b>{visit.meet_person || visit.meet_home_location || "not captured"}</b>{visit.previous_discussion ? ` ? ${visit.previous_discussion.slice(0, 90)}` : ""}</small>{visit.map_location && <a className="text-button" href={visit.map_location} target="_blank" rel="noreferrer">Map</a>}</td><td>{visit.outcome || visit.status}</td><td><div className="followup-cell"><span>{visit.follow_up_date || "-"}</span><div className="button-row"><button type="button" className="text-button" onClick={() => copyFollowUp(visit)}><Copy size={12} /> Copy</button>{whatsappLink(visit) && <a className="text-button" href={whatsappLink(visit)} target="_blank" rel="noreferrer"><Send size={12} /> WhatsApp</a>}</div></div></td><td><label className="text-button">{uploading === visit.id ? "Uploading..." : `${(visit.media || []).length} file(s) +`}<input type="file" accept="image/*,video/*" hidden onChange={(event) => upload(visit, event.target.files?.[0])} /></label></td></tr>)}
            {!visits.length && <tr><td colSpan={6}><div className="empty-state"><MapPin size={22} /><p>No visits yet.</p><small>Log the first field meeting.</small></div></td></tr>}
          </tbody></table></div>
        </section>
      </div>
    </div>
  );
}


// ---------------------------------------------------------------- Instore mails
export function InstoreMails({ onNotice }) {
  const [summary, setSummary] = useState(null);
  const [mails, setMails] = useState([]);
  const [promptInfo, setPromptInfo] = useState(null);
  const [expertise, setExpertise] = useState("sales_strategist");
  const [model, setModel] = useState("");
  const [question, setQuestion] = useState("What should the field team do next based on the latest instore mails?");
  const [reply, setReply] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      const [nextSummary, nextMails, nextPrompts] = await Promise.all([
        request("/instore/summary"), request("/instore/mails?limit=12"), request("/instore/prompts"),
      ]);
      setSummary(nextSummary); setMails(nextMails.mails || []); setPromptInfo(nextPrompts);
      setModel((current) => current || nextPrompts.models?.default || "");
    } catch (error) { onNotice({ type: "error", text: error.message }); }
  };
  useEffect(() => { load(); }, []);

  const sync = async () => {
    setBusy(true);
    try {
      const result = await request("/instore/sync", { method: "POST", body: JSON.stringify({ source: "auto", include_body: true, include_dump: true }) });
      onNotice({ type: result.ok ? "success" : "error", text: `Instore sync: ${result.insights?.total || 0} mails, ${result.missing_links?.count || 0} missing links, ${result.stored?.gcs_uploaded ? "GCS copy saved" : "local copy saved"}.` });
      await load();
    } catch (error) { onNotice({ type: "error", text: error.message }); }
    finally { setBusy(false); }
  };

  const ask = async (event) => {
    event.preventDefault();
    if (!question.trim()) return;
    setBusy(true); setReply(null);
    try {
      const result = await request("/instore/ask", { method: "POST", body: JSON.stringify({ question: question.trim(), expertise, model }) });
      setReply(result);
    } catch (error) { onNotice({ type: "error", text: error.message }); }
    finally { setBusy(false); }
  };

  const insights = summary?.insights || {};
  const missing = summary?.missing_links || {};
  const models = promptInfo?.models || {};
  return (
    <div className="content dash">
      <div className="page-heading">
        <div><div className="section-kicker">MAIL DESK / GCS SNAPSHOT</div><h2>Mail desk</h2>
          <p className="muted">Client mails and WhatsApp order updates with working names, outcomes and contact links - ask Gemma/flash for the next field action.</p></div>
        <div className="button-row">
          <button className="secondary-button" onClick={load} disabled={busy}><RefreshCw size={15} /> Refresh</button>
          <button className="primary-button" onClick={sync} disabled={busy}><Mail size={15} /> {busy ? "Working..." : "Sync mails"}</button>
        </div>
      </div>
      <div className="metric-grid">
        <Metric icon={Mail} label="Mails" value={insights.total ?? "--"} detail={`${insights.linked || 0} linked / ${insights.unlinked || 0} missing`} accent />
        <Metric icon={Link2} label="Missing links" value={missing.count ?? "--"} detail={Object.keys(missing.domains || {}).slice(0, 3).join(", ") || "no sender gaps"} />
        <Metric icon={UploadCloud} label="Attachments" value={insights.attachments ?? "--"} detail={Object.entries(insights.attachment_purposes || {}).slice(0, 2).map(([k, v]) => `${v} ${k}`).join(" / ") || "none classified"} />
        <Metric icon={Sparkles} label="Link accuracy" value={`${insights.accuracy_pct ?? "--"}%`} detail={`forecast ${insights.forecast_next_month_mails ?? 0} mails next month`} />
      </div>
      {!summary?.data_available && (
        <div className="empty-state"><Mail size={22} /><p>No mail snapshot yet.</p><small>Sync a connected mailbox or the interaction dump to build the first snapshot.</small></div>
      )}
      <div className="two-column">
        <section className="panel">
          <div className="panel-heading"><div><div className="section-kicker">LATEST MAIL</div><h3>Sender ? contact links</h3></div><Mail size={19} className="muted" /></div>
          <div className="mini-stats" style={{ marginBottom: 12 }}>
            {Object.entries(insights.by_intent || {}).slice(0, 6).map(([intent, count]) => <span key={intent}><b>{count}</b> {intent}</span>)}
          </div>
          <div className="table-wrap"><table><thead><tr><th>Mail / client</th><th>Date</th><th>Intent</th><th>Outcome</th><th>Link</th></tr></thead><tbody>
            {mails.map((mail) => <tr key={mail.id}>
              <td className="table-person mail-cell">
                <details className="mail-expand">
                  <summary><b>{mail.working_title || mail.subject || "(no subject)"}</b><small>{mail.client_name || mail.from_email || mail.to || "unknown sender"}{mail.owner_email ? ` ? owner ${mail.owner_email}` : ""}</small></summary>
                  <div className="mail-detail">
                    {mail.context && <small className="muted">Context: {mail.context}</small>}
                    {mail.snippet && <p>{mail.snippet.slice(0, 220)}</p>}
                    {(mail.entities || []).length > 0 && <div className="mini-stats">{(mail.entities || []).slice(0, 6).map((entity) => <span key={entity} className="status-chip">{entity}</span>)}</div>}
                    {(mail.attachments || []).length > 0 && <small className="muted">Attachments: {mail.attachments.map((a) => a.name).join(", ")}</small>}
                  </div>
                </details>
              </td>
              <td>{String(mail.date || "").slice(0, 16)}</td>
              <td>{mail.intent}</td>
              <td><span className="status-chip">{mail.outcome || "update"}</span></td>
              <td><span className={`status-pill ${mail.contact_id ? "approved" : "rejected"}`}>{mail.contact_id ? "linked" : "missing"}</span></td>
            </tr>)}
            {!mails.length && <tr><td colSpan={5}><small className="muted">No mails in the current snapshot.</small></td></tr>}
          </tbody></table></div>
          {(missing.samples || []).length > 0 && <div className="status-breakdown" style={{ marginTop: 12 }}>
            {(missing.samples || []).slice(0, 6).map((item) => <span className="status-chip warn" key={`${item.from_email}-${item.subject}`}><b>{item.from_email || item.domain}</b> {item.subject?.slice(0, 40)}</span>)}
          </div>}
        </section>
        <section className="panel">
          <div className="panel-heading"><div><div className="section-kicker">DYNAMIC PROMPT / HUMAN EXPERTISE</div><h3>Ask the mail desk</h3></div><Bot size={19} className="muted" /></div>
          <form onSubmit={ask}>
            <div className="form-grid">
              <select value={expertise} onChange={(event) => setExpertise(event.target.value)}>
                {(promptInfo?.expertise || []).map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
              </select>
              <select value={model} onChange={(event) => setModel(event.target.value)}>
                <option value={models.default || ""}>{models.default || "Gemma"} (default)</option>
                {models.flash && <option value={models.flash}>{models.flash} (flash fallback)</option>}
                {models.local && <option value={models.local}>{models.local} (local SLM)</option>}
              </select>
            </div>
            <textarea className="voice-text" rows={4} value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask about priority accounts, missing links, or the next field action..." />
            <div className="button-row"><button className="primary-button" disabled={busy}><Send size={15} /> {busy ? "Thinking..." : "Ask"}</button><span className="muted">Gemma 4 ? local SLM ? flash ? echo</span></div>
          </form>
          {reply && <div className="review-card"><div className="chat-head"><b>{reply.expertise}</b><small>{reply.model} ? {reply.provider}{reply.fallback_used ? " ? fallback" : ""}</small></div><p style={{ whiteSpace: "pre-wrap" }}>{reply.reply}</p>{reply.notice && <small className="muted">{reply.notice}</small>}</div>}
          <div className="mini-stats" style={{ marginTop: 14 }}>
            <span><b>{summary?.graph_stats?.nodes || 0}</b> graph nodes</span>
            <span><b>{summary?.graph_stats?.edges || 0}</b> edges</span>
            <span><b>{summary?.source?.kind || "none"}</b> source</span>
          </div>
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

// ---------------------------------------------------------------- Marketing companies
export function MarketingCompanies({ onNotice }) {
  const [rows, setRows] = useState([]);
  const [stats, setStats] = useState(null);
  const [query, setQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [editing, setEditing] = useState({});
  const [busy, setBusy] = useState(false);

  const load = async () => {
    const params = new URLSearchParams();
    if (query) params.set("q", query);
    if (categoryFilter) params.set("category", categoryFilter);
    if (statusFilter) params.set("call_status", statusFilter);
    try {
      const [nextRows, nextStats] = await Promise.all([
        request(`/marketing-companies?${params.toString()}`),
        request("/marketing-companies/stats"),
      ]);
      setRows(nextRows);
      setStats(nextStats);
    } catch (error) {
      onNotice({ type: "error", text: error.message });
    }
  };

  useEffect(() => { load(); }, []);

  const debounced = query;
  useEffect(() => {
    const id = setTimeout(() => load(), 250);
    return () => clearTimeout(id);
  }, [debounced, categoryFilter, statusFilter]);

  const updateField = async (id, field, value) => {
    try {
      await request(`/marketing-companies/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ [field]: value }),
      });
      setRows((previous) => previous.map((row) => (row.id === id ? { ...row, [field]: value } : row)));
      setEditing((previous) => ({ ...previous, [id]: { ...(previous[id] || {}), [field]: undefined } }));
    } catch (error) {
      onNotice({ type: "error", text: error.message });
    }
  };

  const runImport = async () => {
    setBusy(true);
    try {
      const result = await request("/marketing-companies/import", { method: "POST" });
      onNotice({
        type: "success",
        text: `Marketing import: ${result.imported} added, ${result.updated} updated, ${result.skipped} unchanged (${result.source}).`,
      });
      await load();
    } catch (error) {
      onNotice({ type: "error", text: error.message });
    } finally {
      setBusy(false);
    }
  };

  const categories = stats ? Object.keys(stats.by_category || {}).sort() : [];
  const statuses = stats ? Object.keys(stats.by_call_status || {}).sort() : [];

  return (
    <div className="content">
      <div className="page-heading">
        <div>
          <div className="section-kicker">KALIKA MARKETING LIST</div>
          <h2>Marketing companies</h2>
          <p className="muted">A clean view of the marketing workbook. Edit requirements directly on each row.</p>
        </div>
        <div className="button-row">
          <button className="secondary-button" onClick={load}><RefreshCw size={16} /> Refresh</button>
          <button className="primary-button" onClick={runImport} disabled={busy}>
            <Database size={16} />{busy ? "Importing..." : "Import marketing workbook"}
          </button>
        </div>
      </div>
      {stats && (
        <div className="mini-stats">
          <span><b>{fmtNum(stats.total)}</b> companies</span>
          <span><b>{fmtNum(stats.with_phone)}</b> with phone</span>
          <span><b>{fmtNum(stats.with_email)}</b> with email</span>
          <span><b>{fmtNum(stats.with_requirements)}</b> with requirements</span>
        </div>
      )}
      <section className="panel table-panel">
        <div className="table-toolbar">
          <div className="search-field"><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search company, contact, email or requirements" /></div>
          <select value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)}>
            <option value="">All categories</option>
            {categories.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="">All call statuses</option>
            {statuses.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <span className="muted">{rows.length} shown</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Company</th>
                <th>Contact</th>
                <th>Category</th>
                <th>Call status</th>
                <th>Requirements</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const editingRequirements = (editing[row.id]?.requirements ?? row.requirements) || "";
                return (
                  <tr key={row.id}>
                    <td><b>{row.company}</b></td>
                    <td className="table-person">
                      <span>{row.contact_name || "-"}</span>
                      <small>{row.phone || row.email || ""}</small>
                    </td>
                    <td>{row.category || "-"}</td>
                    <td>{row.call_status || "-"}</td>
                    <td>
                      <textarea
                        rows={2}
                        value={editingRequirements}
                        onChange={(event) => setEditing((previous) => ({
                          ...previous,
                          [row.id]: { ...(previous[row.id] || {}), requirements: event.target.value },
                        }))}
                        onBlur={(event) => {
                          if (event.target.value !== row.requirements) updateField(row.id, "requirements", event.target.value);
                        }}
                      />
                    </td>
                  </tr>
                );
              })}
              {!rows.length && <tr><td colSpan={5}><div className="empty-state"><BriefcaseBusiness size={22} /><p>No marketing companies yet.</p><small>Import the Kalika marketing workbook to populate this view.</small></div></td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
