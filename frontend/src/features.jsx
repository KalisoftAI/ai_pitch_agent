import React, { useEffect, useState } from "react";
import {
  Activity, BarChart3, Bot, BriefcaseBusiness, Building2, CalendarDays, Calculator, Check, Clock,
  Copy, Database, Edit2, ExternalLink, Eye, Film, FileDown, FileText, Link2, Mail, MapPin, MessageCircle, MessageSquarePlus, Mic, Package, PhoneCall, Plus, RefreshCw, Save, Search, Send, ShieldCheck,
  Sparkles, Target, Trash2, TrendingUp, Truck, UploadCloud, Users, Video, X,
} from "lucide-react";
import { CampaignManager } from "./features/CampaignManager";

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
          <div className="tally-stats">
            <div><small>Sales value</small><b>{fmtMoney(stats.total_value)}</b></div>
            <div><small>Invoices</small><b>{fmtNum(stats.invoices)}</b></div>
            <div><small>Buyers</small><b>{fmtNum(stats.customers)}</b></div>
            <details className="tally-extra"><summary>More register details</summary><div className="tally-extra-body"><span>{fmtNum(stats.total_quantity)} total quantity</span><span>{stats.last_sync?.status || "Not synced"}{stats.last_sync?.finished_at ? ` Â· ${String(stats.last_sync.finished_at).slice(0, 16)}` : ""}</span></div></details>
          </div>
          <div className="table-wrap tally-desktop-table">
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
          <div className="tally-mobile-list">
            {buyers.map((row) => <details className="tally-mobile-row" key={row.buyer}>
              <summary><span><b>{row.buyer}</b><small>{fmtNum(row.invoices)} invoices</small></span><strong>{fmtMoney(row.value)}</strong></summary>
              <div className="tally-extra-body"><span>{Math.round((row.value / (stats.total_value || 1)) * 100)}% of sales</span></div>
            </details>)}
            {!buyers.length && <p className="muted">No buyer rows for this period.</p>}
          </div>
          {!compact && sales.length > 0 && (
            <>
              <details className="invoice-details">
                <summary>Latest invoice lines <span>{sales.length} shown</span></summary>
              <div className="table-wrap tally-desktop-table">
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
              <div className="tally-mobile-list">
                {sales.map((row) => <details className="tally-mobile-row" key={row.id}>
                  <summary><span><b>{row.buyer}</b><small>{row.sale_date} Â· {row.voucher_no}</small></span><strong>{fmtMoney(row.value)}</strong></summary>
                  <div className="tally-extra-body"><span>{row.item_name || "Sales line"}</span><span>{fmtNum(row.quantity)} quantity</span></div>
                </details>)}
              </div>
              </details>
            </>
          )}
        </>
      )}
    </section>
  );
}

// ---------------------------------------------------------------- Instore summary card
export function InstoreSummaryCard({ onNotice }) {
  const [summary, setSummary] = useState(null);
  const [mails, setMails] = useState([]);
  useEffect(() => {
    Promise.all([request("/instore/summary"), request("/instore/mails?limit=3")])
      .then(([nextSummary, nextMails]) => { setSummary(nextSummary); setMails(nextMails.mails || []); })
      .catch((error) => onNotice({ type: "error", text: error.message }));
  }, []);
  const insights = summary?.insights || {};
  const missing = summary?.missing_links || {};
  const intents = Object.entries(insights.by_intent || {}).sort((a, b) => b[1] - a[1]).slice(0, 4);
  return (
    <section className="panel instore-summary-card">
      <div className="panel-heading">
        <div><div className="section-kicker">INSTORE / MAIL DESK</div><h3>Instore mails</h3></div>
        <Mail size={19} className="muted" />
      </div>
      {!summary?.data_available && <div className="empty-state compact"><Mail size={22} /><p>No mail snapshot yet.</p><small>Sync the mail desk to link senders to contacts.</small></div>}
      {summary?.data_available && (
        <>
          <div className="mini-stats">
            <span><b>{fmtNum(insights.total)}</b> mails</span>
            <span><b>{fmtNum(insights.linked)}</b> linked</span>
            <span><b>{fmtNum(missing.count || 0)}</b> missing</span>
            <span><b>{fmtNum(insights.high_priority)}</b> high priority</span>
          </div>
          <div className="mini-stats">
            {intents.map(([intent, count]) => <span key={intent}><b>{fmtNum(count)}</b> {intent}</span>)}
          </div>
          {mails.map((mail) => (
            <div className="connection-row" key={mail.id}>
              <span className="mail-icon"><Mail size={16} /></span>
              <span><b>{mail.working_title || mail.subject || "(no subject)"}</b><small>{mail.client_name || mail.from_email || "unknown sender"} Â· {mail.intent || "general"}</small></span>
              <span className={`status-pill ${mail.contact_id ? "approved" : "rejected"}`}>{mail.contact_id ? "linked" : "missing"}</span>
            </div>
          ))}
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
        <div><div className="section-kicker">DELIVERY / PLANT VIEW</div><h2>Sales analytics &amp; BI</h2>
          <p className="muted">Plant-wise dispatch completion from the latest synced ERP report.</p></div>
        <div className="button-row">
          <button className="secondary-button" onClick={load} disabled={busy}><RefreshCw size={15} className={busy ? "spin" : ""} /> Refresh</button>
          <button className="secondary-button" onClick={() => download("companies", "xlsx")}><FileDown size={15} /> XLSX</button>
          <button className="secondary-button" onClick={() => download("companies", "pdf")}><FileDown size={15} /> PDF</button>
        </div>
      </div>

      {!overview.data_available && <div className="empty-state"><Database size={22} /><p>No ERP report synced yet.</p><small>Run ERP sync from the ERP tab to populate real analytics.</small></div>}

      <section className="panel delivery-hero">
        <div className="panel-heading">
          <div><div className="section-kicker">DELIVERY / PLANT VIEW</div><h3>Dispatch status</h3></div>
          <Truck size={19} className="muted" />
        </div>
        <div className="delivery-hero-grid">
          <div className="delivery-hero-main">
            <b>{totals.completion_pct || 0}%</b>
            <span>Dispatch / {fmtNum(totals.dispatched_qty)} kg</span>
            <small>{fmtNum(totals.scheduled_qty)} kg scheduled Â· {fmtNum(totals.pending_dispatch)} pending lines</small>
          </div>
          <div className="delivery-hero-plants">
            {(delivery.plants || []).map((plant) => (
              <span key={plant.plant}><b>{plant.completion_pct}%</b>{plant.plant} / {fmtNum(plant.dispatched_qty)} kg</span>
            ))}
            {!(delivery.plants || []).length && <span className="muted">No plant totals in the latest report.</span>}
          </div>
        </div>
        {!!delivery.pending?.length && (
          <details className="pending-dispatch-details">
            <summary>Pending dispatch <span>{delivery.pending.length} lines</span></summary>
            {delivery.pending.slice(0, 8).map((row) => (
              <div className="connection-row" key={row.dispatch_no}>
                <span className="mail-icon"><Truck size={16} /></span>
                <span><b>{row.customer}</b><small>{row.dispatch_no} / balance {fmtNum(row.balance_qty)} kg / {row.plant}</small></span>
                <span className="status"><i />{row.status}</span>
              </div>
            ))}
          </details>
        )}
        {!(delivery.pending || []).length && <div className="empty-state compact"><Check size={22} /><p>No pending dispatch lines.</p></div>}
      </section>

      <div className="metric-grid dash-grid">
        <Metric icon={BriefcaseBusiness} label="Orders" value={fmtNum(totals.orders)} detail={`${fmtNum(totals.customers)} companies`} accent />
        <Metric icon={TrendingUp} label="Orders value" value={fmtMoney(totals.orders_value)} detail={`avg ${fmtMoney(totals.average_order_value)}`} />
        <Metric icon={Truck} label="Dispatched" value={fmtNum(totals.dispatched_qty)} detail={`${fmtNum(totals.scheduled_qty)} scheduled`} />
        <Metric icon={BarChart3} label="Completion" value={`${totals.completion_pct || 0}%`} detail={`${totals.pending_dispatch || 0} pending lines`} accent />
      </div>

      <section className="panel">
        <div className="panel-heading"><div><div className="section-kicker">COMPANY MIX</div><h3>Top companies by order value</h3></div><BriefcaseBusiness size={19} className="muted" /></div>
        <div className="table-wrap sales-bi-desktop-table"><table><thead><tr><th>Company</th><th>Orders</th><th>Value</th><th>Completion</th></tr></thead><tbody>
          {(companies || []).map((row) => <tr key={row.company}><td className="table-person"><b>{row.company}</b><div className="bar-track"><div className="bar-fill" style={{ width: `${Math.min(100, (row.orders_value / maxValue) * 100)}%` }} /></div></td><td>{fmtNum(row.orders)}</td><td>{fmtMoney(row.orders_value)}</td><td>{row.completion_pct}%</td></tr>)}
          {!(companies || []).length && <tr><td colSpan={4}><small className="muted">No companies in the latest report.</small></td></tr>}
        </tbody></table></div>
        <div className="sales-bi-mobile-list">
          {(companies || []).map((row) => <details className="tally-mobile-row" key={row.company}>
            <summary><span><b>{row.company}</b><small>{fmtNum(row.orders)} orders</small></span><strong>{fmtMoney(row.orders_value)}</strong></summary>
            <div className="tally-extra-body"><span>{row.completion_pct}% completion</span><div className="bar-track"><div className="bar-fill" style={{ width: `${Math.min(100, row.completion_pct || 0)}%` }} /></div></div>
          </details>)}
          {!(companies || []).length && <p className="muted">No companies in the latest report.</p>}
        </div>
      </section>

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
  const [expandedView, setExpandedView] = useState(false);
  const [selectedVisit, setSelectedVisit] = useState(null);
  const [showCaptureForm, setShowCaptureForm] = useState(false);
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
      setShowCaptureForm(false);
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

  // Group visits by category/outcome
  const visitsByCategory = visits.reduce((acc, visit) => {
    const category = visit.outcome || visit.status || "pending";
    if (!acc[category]) acc[category] = [];
    acc[category].push(visit);
    return acc;
  }, {});
  const captureForm = (
    <form onSubmit={create}>
      <div className="form-grid">
        <label>Company *<input required placeholder="Company name" value={form.company} onChange={(event) => setForm({ ...form, company: event.target.value })} /></label>
        <label>Contact Name<input placeholder="Person met" value={form.contact_name} onChange={(event) => setForm({ ...form, contact_name: event.target.value })} /></label>
        <label>Phone<input placeholder="Contact phone" value={form.contact_phone} onChange={(event) => setForm({ ...form, contact_phone: event.target.value })} /></label>
        <label>Visit Date<input type="date" value={form.visit_date} onChange={(event) => setForm({ ...form, visit_date: event.target.value })} /></label>
        <label>Person Met<input placeholder="Name and role" value={form.meet_person} onChange={(event) => setForm({ ...form, meet_person: event.target.value })} /></label>
        <label>Location<input placeholder="Plant/office location" value={form.meet_home_location} onChange={(event) => setForm({ ...form, meet_home_location: event.target.value })} /></label>
      </div>
      <label style={{ display: "block", marginTop: "12px" }}>Previous Discussion<textarea className="voice-text" rows={3} placeholder="What was discussed previously?" value={form.previous_discussion} onChange={(event) => setForm({ ...form, previous_discussion: event.target.value })} /></label>
      <label style={{ display: "block", marginTop: "12px" }}>Visit Notes<textarea className="voice-text" rows={4} placeholder="Meeting notes and observations" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} /></label>
      <label style={{ display: "block", marginTop: "12px" }}>Mail / Chat Details<textarea className="voice-text" rows={2} placeholder="Emails, WhatsApp or chat references" value={form.mail_chat_details} onChange={(event) => setForm({ ...form, mail_chat_details: event.target.value })} /></label>
      <div className="form-grid" style={{ marginTop: "12px" }}>
        <label>Outcome<input placeholder="e.g. quote_requested, positive" value={form.outcome} onChange={(event) => setForm({ ...form, outcome: event.target.value })} /></label>
        <label>Next Action<input placeholder="What to do next" value={form.next_action} onChange={(event) => setForm({ ...form, next_action: event.target.value })} /></label>
        <label>Follow-up Date<input type="date" value={form.follow_up_date} onChange={(event) => setForm({ ...form, follow_up_date: event.target.value })} /></label>
      </div>
      <div className="button-row" style={{ marginTop: "20px" }}>
        <button type="button" className="secondary-button" onClick={() => setShowCaptureForm(false)}>Cancel</button>
        <button type="submit" className="primary-button"><Plus size={15} /> Save Visit</button>
      </div>
    </form>
  );

  return (
    <div className={`content dash ${expandedView ? "visit-expanded" : ""}`}>
      <div className="greeting-banner">
        <span className="greeting-emoji">ðŸ‘‹</span>
        <div>
          <h3>Hola!! {userName} ðŸŽ‰</h3>
          <p className="muted">Welcome to your field dashboard. Keep up the great work! âœ¨</p>
        </div>
      </div>
      <div className="page-heading">
        <div><div className="section-kicker">FIELD / COMPANY HISTORY</div><h2>Company visits</h2>
          <p className="muted">Log visits, outcomes, follow-ups and attach photo/video evidence in GCS.</p></div>
        <div className="button-row">
          <button className="secondary-button" onClick={() => setExpandedView(!expandedView)}>
            {expandedView ? <X size={15} /> : <Eye size={15} />} {expandedView ? "Compact" : "Expanded"}
          </button>
          <button className="secondary-button" onClick={load}><RefreshCw size={15} /> Refresh</button>
          <button className="primary-button" onClick={() => setShowCaptureForm((open) => !open)}>
            {showCaptureForm ? <X size={15} /> : <Plus size={15} />} {showCaptureForm ? "Close capture" : "Capture Meeting"}
          </button>
        </div>
      </div>

      {showCaptureForm && (
        <div className="visit-capture-inline">
          <div className="panel-heading" style={{ marginBottom: 14 }}>
            <div><div className="section-kicker">NEW VISIT</div><h3>Capture meeting</h3></div>
            <button className="icon-button" onClick={() => setShowCaptureForm(false)} aria-label="Close capture form"><X size={18} /></button>
          </div>
          {captureForm}
        </div>
      )}

      <div className="metric-grid">
        <Metric icon={MapPin} label="Visits" value={stats?.visits ?? "--"} detail={`${stats?.companies ?? 0} companies`} accent />
        <Metric icon={CalendarDays} label="This month" value={stats?.this_month ?? "--"} detail="logged visits" />
        <Metric icon={Clock} label="Follow-ups" value={stats?.pending_followups ?? "--"} detail="due or upcoming" />
        <Metric icon={UploadCloud} label="Attachments" value={stats?.media ?? "--"} detail="photos & videos" />
      </div>

      {/* Visit History - Expanded View */}
      <div className={`visits-container ${expandedView ? "expanded" : ""}`}>
        {Object.entries(visitsByCategory).map(([category, categoryVisits]) => (
          <div key={category} className="visit-category-section">
            <div className="visit-category-header">
              <h3>{category.toUpperCase()} ({categoryVisits.length})</h3>
              <span className="visit-category-badge">{category}</span>
            </div>
            <div className="visit-cards-grid">
              {categoryVisits.map((visit) => (
                <div key={visit.id} className="visit-card" onClick={() => setSelectedVisit(visit)}>
                  <div className="visit-card-header">
                    <div>
                      <div className="visit-company">{visit.company}</div>
                      <div className="visit-contact">{visit.contact_name || visit.meet_person}</div>
                    </div>
                    <div className="visit-date">{visit.visit_date}</div>
                  </div>
                  <div className="visit-card-body">
                    {visit.meet_home_location && (
                      <div className="visit-location">
                        <MapPin size={14} /> {visit.meet_home_location}
                      </div>
                    )}
                    {visit.notes && (
                      <div className="visit-notes">{visit.notes.slice(0, 100)}{visit.notes.length > 100 ? "..." : ""}</div>
                    )}
                    {visit.follow_up_date && (
                      <div className="visit-followup">
                        <Clock size={14} /> Follow-up: {visit.follow_up_date}
                      </div>
                    )}
                  </div>
                  <div className="visit-card-footer">
                    <span className="visit-outcome">{visit.outcome || visit.status}</span>
                    <span className="visit-media">{(visit.media || []).length} files</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
        {!visits.length && (
          <div className="empty-state">
            <MapPin size={22} />
            <p>No visits yet.</p>
            <small>Click "Capture Meeting" to log your first field meeting.</small>
          </div>
        )}
      </div>

      {/* Visit Detail Modal */}
      {selectedVisit && (
        <div className="modal-overlay" onClick={() => setSelectedVisit(null)}>
          <div className="modal-content visit-detail-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>{selectedVisit.company}</h2>
                <div className="muted">{selectedVisit.visit_date} Â· {selectedVisit.outcome || selectedVisit.status}</div>
              </div>
              <button className="icon-button" onClick={() => setSelectedVisit(null)}>
                <X size={20} />
              </button>
            </div>
            <div className="modal-body">
              <div className="visit-detail-list">
                <div className="visit-detail-row"><span>Contact</span><span>{selectedVisit.contact_name || selectedVisit.meet_person || "Not specified"}</span></div>
                <div className="visit-detail-row"><span>Phone</span><span>{selectedVisit.contact_phone || "Not provided"}</span></div>
                <div className="visit-detail-row"><span>Person met</span><span>{selectedVisit.meet_person || "Not specified"}</span></div>
                <div className="visit-detail-row"><span>Location</span><span>{selectedVisit.meet_home_location || "Not specified"}</span></div>
                <div className="visit-detail-row"><span>Outcome</span><span>{selectedVisit.outcome || selectedVisit.status || "Not recorded"}</span></div>
                <div className="visit-detail-row"><span>Next action</span><span>{selectedVisit.next_action || "Not specified"}</span></div>
                <div className="visit-detail-row"><span>Follow-up</span><span>{selectedVisit.follow_up_date || "Not scheduled"}</span></div>
                {selectedVisit.map_location && (
                  <div className="visit-detail-row"><span>Map</span><span><a href={selectedVisit.map_location} target="_blank" rel="noreferrer" className="text-button"><MapPin size={14} /> View on map</a></span></div>
                )}
              </div>
              <div className="visit-detail-section">
                <h3>Previous Discussion</h3>
                <p>{selectedVisit.previous_discussion || "No previous discussion recorded"}</p>
              </div>
              <div className="visit-detail-section">
                <h3>Notes</h3>
                <p>{selectedVisit.notes || "No notes"}</p>
              </div>
              <div className="visit-detail-section">
                <h3>Mail / Chat Details</h3>
                <p>{selectedVisit.mail_chat_details || "No mail or chat references"}</p>
              </div>
              <div className="visit-detail-section">
                <h3>Attachments ({(selectedVisit.media || []).length})</h3>
                {(selectedVisit.media || []).length > 0 && (
                  <div className="visit-media-list">
                    {selectedVisit.media.map((item, index) => (
                      <a key={`${item.gcs_path || item.name}-${index}`} href="#" onClick={(event) => event.preventDefault()} title={item.gcs_path || item.name}>
                        {item.kind === "video" ? <Video size={14} /> : <UploadCloud size={14} />}
                        {item.name || `Attachment ${index + 1}`}
                      </a>
                    ))}
                  </div>
                )}
                <label className="secondary-button" style={{ marginTop: 10 }}>
                  <UploadCloud size={15} /> Upload Files
                  <input type="file" accept="image/*,video/*" hidden onChange={(event) => upload(selectedVisit, event.target.files?.[0])} />
                </label>
              </div>
              <div className="button-row" style={{ marginTop: "20px" }}>
                <button className="secondary-button" onClick={() => copyFollowUp(selectedVisit)}>
                  <Copy size={15} /> Copy Follow-up
                </button>
                {whatsappLink(selectedVisit) && (
                  <a className="secondary-button" href={whatsappLink(selectedVisit)} target="_blank" rel="noreferrer">
                    <Send size={15} /> WhatsApp
                  </a>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


// ---------------------------------------------------------------- Instore mails
export function InstoreMails({ onNotice }) {
  const [summary, setSummary] = useState(null);
  const [mails, setMails] = useState([]);
  const [intentFilter, setIntentFilter] = useState("");
  const [mailFilters, setMailFilters] = useState({ query: "", subject: "", company: "", since: "", until: "" });
  const [syncSource, setSyncSource] = useState("auto");
  const [syncLimit, setSyncLimit] = useState(25);
  const [promptInfo, setPromptInfo] = useState(null);
  const [expertise, setExpertise] = useState("sales_strategist");
  const [model, setModel] = useState("");
  const [question, setQuestion] = useState("What should the field team do next based on the latest instore mails?");
  const [reply, setReply] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = async (intent = intentFilter, filters = mailFilters) => {
    try {
      const params = new URLSearchParams({ limit: "50" });
      if (intent) params.set("intent", intent);
      Object.entries(filters).forEach(([key, value]) => { if (value) params.set(key, value); });
      const [nextSummary, nextMails, nextPrompts] = await Promise.all([
        request("/instore/summary"),
        request(`/instore/mails?${params.toString()}`),
        request("/instore/prompts"),
      ]);
      setSummary(nextSummary); setMails(nextMails.mails || []); setPromptInfo(nextPrompts);
      setModel((current) => current || nextPrompts.models?.default || "");
    } catch (error) { onNotice({ type: "error", text: error.message }); }
  };
  useEffect(() => { load(); }, []);

  const sync = async () => {
    setBusy(true);
    try {
      const result = await request("/instore/sync", { method: "POST", body: JSON.stringify({ source: syncSource, limit: syncLimit, query: mailFilters.query, include_body: true, include_dump: syncSource === "auto" || syncSource === "dump" }) });
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
      const result = await request("/instore/ask", { method: "POST", body: JSON.stringify({ question: question.trim(), expertise, model, intent: intentFilter, ...mailFilters }) });
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
      <section className="panel mail-search-panel">
        <div className="panel-heading"><div><div className="section-kicker">RECENT MAIL SEARCH</div><h3>Fetch a filtered sample</h3></div></div>
        <div className="filter-grid">
          <label>Keyword<input value={mailFilters.query} onChange={(event) => setMailFilters({ ...mailFilters, query: event.target.value })} placeholder="rate, product, order number" /></label>
          <label>Subject<input value={mailFilters.subject} onChange={(event) => setMailFilters({ ...mailFilters, subject: event.target.value })} placeholder="Subject contains" /></label>
          <label>Company / contact<input value={mailFilters.company} onChange={(event) => setMailFilters({ ...mailFilters, company: event.target.value })} placeholder="Company or sender" /></label>
          <label>From date<input type="date" value={mailFilters.since} onChange={(event) => setMailFilters({ ...mailFilters, since: event.target.value })} /></label>
          <label>To date<input type="date" value={mailFilters.until} onChange={(event) => setMailFilters({ ...mailFilters, until: event.target.value })} /></label>
          <label>Intent<select value={intentFilter} onChange={(event) => setIntentFilter(event.target.value)}><option value="">All intents</option>{Object.keys(insights.by_intent || {}).map((intent) => <option key={intent} value={intent}>{intent.replaceAll("_", " ")}</option>)}</select></label>
          <label>Mailbox source<select value={syncSource} onChange={(event) => setSyncSource(event.target.value)}><option value="auto">Connected mailbox + sample data</option><option value="gmail">Gmail OAuth</option><option value="imap">IMAP mailbox</option><option value="dump">Sample / exported mail</option></select></label>
          <label>Recent sample size<select value={syncLimit} onChange={(event) => setSyncLimit(Number(event.target.value))}><option value={10}>10 messages</option><option value={25}>25 messages</option><option value={50}>50 messages</option><option value={100}>100 messages</option></select></label>
        </div>
        <div className="button-row"><button className="secondary-button" onClick={() => { const clean = { query: "", subject: "", company: "", since: "", until: "" }; setMailFilters(clean); setIntentFilter(""); load("", clean); }}><X size={15} /> Clear filters</button><button className="primary-button" onClick={() => load()}><Search size={15} /> Apply filters</button></div>
      </section>
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
          <div className="panel-heading"><div><div className="section-kicker">LATEST MAIL</div><h3>Sender / contact links</h3><p className="muted">{mails.length} recent message(s) match the current filters.</p></div></div>
          <div className="mini-stats" style={{ marginBottom: 12 }}>
            {Object.entries(insights.by_intent || {}).slice(0, 6).map(([intent, count]) => <span key={intent}><b>{count}</b> {intent}</span>)}
          </div>
          <div className="table-wrap instore-mail-table"><table><thead><tr><th>Mail / client</th><th>Date</th><th>Intent</th><th>Outcome</th><th>Link</th></tr></thead><tbody>
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
          <div className="instore-mail-mobile">
            {mails.map((mail) => <details className="instore-mail-card" key={`mobile-${mail.id}`}>
              <summary><span><b>{mail.working_title || mail.subject || "(no subject)"}</b><small>{mail.client_name || mail.from_email || mail.to || "Unknown sender"} Â· {String(mail.date || "").slice(0, 10)}</small></span><span className="contact-tag">{mail.intent || "general"}</span></summary>
              <div className="mail-detail">
                <small className="muted">{mail.from_email || mail.to || ""}{mail.owner_email ? ` Â· owner ${mail.owner_email}` : ""}</small>
                {mail.context && <p><b>Context:</b> {mail.context}</p>}
                {mail.snippet && <p>{mail.snippet}</p>}
                {mail.outcome && <p><b>Outcome:</b> {mail.outcome}</p>}
                {(mail.entities || []).length > 0 && <div className="mini-stats">{mail.entities.slice(0, 8).map((entity) => <span key={entity}>{entity}</span>)}</div>}
                {(mail.attachments || []).length > 0 && <div className="mail-attachments"><b>Attachments</b>{mail.attachments.map((item) => <span key={item.name}>{item.name} Â· {item.purpose || "document"}</span>)}</div>}
                <span className={`status-pill ${mail.contact_id ? "approved" : "rejected"}`}>{mail.contact_id ? "Contact linked" : "Contact missing"}</span>
              </div>
            </details>)}
            {!mails.length && <div className="empty-state"><Mail size={20} /><p>No recent mail matches these filters.</p></div>}
          </div>
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
          <Service status={!!instagram.configured} icon={Video} label="Instagram" value={instagram.configured ? "Kalika Enterprises" : "credentials required"} />
          <a className="text-button" href={INSTAGRAM_PROFILE} target="_blank" rel="noreferrer">Kalika Enterprises Instagram company page <ExternalLink size={14} /></a>
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
const DIWALI_REEL = "https://www.instagram.com/reel/DejmP7AMb5j/?utm_source=ig_web_copy_link&psln=MzRlODBiNWFlZA==&srtk=MzRlODBiNWFlZA==";
const INSTAGRAM_PROFILE = "https://www.instagram.com/kalikaenterprises1667/";
const PACKAGING_SHOWCASE = "https://www.instagram.com/reel/DejmP7AMb5j/?utm_source=ig_web_copy_link&psln=MzRlODBiNWFlZA==&srtk=MzRlODBiNWFlZA==";

const CURATED_MESSAGES = [
  {
    id: "diwali-2026",
    category: "Diwali",
    title: "Diwali greetings + festive reel",
    text: `âœ¨ Happy Diwali from Kalika Enterprises! âœ¨\n\nMay this festival of lights bring growth, prosperity and new partnerships to your business. Thank you for trusting us with your flexible packaging needs.\n\nðŸŽ¬ Watch our festive reel: ${DIWALI_REEL}\n\nWarm wishes,\nKalika Enterprises\nðŸ“ž Reply to this message for a quick quote.`,
    video: DIWALI_REEL,
  },
  {
    id: "growth-partner",
    category: "Business growth",
    title: "Grow faster with a packaging partner",
    text: `Hi {name},\n\nEvery order is a chance to grow. At Kalika Enterprises we help brands cut packaging cost, improve shelf appeal and deliver on time â€” every time.\n\nâœ… Custom poly bags & films\nâœ… Fast sampling and quotes\nâœ… Reliable dispatch from our plant\n\nReply YES and we will share a growth plan for {company}.`,
  },
  {
    id: "short-packaging",
    category: "Packaging",
    title: "Short packaging pitch",
    text: `Hi {name}, need stronger, lighter, better-looking packaging?\n\nKalika Enterprises makes custom poly bags & films that protect your product and lift your brand â€” at the right price.\n\nSend us your size and quantity for a same-day estimate. ðŸ“¦`,
  },
  {
    id: "feedback-recent-order",
    category: "Feedback",
    title: "Feedback on recent order",
    text: `Hi {name},\n\nThank you for your recent order {order_no} with Kalika Enterprises. We would love your feedback:\n\n1ï¸âƒ£ Product quality (1-5)\n2ï¸âƒ£ Delivery timeliness (1-5)\n3ï¸âƒ£ Anything we can improve?\n\nYour feedback helps us serve you better. ðŸ™`,
  },
  {
    id: "new-customer",
    category: "New customer",
    title: "Welcome a new customer",
    text: `Welcome to Kalika Enterprises, {name}! ðŸŽ‰\n\nWe are excited to partner with {company} for flexible packaging. Here is what you can expect:\n\nâ€¢ Dedicated support\nâ€¢ Fast quotes and samples\nâ€¢ Consistent quality and dispatch\n\nReply with your requirement and we will get started today.`,
  },
  {
    id: "reorder",
    category: "Follow-up",
    title: "Reorder / follow-up",
    text: `Hi {name}, hope your last batch from Kalika Enterprises is working well.\n\nRunning low on stock? Reply with your quantity and we will reserve production for {company} this week.\n\nðŸŽ¬ See our packaging in action: {video}`,
    video: DIWALI_REEL,
  },
  {
    id: "rate-quote",
    category: "Business growth",
    title: "Share a rate quote",
    text: `Hi {name}, here is our latest quote for {company}:\n\nâ€¢ Product: {product}\nâ€¢ Rate: {rate}\nâ€¢ Validity: 7 days\n\nReply to confirm and we will block capacity for you. Thank you for choosing Kalika Enterprises.`,
  },
  {
    id: "catalogue",
    category: "Packaging",
    title: "Share catalogue / samples",
    text: `Hi {name}, sharing the Kalika Enterprises packaging range for {company}. We can customise size, micron, print and finish.\n\nWant physical samples? Reply with your address and we will courier them. ðŸ“¬`,
  },
];

const CHANNEL_VIDEOS = [
  { title: "Diwali festive reel", link: DIWALI_REEL, tag: "Instagram", note: "Share with Diwali greetings" },
  { title: "Packaging showcase", link: PACKAGING_SHOWCASE, tag: "Instagram", note: "Kalika Enterprises packaging reel" },
  { title: "Plant & capacity tour", link: "https://www.youtube.com/@kalikaenterprises", tag: "YouTube", note: "Build trust with new customers" },
  { title: "Product demo", link: "https://www.youtube.com/@kalikaenterprises", tag: "YouTube", note: "Attach to follow-ups" },
];

function whatsappHref(text, phone) {
  const digits = String(phone || "").replace(/\D/g, "");
  const base = digits ? `https://wa.me/${digits.length === 10 ? `91${digits}` : digits}` : "https://wa.me/";
  return `${base}?text=${encodeURIComponent(text || "")}`;
}

function htmlToText(html) {
  return String(html || "")
    .replace(/<style[\s\S]*?<\/style>/gi, "")
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/(p|div|li|h[1-6]|tr)>/gi, "\n")
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function MessageStudio_UNUSED({ onNotice }) {
  const [category, setCategory] = useState("All");
  const [phone, setPhone] = useState("");
  const [orders, setOrders] = useState([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    request("/erp/orders?limit=5")
      .then((rows) => setOrders(Array.isArray(rows) ? rows.slice(0, 5) : []))
      .catch(() => setOrders([]));
  }, []);

  const categories = ["All", ...Array.from(new Set(CURATED_MESSAGES.map((m) => m.category)))];
  const visible = category === "All" ? CURATED_MESSAGES : CURATED_MESSAGES.filter((m) => m.category === category);

  const fill = (text, order) => {
    let out = text;
    if (order) {
      out = out
        .replaceAll("{name}", order.customer || "there")
        .replaceAll("{company}", order.customer || "your business")
        .replaceAll("{order_no}", order.order_no || "recent order");
    }
    return out.replaceAll("{video}", DIWALI_REEL);
  };

  const copy = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      onNotice({ type: "success", text: "Message copied â€” paste it in WhatsApp." });
    } catch {
      onNotice({ type: "error", text: "Clipboard unavailable â€” select and copy manually." });
    }
  };

  const openWhatsApp = (text) => {
    window.open(whatsappHref(text, phone), "_blank", "noopener");
  };

  return (
    <section className="panel studio-panel">
      <div className="panel-heading">
        <div>
          <div className="section-kicker">CURATED OUTREACH / COPY &amp; WHATSAPP</div>
          <h3>Message studio</h3>
        </div>
        <div className="studio-phone">
          <MessageCircle size={16} />
          <input
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
            placeholder="WhatsApp number (optional)"
            inputMode="tel"
          />
        </div>
      </div>

      <div className="studio-funnel">
        <div className="studio-funnel-head"><Target size={15} /><b>Refine your funnel</b><span className="muted">turn the marketing list into conversations</span></div>
        <div className="studio-chips">
          {categories.map((item) => (
            <button key={item} className={`chip ${category === item ? "active" : ""}`} onClick={() => setCategory(item)}>{item}</button>
          ))}
        </div>
      </div>

      <div className="studio-grid">
        {visible.map((message) => {
          const text = fill(message.text);
          return (
            <article className="studio-card" key={message.id}>
              <div className="studio-card-top">
                <span className="template-channel">{message.category}</span>
                <b>{message.title}</b>
              </div>
              <p className="studio-text">{text}</p>
              <div className="button-row studio-actions">
                <button className="secondary-button" onClick={() => copy(text)}><Copy size={14} /> Copy</button>
                <button className="primary-button" onClick={() => openWhatsApp(text)}><MessageCircle size={14} /> WhatsApp</button>
                {message.video && <a className="text-button" href={message.video} target="_blank" rel="noreferrer"><ExternalLink size={14} /> Reel</a>}
              </div>
            </article>
          );
        })}
      </div>

      <div className="studio-section">
        <div className="section-kicker"><Film size={13} /> CHANNEL VIDEO LIBRARY</div>
        <div className="studio-videos">
          {CHANNEL_VIDEOS.map((video) => (
            <div className="studio-video" key={video.title}>
              <span className="mail-icon"><Video size={16} /></span>
              <div>
                <b>{video.title}</b>
                <small>{video.tag} Â· {video.note}</small>
              </div>
              <div className="button-row">
                <button className="icon-button" title="Copy link" onClick={() => copy(video.link)}><Copy size={15} /></button>
                <a className="icon-button" title="Open video" href={video.link} target="_blank" rel="noreferrer"><ExternalLink size={15} /></a>
                <button className="icon-button" title="Share on WhatsApp" onClick={() => openWhatsApp(`${video.title}: ${video.link}`)}><MessageCircle size={15} /></button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="studio-section">
        <div className="section-kicker"><TrendingUp size={13} /> RECENT ERP ORDERS Â· ASK FOR FEEDBACK</div>
        {orders.length === 0 ? (
          <p className="muted" style={{ fontSize: 12 }}>No recent ERP orders available yet.</p>
        ) : (
          <div className="studio-videos">
            {orders.map((order) => {
              const feedback = fill(CURATED_MESSAGES.find((m) => m.id === "feedback-recent-order").text, order);
              return (
                <div className="studio-video" key={order.order_no}>
                  <span className="mail-icon"><BriefcaseBusiness size={16} /></span>
                  <div>
                    <b>{order.customer}</b>
                    <small>{order.order_no} Â· â‚¹{fmtNum(order.total_value)} Â· {order.status}</small>
                  </div>
                  <div className="button-row">
                    <button className="icon-button" title="Copy feedback request" onClick={() => copy(feedback)}><Copy size={15} /></button>
                    <button className="icon-button" title="Send feedback request on WhatsApp" onClick={() => openWhatsApp(feedback)}><MessageCircle size={15} /></button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}


function MarketingLibrary({ onNotice, orders, videos }) {
  const copy = async (text) => { try { await navigator.clipboard.writeText(text||""); onNotice({type:"success",text:"Copied."}); } catch { onNotice({type:"error",text:"Copy failed."}); } };
  const wa = (text) => window.open(`https://wa.me/?text=${encodeURIComponent(text||"")}`, "_blank", "noopener");
  const feedbackText = (o) => `Hi ${o.customer||"there"},\n\nThank you for your recent order ${o.order_no||""} with Kalika Enterprises. We would love your feedback:\n1) Product quality (1-5)\n2) Delivery timeliness (1-5)\n3) Anything we can improve?\n\nThank you.`;
  return (<>
    <section className="panel studio-panel">
      <div className="section-kicker"><Film size={13} /> CHANNEL VIDEO LIBRARY</div>
      <div className="studio-videos">
        {(videos?.length ? videos : CHANNEL_VIDEOS.map(v=>({title:v.title,url:v.link,platform:v.tag,description:v.note}))).map((v) => (
          <div className="studio-video" key={v.title||v.url}>
            <span className="mail-icon"><Video size={16} /></span>
            <div><b>{v.title}</b><small>{v.platform||v.tag||""} ? {v.description||v.note||""}</small></div>
            <div className="button-row">
              <button className="icon-button" title="Copy link" onClick={() => copy(v.url||v.link)}><Copy size={15} /></button>
              <a className="icon-button" title="Open" href={v.url||v.link} target="_blank" rel="noreferrer"><ExternalLink size={15} /></a>
              <button className="icon-button" title="WhatsApp" onClick={() => wa(`${v.title}: ${v.url||v.link}`)}><MessageCircle size={15} /></button>
            </div>
          </div>
        ))}
      </div>
    </section>
    <section className="panel studio-panel">
      <div className="section-kicker"><TrendingUp size={13} /> RECENT ERP ORDERS ? ASK FOR FEEDBACK</div>
      {!orders?.length ? <p className="muted" style={{fontSize:12}}>No recent ERP orders available yet.</p> : (
        <div className="studio-videos">
          {orders.map((o) => (
            <div className="studio-video" key={o.order_no}>
              <span className="mail-icon"><BriefcaseBusiness size={16} /></span>
              <div><b>{o.customer}</b><small>{o.order_no} ? ?{fmtNum(o.total_value)} ? {o.status}</small></div>
              <div className="button-row">
                <button className="icon-button" title="Copy feedback request" onClick={() => copy(feedbackText(o))}><Copy size={15} /></button>
                <button className="icon-button" title="WhatsApp" onClick={() => wa(feedbackText(o))}><MessageCircle size={15} /></button>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  </>);
}

function MarketingSignals({ onNotice }) {
  const [out, setOut] = useState(null); const [busy, setBusy] = useState(false);
  const run = async (path, body, label) => { setBusy(true); try { setOut({ label, data: await request(path, { method: "POST", body: JSON.stringify(body) }) }); } catch (e) { onNotice({type:"error",text:e.message}); } finally { setBusy(false); } };
  return (<div className="panel studio-panel">
    <div className="panel-heading"><div><div className="section-kicker">MARKET INTELLIGENCE</div><h3>Signal desk</h3></div></div>
    <div className="signal-actions">
      <button className="signal-action" onClick={() => run("/social/linkedin/search", { keywords: ["procurement", "scm", "hiring"] }, "LinkedIn")}><span><BriefcaseBusiness size={20} /></span><b>LinkedIn hiring search</b><small>Procurement & SCM signals.</small></button>
      <button className="signal-action" onClick={() => run("/social/reddit/search", {}, "Reddit")}><span><Search size={20} /></span><b>Reddit search</b><small>Useful conversations.</small></button>
      <button className="signal-action" onClick={() => run("/social/youtube/search", { queries: ["hiring procurement", "supply chain"], max_results: 10 }, "YouTube")}><span><Video size={20} /></span><b>YouTube scan</b><small>Company/tech signals.</small></button>
      <button className="signal-action" onClick={() => run("/scheduler/run", {}, "Cron sweep")}><span><RefreshCw size={20} /></span><b>Run cron sweep</b><small>Scheduled tasks.</small></button>
    </div>
    {busy && <p className="muted">Working?</p>}
    {out && <section className="panel output-panel" style={{marginTop:12}}><div className="panel-heading"><h3>{out.label}</h3><button className="icon-button" onClick={() => setOut(null)}><X size={17} /></button></div><pre>{JSON.stringify(out.data, null, 2)}</pre></section>}
  </div>);
}

function MarketingEvents({ onNotice }) {
  const [events, setEvents] = useState([]); const [busy, setBusy] = useState(false);
  const load = () => request("/events?limit=50").then((r)=>setEvents(Array.isArray(r)?r:[])).catch(()=>setEvents([]));
  useEffect(()=>{ load(); }, []);
  const importLocal = async () => { setBusy(true); try { const body=new FormData(); body.append("include_contacts","true"); const token=sessionStorage.getItem("sales_token"); const res=await fetch(`${API}/events/import`,{method:"POST",headers:token?{Authorization:`Bearer ${token}`}:{},body}); if(!res.ok) throw new Error((await res.json().catch(()=>({}))).detail||"Import failed"); const result=await res.json(); onNotice({type:"success",text:`Loaded ${result.source||"workbook"}: ${result.events_imported} events.`}); load(); } catch(e){ onNotice({type:"error",text:e.message}); } finally{ setBusy(false);} };
  return (<div className="panel studio-panel">
    <div className="panel-heading"><div><div className="section-kicker">EVENTS &amp; OUTREACH</div><h3>Events</h3></div><div className="button-row"><button className="secondary-button" onClick={importLocal} disabled={busy}><Database size={15}/> {busy?"Loading?":"Load workbook"}</button><button className="icon-button" onClick={load}><RefreshCw size={16}/></button></div></div>
    <div className="contact-list" role="list">
      {events.map((ev)=> <div key={ev.id} className="contact-row"><span className="contact-main"><b>{ev.title}</b><small>{ev.starts_at?new Date(ev.starts_at).toLocaleString():(ev.when_text||"Date TBC")} ? {ev.location||ev.organiser||""}</small></span><span className={`event-status ${ev.status||""}`}>{ev.status||""}</span></div>)}
      {!events.length && <div className="empty-state"><CalendarDays size={22}/><p>No events loaded.</p><small>Load the workbook to populate events and outreach.</small></div>}
    </div>
  </div>);
}


export function MarketingCompanies({ onNotice }) {
  const [mTab, setMTab] = useState("send");
  const [sources, setSources] = useState([]);
  const [imageTemplates, setImageTemplates] = useState([]);
  const [attachImage, setAttachImage] = useState("");
  const imgUploadRef = React.useRef(null);
  const [showTplPicker, setShowTplPicker] = useState(false);
  const [tplSearch, setTplSearch] = useState("");
  const [tplSort, setTplSort] = useState("recent");
  const [editTplId, setEditTplId] = useState(null);
  const [tplEdit, setTplEdit] = useState({ subject: "", body: "" });
  const [mOrders, setMOrders] = useState([]);
  const [mVideos, setMVideos] = useState([]);
  const [rows, setRows] = useState([]);
  const [stats, setStats] = useState(null);
  const [query, setQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [funnelStageFilter, setFunnelStageFilter] = useState(() => {
    const saved = sessionStorage.getItem("marketing_funnel_filter") || "";
    sessionStorage.removeItem("marketing_funnel_filter");
    return saved;
  });
  const [salesProgressFilter, setSalesProgressFilter] = useState("");
  const [dueFollowupsOnly, setDueFollowupsOnly] = useState(() => {
    const saved = sessionStorage.getItem("marketing_due_follow_up") === "true";
    sessionStorage.removeItem("marketing_due_follow_up");
    return saved;
  });
  const [editing, setEditing] = useState({});
  const [busy, setBusy] = useState(false);
  const [templates, setTemplates] = useState([]);
  const [limit, setLimit] = useState(25);
  const [requirementsOnly, setRequirementsOnly] = useState(false);
  const [sendTarget, setSendTarget] = useState(null);
  const [sendTemplateId, setSendTemplateId] = useState("");
  const [sendSubject, setSendSubject] = useState("");
  const [sendText, setSendText] = useState("");
  const [sortBy, setSortBy] = useState("company");
  const [syncPath, setSyncPath] = useState("");
  const [activity, setActivity] = useState({});

  const loadActivity = async () => {
    try {
      const rows = await request("/marketing-companies/activity");
      const map = {};
      (Array.isArray(rows) ? rows : []).forEach((a) => { map[a.contact_id] = a; });
      setActivity(map);
    } catch { /* activity is best-effort */ }
  };
  const fileInputRef = React.useRef(null);

  const load = async () => {
    const params = new URLSearchParams();
    if (query) params.set("q", query);
    if (categoryFilter) params.set("category", categoryFilter);
    if (statusFilter) params.set("call_status", statusFilter);
    if (funnelStageFilter) params.set("funnel_stage", funnelStageFilter);
    if (salesProgressFilter) params.set("sales_progress", salesProgressFilter);
    if (dueFollowupsOnly) params.set("due_follow_up", "true");
    if (requirementsOnly) params.set("requirements_only", "true");
    if (sortBy) params.set("sort", sortBy);
    params.set("limit", String(limit));
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

  const loadSources = () => request("/marketing-companies/sources").then((d) => setSources(Array.isArray(d?.items) ? d.items : [])).catch(() => setSources([]));
  const loadImageTemplates = () => request("/media/image-templates")
    .then((d) => { const items = Array.isArray(d?.items) ? d.items : []; setImageTemplates(items); setAttachImage((prev) => prev || items[0]?.url || ""); })
    .catch(() => setImageTemplates([]));
  const uploadImageTemplate = async (ev) => {
    const file = ev.target.files?.[0];
    if (!file) return;
    const fd = new FormData(); fd.append("file", file);
    const token = sessionStorage.getItem("sales_token") || "";
    setBusy(true);
    try {
      const res = await fetch(`${API}/media/upload?kind=image_template`, { method: "POST", headers: token ? { Authorization: `Bearer ${token}` } : {}, body: fd });
      if (!res.ok) { let m = "Image upload failed"; try { m = (await res.json()).detail || m; } catch {} throw new Error(m); }
      const data = await res.json();
      onNotice({ type: "success", text: `Poster uploaded to ${data.gcs_path}` });
      await loadImageTemplates();
      if (data.url) setAttachImage(data.url);
    } catch (e) { onNotice({ type: "error", text: e.message }); } finally { setBusy(false); if (imgUploadRef.current) imgUploadRef.current.value = ""; }
  };
  useEffect(() => { load(); loadActivity(); loadSources(); loadImageTemplates(); }, []);

  useEffect(() => {
    if (!cDetail) return undefined;
    const id = setInterval(() => openCampaign(cDetail.id), 12000);
    return () => clearInterval(id);
  }, [cDetail?.id, cDetail?.status, cDetail?.sent_count, cDetail?.opened_count]);

  useEffect(() => {
    request("/templates")
      .then((rows) => setTemplates(Array.isArray(rows) ? rows : []))
      .catch(() => setTemplates([]));
  }, []);

  const debounced = query;
  useEffect(() => {
    const id = setTimeout(() => load(), 250);
    return () => clearTimeout(id);
  }, [debounced, categoryFilter, statusFilter, funnelStageFilter, salesProgressFilter, dueFollowupsOnly, requirementsOnly, limit, sortBy]);

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

  const uploadFile = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    
    setBusy(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      
      const response = await fetch("/api/marketing-companies/import", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${sessionStorage.getItem("sales_token")}`,
        },
        body: formData,
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Upload failed");
      }
      
      const result = await response.json();
      onNotice({
        type: "success",
        text: `File uploaded successfully! Imported ${result.imported}, updated ${result.updated}, skipped ${result.skipped}.`,
      });
      await load();
    } catch (error) {
      onNotice({ type: "error", text: error.message });
    } finally {
      setBusy(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
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

  const syncOne = async (path) => {
    setBusy(true);
    try {
      const result = await request(`/marketing-companies/sync?path=${encodeURIComponent(path)}`, { method: "POST" });
      onNotice({ type: result.ok ? "success" : "error", text: result.ok ? `Synced ${path.split("/").pop()} (${result.imported} new, ${result.updated} updated).` : (result.detail || "Sync failed.") });
      load(); loadSources();
    } catch (error) { onNotice({ type: "error", text: error.message }); } finally { setBusy(false); }
  };
  const syncFromGCS = async () => {
    setBusy(true);
    try {
      const params = new URLSearchParams();
      if (syncPath.trim()) params.set("path", syncPath.trim());
      const suffix = params.toString() ? `?${params.toString()}` : "";
      const result = await request(`/marketing-companies/sync${suffix}`, { method: "POST" });
      onNotice({
        type: result.ok ? "success" : "error",
        text: `Synced ${result.sources?.length || 0} GCS file(s): ${result.imported} new, ${result.updated} refreshed, ${result.skipped} unchanged.${result.warnings?.length ? ` ${result.warnings.join("; ")}` : ""}`,
      });
      await load(); await loadActivity();
    } catch (error) {
      onNotice({ type: "error", text: error.message });
    } finally {
      setBusy(false);
    }
  };

  const categories = stats ? Object.keys(stats.by_category || {}).sort() : [];
  const statuses = stats ? Object.keys(stats.by_call_status || {}).sort() : [];
  const funnelStages = ["awareness", "interest", "decision", "action"];
  const progressOptions = ["new", "video_sent", "catalog_sent", "requirements_requested", "rate_requested", "quote_sent", "material_sent"];
  const copyPhone = async (phone) => {
    try {
      await navigator.clipboard.writeText(phone);
      onNotice({ type: "success", text: "Phone number copied." });
    } catch {
      onNotice({ type: "error", text: "Clipboard unavailable â€” copy the number manually." });
    }
  };

  const openSend = (row) => {
    setSendTarget(row);
    setSendTemplateId("");
    setSendSubject("");
    setSendText("");
  };

  const applyTemplate = (id) => {
    setSendTemplateId(id);
    const template = templates.find((item) => String(item.id) === String(id));
    if (!template) return;
    setSendSubject(template.subject || "");
    setSendText(htmlToText(template.body));
  };

  const copySendText = async () => {
    try {
      await navigator.clipboard.writeText(sendText);
      onNotice({ type: "success", text: "Message copied." });
    } catch {
      onNotice({ type: "error", text: "Clipboard unavailable â€” copy the message manually." });
    }
  };

  const sendWhatsApp = () => {
    if (!sendTarget?.phone) return;
    window.open(whatsappHref(sendText, sendTarget.phone), "_blank", "noopener");
  };

  const sendEmail = () => {
    if (!sendTarget?.email) return;
    const subject = encodeURIComponent(sendSubject || `Kalika Enterprises Â· ${sendTarget.company}`);
    const body = encodeURIComponent(sendText || "");
    window.location.href = `mailto:${sendTarget.email}?subject=${subject}&body=${body}`;
  };

  const [campaigns, setCampaigns] = useState([]);
  const [tplMeta, setTplMeta] = useState({ channels: [], strategies: [], funnel_stages: [] });
  const [selTemplate, setSelTemplate] = useState(null);
  const [cName, setCName] = useState("Marketing campaign");
  const [cChannel, setCChannel] = useState("email");
  const [cStrategy, setCStrategy] = useState("cold_outreach");
  const [useAi, setUseAi] = useState(true);
  const [cLimit, setCLimit] = useState(50);
  const [cDetail, setCDetail] = useState(null);
  const [cBusy, setCBusy] = useState(false);
  const loadCampaigns = async () => {
    try {
      const [camps, m] = await Promise.all([request("/campaigns"), request("/templates/meta")]);
      setCampaigns(Array.isArray(camps) ? camps : []);
      setTplMeta(m || { channels: [], strategies: [], funnel_stages: [] });
    } catch { setCampaigns([]); }
  };
  useEffect(() => { loadCampaigns(); }, []);
  const pickTemplate = (t) => { setSelTemplate(t); if (t) { setCChannel(t.channel || "email"); setCStrategy(t.strategy || "cold_outreach"); } };

  // Templates tab content (preview/edit/delete) folded in, minus the giant page heading
  const [previewTemplate, setPreviewTemplate] = useState(null);
  const [editTemplate, setEditTemplate] = useState(null);
  const [newTemplate, setNewTemplate] = useState(null);
  const [newContact, setNewContact] = useState(null);
  const [defaultVideos, setDefaultVideos] = useState([]);
  const [ga, setGa] = useState(null);
  const [gaBusy, setGaBusy] = useState(false);
  const tplUploadRef = React.useRef(null);
  const mediaUploadRef = React.useRef(null);
  const mediaKindRef = React.useRef("image");

  const loadDefaultVideos = async () => {
    try { setDefaultVideos(await request("/media/default-videos")); } catch { setDefaultVideos([]); }
  };
  const loadGa = async () => {
    try { setGa(await request("/analytics/google")); } catch (e) { setGa({ data_available: false, message: e.message, insights: [], stats: {} }); }
  };
  const gaSync = async (force = false) => {
    setGaBusy(true);
    try {
      const result = await request(`/analytics/google/sync${force ? "?force=true" : ""}`, { method: "POST" });
      setGa(result);
      if (result.status === "no_new_files") onNotice({ type: "success", text: result.message || "No new file detected." });
      else if (result.status === "processed") onNotice({ type: "success", text: `Processed ${result.new_files?.length || 0} new GA file(s) ? insights updated.` });
      else onNotice({ type: "error", text: result.message || "GA sync failed." });
    } catch (error) { onNotice({ type: "error", text: error.message }); } finally { setGaBusy(false); }
  };
  useEffect(() => { loadDefaultVideos(); loadGa(); }, []);
  const pickDefaultVideo = (video) => {
    const url = video?.url || "";
    setSendText((prev) => {
      if (!url || (prev || "").includes(url)) return prev || "";
      return prev ? `${prev}\n\nWatch our manufacturing process: ${url}` : `Watch our manufacturing process: ${url}`;
    });
    onNotice({ type: "success", text: "Default video link added to the message." });
  };
  const deleteTemplate = async (id) => {
    if (!window.confirm("Delete this template?")) return;
    try { await request(`/templates/${id}`, { method: "DELETE" }); onNotice({ type: "success", text: "Template deleted" }); loadCampaigns(); }
    catch (e) { onNotice({ type: "error", text: e.message }); }
  };
  const updateTemplate = async (id, updates) => {
    try { await request(`/templates/${id}`, { method: "PATCH", body: JSON.stringify(updates) }); onNotice({ type: "success", text: "Template updated" }); setEditTemplate(null); loadCampaigns(); }
    catch (e) { onNotice({ type: "error", text: e.message }); }
  };
  const createTemplateFromForm = async (e) => {
    e.preventDefault();
    const form = newTemplate || {};
    if (!form.name?.trim() || !form.body?.trim()) return onNotice({ type: "error", text: "Template name and body are required." });
    setCBusy(true);
    try {
      const created = await request("/templates", {
        method: "POST",
        body: JSON.stringify({
          name: form.name.trim(), channel: form.channel || "email", strategy: form.strategy || "cold_outreach",
          funnel_stage: "awareness", subject: form.subject || "", body: form.body,
        }),
      });
      onNotice({ type: "success", text: `Template "${created.name}" created. Uploading it to Mail_templates on next sync keeps it in GCS.` });
      setNewTemplate(null); loadCampaigns();
    } catch (e) { onNotice({ type: "error", text: e.message }); } finally { setCBusy(false); }
  };
  const uploadTemplateFile = async (ev) => {
    const file = ev.target.files?.[0];
    if (!file) return;
    const fd = new FormData(); fd.append("file", file);
    const token = sessionStorage.getItem("sales_token") || "";
    setCBusy(true);
    try {
      const res = await fetch(`${API}/templates/upload?channel=${encodeURIComponent((newTemplate?.channel || "email"))}`, {
        method: "POST", headers: token ? { Authorization: `Bearer ${token}` } : {}, body: fd,
      });
      if (!res.ok) { let m = "Template upload failed"; try { m = (await res.json()).detail || m; } catch {} throw new Error(m); }
      const data = await res.json();
      onNotice({ type: "success", text: `${data.message || "Template uploaded"}${data.gcs_path ? ` Â· stored ${data.gcs_path}` : ""}` });
      setNewTemplate(null); loadCampaigns();
    } catch (e) { onNotice({ type: "error", text: e.message }); } finally {
      setCBusy(false); if (tplUploadRef.current) tplUploadRef.current.value = "";
    }
  };
  const uploadMedia = async (ev) => {
    const file = ev.target.files?.[0];
    if (!file) return;
    const kind = mediaKindRef.current || "image";
    const fd = new FormData(); fd.append("file", file);
    const token = sessionStorage.getItem("sales_token") || "";
    setBusy(true);
    try {
      const res = await fetch(`${API}/media/upload?kind=${encodeURIComponent(kind)}`, {
        method: "POST", headers: token ? { Authorization: `Bearer ${token}` } : {}, body: fd,
      });
      if (!res.ok) { let m = "Media upload failed"; try { m = (await res.json()).detail || m; } catch {} throw new Error(m); }
      const data = await res.json();
      setSendText((prev) => {
        const url = data.url || data.gcs_path || "";
        if (!url) return prev || "";
        return prev ? `${prev}\n${url}` : url;
      });
      onNotice({ type: "success", text: `Uploaded to ${data.gcs_path}` });
    } catch (e) { onNotice({ type: "error", text: e.message }); } finally {
      setBusy(false); if (mediaUploadRef.current) mediaUploadRef.current.value = "";
    }
  };
  const addContactManually = async (e) => {
    e.preventDefault();
    const form = newContact || {};
    if (!form.company?.trim()) return onNotice({ type: "error", text: "Company is required." });
    setBusy(true);
    try {
      await request("/marketing-companies", {
        method: "POST",
        body: JSON.stringify({
          company: form.company.trim(), contact_name: form.contact_name || "", phone: form.phone || "", email: form.email || "",
          category: form.category || "", call_status: form.call_status || "", requirements: form.requirements || "",
          follow_up_date: form.follow_up_date || "", next_action: form.next_action || "",
        }),
      });
      onNotice({ type: "success", text: "Contact added manually." });
      setNewContact(null); load(); loadActivity();
    } catch (e) { onNotice({ type: "error", text: e.message }); } finally { setBusy(false); }
  };
  const runTaskPreset = async (type) => {
    if (!selTemplate) return onNotice({ type: "error", text: "Select a template first." });
    if (!selectedRows.length) return onNotice({ type: "error", text: "Select contacts (checkbox) first, or the table filters will be used." });
    const presets = {
      bulk: { name: "Bulk marketing", strategy: "cold_outreach" },
      followup: { name: "Follow-up", strategy: "follow_up" },
      catalog: { name: "Product catalog", strategy: "catalog" },
      video: { name: "Manufacturing video", strategy: "manufacturing_video" },
    };
    const p = presets[type] || presets.bulk;
    setCName(p.name); setCStrategy(p.strategy);
    await createCampaign(selectedRows);
  };
  const syncTemplates = async () => {
    setCBusy(true);
    try { const r = await request("/templates/sync-gcs", { method: "POST" }); onNotice({ type: "success", text: r.message || `Synced ${r.synced} templates` }); await loadCampaigns(); }
    catch (e) { onNotice({ type: "error", text: e.message }); } finally { setCBusy(false); }
  };

  const fillSendArea = (row) => {
    const t = templates.find((x) => x.channel === "email") || templates[0];
    if (t) {
      pickTemplate(t);
      setSendTemplateId(String(t.id));
      setSendSubject(t.subject || "");
      setSendText(t.body ? htmlToText(t.body) : "");
    }
    setActiveRow(row);
    setSendTarget(row);
  };

  const createCampaign = async (targetRows, autoSend = false) => {
    if (!selTemplate) return onNotice({ type: "error", text: "Select a template first." });
    setCBusy(true);
    try {
      const detail = await request("/campaigns", {
        method: "POST",
        body: JSON.stringify({
          name: cName, channel: cChannel, strategy: cStrategy,
          template_id: selTemplate.id, use_ai: useAi, auto_send: !!autoSend, image_url: attachImage || "",
          filter: {
            limit: Math.min(Number(cLimit) || (targetRows?.length || 50), targetRows?.length || Number(cLimit) || 50),
            contact_type: "marketing_companies",
            q: query, category: categoryFilter, call_status: statusFilter, funnel_stage: funnelStageFilter,
            contact_ids: (targetRows || []).map((r) => r.id),
          },
        }),
      });
      setCDetail(detail); onNotice({ type: "success", text: `Generated ${detail.total} messages for review.` }); loadCampaigns();
    } catch (e) { onNotice({ type: "error", text: e.message }); } finally { setCBusy(false); }
  };
  const createSelectedCampaign = async () => {
    if (!selTemplate) return onNotice({ type: "error", text: "Select a template first." });
    if (!selectedRows.length) return onNotice({ type: "error", text: "Tick at least one contact checkbox, or use Select for a single contact." });
    await createCampaign(selectedRows);
  };
  const openCampaign = async (id) => { try { setCDetail(await request(`/campaigns/${id}`)); } catch (e) { onNotice({ type: "error", text: e.message }); } };
  const approveCampaign = async () => {
    if (!cDetail) return; setCBusy(true);
    try { setCDetail(await request(`/campaigns/${cDetail.id}/approve`, { method: "POST" })); onNotice({ type: "success", text: "Approved â€” ready to send." }); }
    catch (e) { onNotice({ type: "error", text: e.message }); } finally { setCBusy(false); }
  };
  const sendCampaign = async () => {
    if (!cDetail || cDetail.status !== "approved") return;
    if (!window.confirm(`Send ${cDetail.total} approved messages in ${cDetail.name}?`)) return;
    setCBusy(true);
    try {
      const result = await request(`/campaigns/${cDetail.id}/send`, { method: "POST" });
      onNotice({ type: "success", text: `Sent ${result.sent}, failed ${result.failed}, queued ${result.skipped}.` });
      setCDetail(await request(`/campaigns/${cDetail.id}`)); loadCampaigns();
    } catch (e) { onNotice({ type: "error", text: e.message }); } finally { setCBusy(false); }
  };
  const progressPct = cDetail && cDetail.total ? Math.round(((cDetail.sent_count + cDetail.failed_count) / cDetail.total) * 100) : 0;
  const openRate = cDetail && cDetail.sent_count ? Math.round(((cDetail.opened_count || 0) / cDetail.sent_count) * 100) : 0;
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const allVisibleSelected = rows.length > 0 && rows.every((r) => selectedIds.has(r.id));
  const toggleSelectAll = () => setSelectedIds((prev) => {
    const next = new Set(prev);
    if (rows.every((r) => next.has(r.id))) rows.forEach((r) => next.delete(r.id));
    else rows.forEach((r) => next.add(r.id));
    return next;
  });
  const [activeRow, setActiveRow] = useState(null);
  const toggleSelect = (id) => setSelectedIds((prev) => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });
  const selectedRows = rows.filter((r) => selectedIds.has(r.id));
  const selectedEmail = selectedRows.filter((r) => r.email).length;
  const selectedPhone = selectedRows.filter((r) => r.phone).length;
  const selectedForChannel = cChannel === "email" ? selectedEmail : selectedPhone;
  const selectRowForSend = (row) => fillSendArea(row);
  const sumWith = (key) => stats ? (stats[key] || 0) : 0;
  const totalCompanies = stats?.total || 0;

  const curatedFor = (ch) => ch === "whatsapp" || ch === "both" ? CURATED_MESSAGES : [];
  const tplFor = (ch) => (templates || []).filter((t) => { const tc = (t.channel || "email").toLowerCase(); return ch === "both" ? (tc === "email" || tc === "whatsapp") : tc === ch; });
  const visibleTemplates = tplFor(cChannel);
  const fillMsg = (raw, row) => String(raw || "").replaceAll("{name}", row?.contact_name || row?.company || "there").replaceAll("{company}", row?.company || "your business").replaceAll("{email}", row?.email || "").replaceAll("{phone}", row?.phone || "").replaceAll("{video}", DIWALI_REEL);
  const copyText = async (value) => { try { await navigator.clipboard.writeText(value || ""); onNotice({ type: "success", text: "Copied." }); } catch { onNotice({ type: "error", text: "Copy failed." }); } };
  const bucketStatus = (list) => { const b = { Reached: 0, Pending: 0, Invalid: 0, Other: 0 }; (list||[]).forEach((r) => { const s = String(r.call_status||"").toLowerCase(); if (/answer|done|sent|reach|connect|interested|converted|positive/.test(s)) b.Reached++; else if (!s || /pending|follow|later|call|new|na|n\/a/.test(s)) b.Pending++; else if (/invalid|wrong|bounce|dnd|closed|no\b/.test(s)) b.Invalid++; else b.Other++; }); return b; };
  const statusBuckets = bucketStatus(rows);
  const topDomains = Object.entries(stats?.by_domain || {}).slice(0, 5);
  const maxDomain = Math.max(1, ...topDomains.map(([, n]) => n));
  const bar = (value, max) => <span className="mini-bar"><i style={{ width: `${Math.max(4, Math.round((value / (max || 1)) * 100))}%` }} /></span>;
  const sendBoth = async () => {
    if (!selTemplate || selTemplate._curated) return onNotice({ type: "error", text: "Select a saved template for bulk send." });
    if (!selectedRows.length) return onNotice({ type: "error", text: "Select contacts." });
    const byCh = [["email", selectedRows.filter((r)=>r.email)],["whatsapp", selectedRows.filter((r)=>r.phone)]].filter(([,l])=>l.length);
    if (!byCh.length) return onNotice({ type: "error", text: "Selected contacts have no email/phone." });
    setCBusy(true);
    try {
      for (const [channel, list] of byCh) await request("/campaigns", { method: "POST", body: JSON.stringify({ name: `${cName} (${channel})`, channel, strategy: cStrategy, template_id: selTemplate.id, use_ai: useAi, image_url: attachImage || "", filter: { limit: list.length, contact_type: "marketing_companies", contact_ids: list.map((r)=>r.id), q: query, category: categoryFilter, call_status: statusFilter, funnel_stage: funnelStageFilter } }) });
      onNotice({ type: "success", text: `Queued ${byCh.map(([ch,l])=>`${l.length} ${ch}`).join(" + ")} for review.` }); loadCampaigns();
    } catch (e) { onNotice({ type: "error", text: e.message }); } finally { setCBusy(false); }
  };

  return (
    <div className="content outreach-compact">
      <div className="page-heading"><div><div className="section-kicker">OUTREACH ? TEMPLATES ? MARKETING</div><h2>Outreach &amp; marketing</h2><p className="muted">Channel-first send, curated templates, insights, videos, signals and events.</p></div>
        <div className="button-row"><button className="secondary-button" onClick={() => { load(); loadActivity(); loadCampaigns(); }}><RefreshCw size={16}/> Refresh</button><button className="secondary-button" onClick={syncFromGCS} disabled={busy}><Database size={16}/>{busy?"Syncing...":"Sync"}</button></div></div>
      <div className="outreach-tabs" role="tablist">{[["send","Send & templates"],["insights","Insights & stats"],["library","Videos & ERP"],["signals","Signal desk"],["events","Events"]].map(([id,label])=>(<button key={id} role="tab" aria-selected={mTab===id} className={`secondary-button ${mTab===id?"primary-button":""}`} onClick={()=>setMTab(id)}>{label}</button>))}</div>
      {mTab==="insights" && <><section className="panel studio-panel"><div className="panel-heading"><div><div className="section-kicker">MARKETING HIGH-LEVEL</div><h3>Exact details for sending</h3></div><span className="muted">{fmtNum(totalCompanies)} companies ? {fmtNum(sumWith("with_email"))} with email ? {fmtNum(sumWith("with_phone"))} with phone</span></div>
        <div className="marketing-stat-grid">{stats ? [["Companies",stats.total,100],["Name + email",sumWith("with_email"),totalCompanies?Math.round(sumWith("with_email")/totalCompanies*100):0],["Phone",sumWith("with_phone"),totalCompanies?Math.round(sumWith("with_phone")/totalCompanies*100):0],["Templates",templates.length,totalCompanies?Math.round(templates.length/totalCompanies*100):0],["Follow-ups due",sumWith("follow_up_due"),0],["With requirements",sumWith("with_requirements"),totalCompanies?Math.round(sumWith("with_requirements")/totalCompanies*100):0]].map(([label,value,pct])=>(<div className="marketing-stat" key={label}><small>{label}</small><b>{fmtNum(value)}</b><span>{pct}%</span></div>)) : <div className="marketing-stat"><small>Templates</small><b>{templates.length}</b></div>}</div>
        <div className="mini-charts"><div><b>Top domains</b>{topDomains.length?topDomains.map(([label,count])=>(<div key={label} className="mini-chart-row"><span>{label}</span>{bar(count,maxDomain)}<strong>{fmtNum(count)}</strong></div>)):<small className="muted">No domains.</small>}</div><div><b>Call status</b>{Object.entries(statusBuckets).map(([label,count])=>(<div key={label} className="mini-chart-row"><span>{label}</span>{bar(count,Math.max(1,...Object.values(statusBuckets)))}<strong>{fmtNum(count)}</strong></div>))}</div></div>
        <details className="marketing-breakdown"><summary>Domains ? call status ? categories</summary><div className="marketing-breakdown-grid"><div><b>Domains</b>{Object.entries(stats?.by_domain||{}).slice(0,12).map(([l,c])=><span key={l}>{l}<strong>{c}</strong></span>)}</div><div><b>Call status</b>{Object.entries(stats?.by_call_status||{}).map(([l,c])=><span key={l}>{l}<strong>{c}</strong></span>)}</div><div><b>Categories</b>{Object.entries(stats?.by_category||{}).slice(0,12).map(([l,c])=><span key={l}>{l}<strong>{c}</strong></span>)}</div></div></details></section>
      <section className="panel studio-panel"><div className="panel-heading"><div><div className="section-kicker">GOOGLE ANALYTICS SYNC</div><h3>Insights &amp; stats (city/country &amp; more)</h3></div><div className="button-row"><button className="secondary-button" onClick={loadGa} title="Reload cached insights"><RefreshCw size={14}/> Reload</button><button className="primary-button" onClick={()=>gaSync(false)} disabled={gaBusy}><Database size={14}/> {gaBusy?"Processing...":"GA Sync"}</button><button className="icon-button" title="Force reprocess all exports" onClick={()=>gaSync(true)} disabled={gaBusy}><RefreshCw size={14}/></button></div></div>
        {ga ? (<>
          <p className="muted">{ga.status === "no_new_files" ? (ga.message||"No new file detected.") : ga.data_available ? `${(ga.files||[]).length} file(s) ? ${(ga.rows||0).toLocaleString()} rows ? processed ${String(ga.synced_at||"").slice(0,10)}${ga.from_cache?" (cached)":""}` : (ga.message||"No analytics export processed yet ? press GA Sync.")}</p>
          {(ga.range?.from) && <div className="outreach-chip-row"><span className="outreach-chip">Period: {ga.range.from} ? {ga.range.to}</span>{ga.metric && <span className="outreach-chip">Weight: {ga.metric}</span>}</div>}
          <div className="marketing-stat-grid">{Object.entries(ga.stats||{}).slice(0,8).map(([k,v])=><div className="marketing-stat" key={k}><small>{k}</small><b>{typeof v === "number" ? v.toLocaleString() : String(v)}</b></div>)}</div>
          {Object.keys(ga.groups||{}).length ? <div className="mini-charts">{Object.entries(ga.groups).slice(0,6).map(([g,items]) => { const max = items?.[0]?.value || 1; return (<div key={g}><b>{g}</b>{items.slice(0,6).map((x) => (<div key={x.label} className="mini-chart-row"><span title={x.label}>{String(x.label).slice(0,18)}</span>{bar(x.value,max)}<strong>{x.value.toLocaleString()}<em className="muted"> {x.share}%</em></strong></div>))}</div>); })}</div> : (ga.data_available ? <small className="muted">No city/country dimensions in this export.</small> : null)}
          {(ga.insights||[]).length ? <details open className="marketing-breakdown"><summary>Auto insights</summary><div className="marketing-breakdown-grid"><div>{(ga.insights||[]).slice(0,12).map((x,i)=><span key={i}>{x}</span>)}</div></div></details> : null}
          {ga.warnings?.length ? <small className="muted">Warnings: {ga.warnings.slice(0,3).join("; ")}</small> : null}
          {Array.isArray(ga.sample)&&ga.sample[0] && <details className="marketing-breakdown"><summary>Sample fields ({(ga.files||[]).length} file{(ga.files||[]).length===1?"":"s"})</summary><div className="marketing-breakdown-grid"><div>{Object.keys(ga.sample[0]).slice(0,16).map((k)=><span key={k}>{k}</span>)}</div></div></details>}
        </>) : <p className="muted">Loading analytics?</p>}
      </section></>}
      {mTab==="library" && <MarketingLibrary onNotice={onNotice} orders={mOrders} videos={mVideos.length?mVideos:CHANNEL_VIDEOS} />}
      {mTab==="signals" && <MarketingSignals onNotice={onNotice} />}
      {mTab==="events" && <MarketingEvents onNotice={onNotice} />}
      {mTab==="send" && <div className="outreach-send-compact">
      <section className="panel outreach-send-top" aria-label="Send and progress">
        <div className="panel-heading"><div><div className="section-kicker">SEND ? PROGRESS</div><h3>Campaign send</h3></div>
          <div className="button-row"><select value={cChannel} onChange={(e)=>{setCChannel(e.target.value);setSelTemplate(null);}} aria-label="Channel"><option value="email">Email</option><option value="whatsapp">WhatsApp</option><option value="both">Both (email + WhatsApp)</option></select>
          <input className="campaign-name" value={cName} onChange={(e)=>setCName(e.target.value)} placeholder="Campaign name" />
          {selTemplate && selectedRows.length>0 ? (cChannel==="both"
            ? <button className="primary-button" onClick={sendBoth} disabled={cBusy}><Send size={15}/> {cBusy?"Working...":`Create campaigns (${selectedEmail}? ${selectedPhone}WA)`}</button>
            : <><button className="secondary-button" onClick={createSelectedCampaign} disabled={cBusy || selectedForChannel===0}>{cBusy?"Working...":`Send for review (${selectedForChannel})`}</button><button className="primary-button" onClick={()=>createCampaign(selectedRows,true)} disabled={cBusy || selectedForChannel===0}><Send size={15}/> {cBusy?"Working...":`Send now (${selectedForChannel})`}</button></>)
          : <button className="primary-button" disabled><Send size={15}/> Select template + contacts</button>}
          <button className="secondary-button" onClick={()=>setShowTplPicker(true)}><FileText size={14}/> {selTemplate ? "Change template" : "Choose template"}</button>
          {cDetail && <><button className="secondary-button" onClick={approveCampaign} disabled={cBusy||cDetail.status!=="pending_review"}>Approve</button><button className="secondary-button" onClick={sendCampaign} disabled={cBusy||cDetail.status!=="approved"}>Send approved</button><button className="icon-button" onClick={()=>openCampaign(cDetail.id)} title="Refresh"><RefreshCw size={14}/></button></>}</div></div>
        <div className="outreach-chip-row">
          <span className="outreach-chip"><b>Template:</b> {selTemplate ? <>{selTemplate.name} <button className="icon-button" style={{padding:0,marginLeft:4}} onClick={()=>setSelTemplate(null)} title="Clear">?</button></> : "none selected"}</span>
          <span className="outreach-chip"><b>Selected:</b> {selectedRows.length} / {fmtNum(totalCompanies)}</span>
          <span className="outreach-chip">{selectedEmail} email</span><span className="outreach-chip">{selectedPhone} phone</span><span className="outreach-chip">{selectedForChannel} reachable via {cChannel}</span>
          {cDetail && <><span className="outreach-chip"><b>{cDetail.status}</b></span><span className="outreach-chip">sent {cDetail.sent_count}/{cDetail.total}</span><span className="outreach-chip">viewed {cDetail.opened_count||0}</span><span className="outreach-chip">failed {cDetail.failed_count}</span><span className="outreach-chip">progress {cDetail.total?Math.round(((cDetail.sent_count+cDetail.failed_count)/cDetail.total)*100):0}%</span><button className="icon-button" title="Close progress" onClick={()=>setCDetail(null)}><X size={14}/></button></>}
        </div>
        {selectedRows.length>0 && <div className="outreach-chip-row" style={{marginTop:4}}><small className="muted">Contacts:</small>{selectedRows.slice(0,8).map((r)=>(<span key={r.id} className="contact-tag">{r.contact_name||r.company} <button className="icon-button" style={{padding:0}} onClick={()=>toggleSelect(r.id)}>?</button></span>))}{selectedRows.length>8 && <small className="muted">+{selectedRows.length-8} more</small>}</div>}
      </section>

      <div className="outreach-workspace">
        <section className="panel outreach-pane" aria-label="Templates">
          <div className="panel-heading"><div><div className="section-kicker">TEMPLATES</div><h3>Message windows</h3></div><button className="secondary-button" onClick={syncTemplates} disabled={cBusy}><Database size={14}/></button></div>
          <div className="studio-grid">
            {curatedFor(cChannel).map((m)=>(<article className="studio-card" key={m.id}><div className="studio-card-top"><span className="template-channel">curated</span><b>{m.title}</b></div><p className="studio-text">{fillMsg(m.text, selectedRows[0]||{}).slice(0,140)}</p><div className="button-row studio-actions"><button className="secondary-button" onClick={()=>copyText(fillMsg(m.text, selectedRows[0]||{}))}><Copy size={13}/></button>{cChannel!=="email" && <button className="primary-button" onClick={()=>window.open(whatsappHref(fillMsg(m.text, selectedRows[0]||{}), selectedRows[0]?.phone||""),"_blank","noopener")}><MessageCircle size={13}/></button>}</div></article>))}
            {visibleTemplates.map((tt)=>(<article className={`studio-card ${selTemplate?.id===tt.id?"tick-selected":""}`} key={tt.id} onClick={()=> (selTemplate?.id===tt.id?setSelTemplate(null):pickTemplate(tt))} role="button" tabIndex={0} onKeyDown={(e)=>{if(e.key==="Enter") (selTemplate?.id===tt.id?setSelTemplate(null):pickTemplate(tt));}}><div className="studio-card-top"><span className="template-channel">{tt.channel}</span><b>{tt.name}</b>{selTemplate?.id===tt.id && <span className="contact-tag">?</span>}</div><p className="studio-text">{tt.subject?<><b>{tt.subject}</b><br/></>:null}{htmlToText(tt.body).slice(0,120)}</p><div className="button-row studio-actions" onClick={(e)=>e.stopPropagation()}><button className="secondary-button" onClick={()=>setPreviewTemplate(tt)}><Eye size={13}/> View</button><button className={selTemplate?.id===tt.id?"primary-button":"secondary-button"} onClick={()=> (selTemplate?.id===tt.id?setSelTemplate(null):pickTemplate(tt))}>{selTemplate?.id===tt.id?"Selected":"Select"}</button></div></article>))}
            {!visibleTemplates.length && !curatedFor(cChannel).length && <small className="muted">No templates for {cChannel}.</small>}
          </div>
          <div className="panel-heading" style={{marginTop:12}}><div><div className="section-kicker">POSTERS / IMAGES</div><h3>Attach to WhatsApp &amp; Mail</h3></div><button className="secondary-button" onClick={()=>imgUploadRef.current&&imgUploadRef.current.click()} disabled={busy}><UploadCloud size={13}/> Upload</button></div>
          <input ref={imgUploadRef} type="file" accept="image/*" hidden onChange={uploadImageTemplate} />
          <div className="image-strip">
            {imageTemplates.map((img)=>(<button type="button" className={`image-tile ${attachImage===img.url?"tick-selected":""}`} key={img.path} onClick={()=>setAttachImage(attachImage===img.url?"":img.url)} title={img.name}>
              <img src={img.url} alt={img.name} loading="lazy" />
              <span>{img.name.replace(/\.[a-z]+$/i,"").slice(0,16)}</span>
            </button>))}
            {!imageTemplates.length && <small className="muted">No posters in sales-image-templates yet ? Upload one (goes to that GCS folder) or pick after GA/media sync.</small>}
          </div>
          {attachImage && <div className="outreach-chip-row" style={{marginTop:6}}><span className="contact-tag">Attached to send ? <button className="icon-button" style={{padding:0}} onClick={()=>setAttachImage("")}>?</button></span></div>}
        </section>

        <section className="panel outreach-pane" aria-label="Contacts">
          <div className="panel-heading"><div><div className="section-kicker">CONTACTS</div><h3>Select & act</h3></div><label style={{fontSize:12}}><input type="checkbox" checked={allVisibleSelected} onChange={toggleSelectAll}/> visible</label></div>
          <div className="source-tiles" aria-label="Contact source files">
            {sources.map((f)=>(<div className={`source-tile ${f.processed?"done":""}`} key={f.file} title={f.path||f.file}>
              <b>{f.short}</b><small>{f.size_mb?`${f.size_mb} MB ? `:""}{f.updated}{f.in_gcs?"":" ? local"}</small>
              <span className="contact-tag">{f.processed?`? ${f.rows_in_db} rows`:"not synced"}</span>
              {f.in_gcs && <button className="secondary-button" disabled={busy} onClick={()=>syncOne(f.path)}><Database size={12}/> Sync</button>}
            </div>))}
            {!sources.length && <small className="muted">No files in sales-contacts/ yet.</small>}
          </div>
          <div className="table-toolbar"><div className="search-field"><Search size={15}/><input value={query} onChange={(e)=>setQuery(e.target.value)} placeholder="Search"/></div>
            <select value={categoryFilter} onChange={(e)=>setCategoryFilter(e.target.value)}><option value="">Category</option>{categories.map((i)=><option key={i} value={i}>{i}</option>)}</select>
            <select value={statusFilter} onChange={(e)=>setStatusFilter(e.target.value)}><option value="">Status</option>{statuses.map((i)=><option key={i} value={i}>{i}</option>)}</select>
            <select value={limit} onChange={(e)=>setLimit(Number(e.target.value))}>{[25,50,100,250].map((s)=><option key={s} value={s}>{s}</option>)}</select></div>
          <div className="table-wrap"><table><thead><tr><th></th><th>Company / person</th><th>Status / last</th></tr></thead><tbody>
            {rows.map((row)=>{ const act=activity[row.id]; const msgText=fillMsg(selTemplate?htmlToText(selTemplate.body):"Hi from Kalika Enterprises", row) + (attachImage?`\n\n\u{1F5BC}\uFE0F ${attachImage}`:""); return (
              <tr key={row.id} className={selectedIds.has(row.id)?"tick-selected":""}>
                <td><input type="checkbox" checked={selectedIds.has(row.id)} onChange={()=>toggleSelect(row.id)}/></td>
                <td><b>{row.company}</b><br/><small className="muted">{row.contact_name||"-"} ? {row.email||"no email"}{row.phone?` ? ${row.phone}`:""}{row.source_file?` ? ${row.source_file.replace(/\.[a-z]+$/i,"").slice(0,18)}`:""}</small>
                  <div className="reach-actions" aria-label="Contact actions">{row.phone && <a className="secondary-button" href={`tel:${row.phone}`}>Call</a>}{row.phone && <a className="secondary-button" href={whatsappHref(msgText,row.phone)} target="_blank" rel="noreferrer">Msg</a>}{row.email && <a className="secondary-button" href={`mailto:${row.email}?subject=${encodeURIComponent(selTemplate?.subject||"Kalika Enterprises")}&body=${encodeURIComponent(msgText)}`}>Mail</a>}</div>
                  <div className="inline-edit">
                    <input value={editing[row.id]?.call_status ?? row.call_status ?? ""} onChange={(e)=>setEditing((p)=>({...p,[row.id]:{...(p[row.id]||{}),call_status:e.target.value}}))} onBlur={(e)=>{if(e.target.value!==row.call_status) updateField(row.id,"call_status",e.target.value);}} placeholder="Call comments" />
                    <input type="date" value={row.follow_up_date||""} onChange={(e)=>updateField(row.id,"follow_up_date",e.target.value)} />
                    <textarea rows={1} value={editing[row.id]?.requirements ?? row.requirements ?? ""} onChange={(e)=>setEditing((p)=>({...p,[row.id]:{...(p[row.id]||{}),requirements:e.target.value}}))} onBlur={(e)=>{if(e.target.value!==row.requirements) updateField(row.id,"requirements",e.target.value);}} placeholder="Requirements / discussion" />
                    <textarea rows={1} value={editing[row.id]?.next_action ?? row.next_action ?? ""} onChange={(e)=>setEditing((p)=>({...p,[row.id]:{...(p[row.id]||{}),next_action:e.target.value}}))} onBlur={(e)=>{if(e.target.value!==row.next_action) updateField(row.id,"next_action",e.target.value);}} placeholder="Follow-up msg / next action" />
                  </div>
                </td>
                <td><small>{(row.call_status||"pending").slice(0,18)}</small><br/>{act ? <span className="activity-badges"><span className="contact-tag">?{act.sent}</span><span className="contact-tag">??{act.opened||0}</span></span> : <small className="muted">?</small>}</td>
              </tr>); })}
            {!rows.length && <tr><td colSpan={3}><small className="muted">No contacts.</small></td></tr>}
          </tbody></table></div>
        </section>

        <section className="panel outreach-pane" aria-label="Campaign details">
          <div className="panel-heading"><div><div className="section-kicker">PROGRESS & DETAILS</div><h3>Sent / viewed</h3></div><button className="icon-button" onClick={loadCampaigns} title="Refresh"><RefreshCw size={14}/></button></div>
          {cDetail ? (<div>
            <div className="outreach-chip-row"><span className="contact-tag">{cDetail.name}</span><span className="contact-tag">{cDetail.status}</span><span className="contact-tag">{cDetail.channel}</span></div>
            <div className="marketing-stat-grid" style={{marginTop:6}}>{[["Total",cDetail.total],["Sent",cDetail.sent_count],["Viewed",cDetail.opened_count||0],["Failed",cDetail.failed_count],["Queued",Math.max(0,(cDetail.total||0)-(cDetail.sent_count||0)-(cDetail.failed_count||0))]].map(([l,v])=><div className="marketing-stat" key={l}><small>{l}</small><b>{fmtNum(v)}</b></div>)}</div>
            <div className="mini-chart-row" style={{margin:"6px 0"}}><span>Progress</span><span className="mini-bar"><i style={{width:`${cDetail.total?Math.round(((cDetail.sent_count+cDetail.failed_count)/cDetail.total)*100):0}%`}}/></span><strong>{cDetail.total?Math.round(((cDetail.sent_count+cDetail.failed_count)/cDetail.total)*100):0}%</strong></div>
            <small className="muted">Opened/viewed via tracking where supported; delivery ?received? not verifiable for all channels.</small>
            <div className="table-wrap" style={{marginTop:6}}><table><thead><tr><th>Contact</th><th>Status</th><th>Sent</th><th>Viewed</th></tr></thead><tbody>
              {(cDetail.messages||[]).slice(0,50).map((m)=>(<tr key={m.id}><td><small><b>{m.contact_name||m.contact_id}</b></small></td><td><span className="contact-tag">{m.status}</span></td><td><small>{m.sent_at?String(m.sent_at).slice(5,16).replace("T"," "):"?"}</small></td><td><small>{m.opened_at?String(m.opened_at).slice(5,16).replace("T"," "):(m.status==="opened"?"yes":"?")}</small></td></tr>))}
            </tbody></table></div>
          </div>) : <small className="muted">Create/approve/send a campaign to see progress, or click one below.</small>}
          <h4 style={{margin:"10px 0 4px"}}>History</h4>
          <div className="contact-list" role="list">{campaigns.slice(0,8).map((cmp)=>(<button key={cmp.id} className="contact-row" style={{width:"100%",textAlign:"left",border:0,background:"transparent",padding:"4px 0"}} onClick={()=>openCampaign(cmp.id)}><span className="contact-main"><b>{cmp.name}</b><small>{cmp.channel} ? sent {cmp.sent_count||0} ? viewed {cmp.opened_count||0} ? fail {cmp.failed_count||0}</small></span><span className="contact-tag">{cmp.status}</span></button>))}{!campaigns.length && <small className="muted">No campaigns.</small>}</div>
        </section>
      </div>
    </div>}

            {showTplPicker && (<div className="modal-overlay" onClick={()=>setShowTplPicker(false)}>
        <div className="modal-content template-picker" onClick={(e)=>e.stopPropagation()}>
          <div className="modal-header"><h2>Pick a template</h2>
            <div className="button-row"><select value={tplSort} onChange={(e)=>setTplSort(e.target.value)}><option value="recent">Recently added</option><option value="name">Name</option><option value="used">Most used</option></select><button className="icon-button" onClick={()=>setShowTplPicker(false)}><X size={20}/></button></div></div>
          <div className="modal-body">
            <div className="search-field"><Search size={15}/><input autoFocus value={tplSearch} onChange={(e)=>setTplSearch(e.target.value)} placeholder="Search templates?"/></div>
            {(() => {
              const q = tplSearch.toLowerCase();
              let list = (templates||[]).filter((tt)=>!q || String(tt.name||"").toLowerCase().includes(q) || String(tt.subject||"").toLowerCase().includes(q));
              if (cChannel!=="both") list = list.filter((tt)=>(tt.channel||"email")===cChannel);
              if (tplSort==="name") list = [...list].sort((a,b)=>String(a.name||"").localeCompare(String(b.name||"")));
              else if (tplSort==="used") list = [...list].sort((a,b)=>(b.used_count||0)-(a.used_count||0));
              else list = [...list].sort((a,b)=>String(b.updated_at||"").localeCompare(String(a.updated_at||"")));
              return list.map((tt)=>(
                <div className={`picker-row ${selTemplate?.id===tt.id?"tick-selected":""}`} key={tt.id}>
                  <div className="picker-main"><b>{tt.name}</b><small className="muted">{tt.channel} ? used {tt.used_count||0} ? {String(tt.updated_at||"").slice(0,10)}</small></div>
                  <div className="button-row">
                    <button className="secondary-button" onClick={()=>setPreviewTemplate(tt)}><Eye size={13}/> View</button>
                    <button className="secondary-button" onClick={()=>{ setEditTplId(editTplId===tt.id?null:tt.id); setTplEdit({ subject: tt.subject||"", body: htmlToText(tt.body) }); }}><FileText size={13}/> Edit</button>
                    <button className="primary-button" onClick={()=>{ pickTemplate(tt); setShowTplPicker(false); }}>{selTemplate?.id===tt.id?"Selected":"Select"}</button>
                  </div>
                  {editTplId===tt.id && <div className="picker-edit">
                    <input value={tplEdit.subject} onChange={(e)=>setTplEdit((x)=>({...x,subject:e.target.value}))} placeholder="Subject" />
                    <textarea rows={4} defaultValue={tplEdit.body} onChange={(e)=>setTplEdit((x)=>({...x,body:e.target.value}))} placeholder="Body" />
                    <div className="button-row"><button className="primary-button" onClick={async()=>{ try { await request(`/templates/${tt.id}`, { method: "PATCH", body: JSON.stringify({ subject: tplEdit.subject, body: tplEdit.body }) }); onNotice({ type:"success", text:"Template saved." }); setEditTplId(null); request("/templates").then((r)=>setTemplates(Array.isArray(r)?r:[])).catch(()=>{}); } catch (e) { onNotice({ type:"error", text: e.message }); } }}>Save</button></div>
                  </div>}
                </div>
              ));
            })()}
            {!(templates||[]).length && <small className="muted">No templates loaded ? use Sync templates.</small>}
          </div>
        </div>
      </div>)}
      {previewTemplate && (<div className="modal-overlay" onClick={()=>setPreviewTemplate(null)}><div className="modal-content template-preview-modal" onClick={(e)=>e.stopPropagation()}><div className="modal-header"><h2>{previewTemplate.name}</h2><button className="icon-button" onClick={()=>setPreviewTemplate(null)}><X size={20}/></button></div><div className="modal-body"><iframe srcDoc={previewTemplate.body} title="Template Preview" sandbox="allow-same-origin" style={{width:"100%",height:"420px",border:"1px solid #ddd",borderRadius:"8px",background:"white"}}/></div></div></div>)}
    </div>
  );
}

// ---------------------------------------------------------------- Templates
function Templates({ onNotice }) {
  const [templates, setTemplates] = useState([]);
  const [meta, setMeta] = useState(null);
  const [categoryFilter, setCategoryFilter] = useState("");
  const [query, setQuery] = useState("");
  const [sortBy, setSortBy] = useState("recent");
  const [previewTemplate, setPreviewTemplate] = useState(null);
  const [editTemplate, setEditTemplate] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [templatesData, metaData] = await Promise.all([
        request("/templates"),
        request("/templates/meta"),
      ]);
      setTemplates(templatesData);
      setMeta(metaData);
    } catch (error) {
      onNotice({ type: "error", text: error.message });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const syncFromGCS = async () => {
    setSyncing(true);
    try {
      const result = await request("/templates/sync-gcs", { method: "POST" });
      onNotice({ type: "success", text: result.message || `Synced ${result.synced} templates` });
      await load();
    } catch (error) {
      onNotice({ type: "error", text: error.message });
    } finally {
      setSyncing(false);
    }
  };

  const deleteTemplate = async (id) => {
    if (!window.confirm("Delete this template?")) return;
    try {
      await request(`/templates/${id}`, { method: "DELETE" });
      onNotice({ type: "success", text: "Template deleted" });
      await load();
    } catch (error) {
      onNotice({ type: "error", text: error.message });
    }
  };

  const updateTemplate = async (id, updates) => {
    try {
      await request(`/templates/${id}`, {
        method: "PATCH",
        body: JSON.stringify(updates),
      });
      onNotice({ type: "success", text: "Template updated" });
      setEditTemplate(null);
      await load();
    } catch (error) {
      onNotice({ type: "error", text: error.message });
    }
  };

  // Filter and sort templates
  let filteredTemplates = templates;
  if (query) {
    const needle = query.toLowerCase();
    filteredTemplates = filteredTemplates.filter((template) =>
      [template.name, template.subject, template.channel, template.body]
        .some((value) => String(value || "").toLowerCase().includes(needle))
    );
  }
  if (categoryFilter) {
    filteredTemplates = filteredTemplates.filter(t => t.channel === categoryFilter);
  }

  const sortedTemplates = [...filteredTemplates].sort((a, b) => {
    if (sortBy === "recent") {
      return new Date(b.updated_at) - new Date(a.updated_at);
    } else if (sortBy === "name") {
      return a.name.localeCompare(b.name);
    } else if (sortBy === "channel") {
      return a.channel.localeCompare(b.channel);
    }
    return 0;
  });

  // Group by category for expanded view
  const grouped = sortedTemplates.reduce((acc, template) => {
    const key = template.channel || "other";
    if (!acc[key]) acc[key] = [];
    acc[key].push(template);
    return acc;
  }, {});

  return (
    <div className="content">
      <div className="page-heading">
        <div>
          <div className="section-kicker">MESSAGE TEMPLATES</div>
          <h2>Templates</h2>
          <p className="muted">Manage HTML email templates synced from GCS. Preview, edit, and organize by category.</p>
        </div>
        <div className="button-row">
          <button className="secondary-button" onClick={load} disabled={loading}>
            <RefreshCw size={16} className={loading ? "spin" : ""} /> Refresh
          </button>
          <button className="primary-button" onClick={syncFromGCS} disabled={syncing}>
            <Database size={16} /> {syncing ? "Syncing..." : "Sync from GCS"}
          </button>
        </div>
      </div>

      <div className="panel" style={{ marginBottom: "20px" }}>
        <div className="table-toolbar">
          <div className="search-field">
            <Search size={17} />
            <input
              placeholder="Search name, subject or body..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)} aria-label="Filter by channel">
            <option value="">All channels</option>
            {Array.from(new Set(templates.map((template) => template.channel).filter(Boolean))).sort().map((channel) => <option key={channel} value={channel}>{channel}</option>)}
          </select>
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
            <option value="recent">Recent first</option>
            <option value="name">Name A-Z</option>
            <option value="channel">Category</option>
          </select>
          <span className="muted">{sortedTemplates.length} templates</span>
        </div>
      </div>

      {loading ? (
        <div className="loading-inline">
          <RefreshCw size={18} className="spin" /> Loading templates...
        </div>
      ) : (
        <div className="templates-grid">
          {Object.entries(grouped).map(([category, categoryTemplates]) => (
            <div key={category} className="template-category-section">
              <div className="template-category-header">
                <h3>{category.toUpperCase().replace("_", " ")} ({categoryTemplates.length})</h3>
              </div>
              <div className="template-cards">
                {categoryTemplates.map((template) => (
                  <div key={template.id} className="template-card">
                    <div className="template-card-header">
                      <div>
                        <div className="template-name">{template.name}</div>
                        <div className="template-meta">
                          <span className="template-channel">{template.channel}</span>
                          <span className="template-date">
                            {new Date(template.updated_at).toLocaleDateString()}
                          </span>
                        </div>
                      </div>
                      <div className="template-actions">
                        <button
                          className="icon-button"
                          onClick={() => setPreviewTemplate(template)}
                          title="Preview"
                        >
                          <Eye size={18} />
                        </button>
                        <button
                          className="icon-button"
                          onClick={() => setEditTemplate(template)}
                          title="Edit"
                        >
                          <Edit2 size={18} />
                        </button>
                        <button
                          className="icon-button danger"
                          onClick={() => deleteTemplate(template.id)}
                          title="Delete"
                        >
                          <Trash2 size={18} />
                        </button>
                      </div>
                    </div>
                    <div className="template-subject">{template.subject || "No subject"}</div>
                    <div className="template-preview">
                      {template.body.substring(0, 150)}...
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
          {Object.keys(grouped).length === 0 && (
            <div className="empty-state">
              <FileText size={22} />
              <p>No templates yet</p>
              <small>Sync from GCS to import HTML templates</small>
            </div>
          )}
        </div>
      )}

      {/* Preview Modal */}
      {previewTemplate && (
        <div className="modal-overlay" onClick={() => setPreviewTemplate(null)}>
          <div className="modal-content template-preview-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{previewTemplate.name}</h2>
              <button className="icon-button" onClick={() => setPreviewTemplate(null)}>
                <X size={20} />
              </button>
            </div>
            <div className="modal-body">
              <div className="template-preview-info">
                <div><strong>Channel:</strong> {previewTemplate.channel}</div>
                <div><strong>Subject:</strong> {previewTemplate.subject}</div>
                <div><strong>Updated:</strong> {new Date(previewTemplate.updated_at).toLocaleString()}</div>
              </div>
              <div className="template-html-preview">
                <iframe
                  srcDoc={previewTemplate.body}
                  title="Template Preview"
                  sandbox="allow-same-origin"
                  style={{ width: "100%", height: "500px", border: "1px solid #ddd", borderRadius: "8px", background: "white" }}
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Edit Modal */}
      {editTemplate && (
        <div className="modal-overlay" onClick={() => setEditTemplate(null)}>
          <div className="modal-content template-edit-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Edit Template</h2>
              <button className="icon-button" onClick={() => setEditTemplate(null)}>
                <X size={20} />
              </button>
            </div>
            <div className="modal-body">
              <div className="form-grid">
                <label>
                  Name
                  <input
                    value={editTemplate.name}
                    onChange={(e) => setEditTemplate({ ...editTemplate, name: e.target.value })}
                  />
                </label>
                <label>
                  Channel
                  <select
                    value={editTemplate.channel}
                    onChange={(e) => setEditTemplate({ ...editTemplate, channel: e.target.value })}
                  >
                    {meta?.channels?.map((ch) => (
                      <option key={ch} value={ch}>{ch}</option>
                    )) || (
                      <>
                        <option value="email">email</option>
                        <option value="whatsapp">whatsapp</option>
                        <option value="linkedin">linkedin</option>
                      </>
                    )}
                  </select>
                </label>
                <label>
                  Subject
                  <input
                    value={editTemplate.subject}
                    onChange={(e) => setEditTemplate({ ...editTemplate, subject: e.target.value })}
                  />
                </label>
              </div>
              <label style={{ marginTop: "16px", display: "block" }}>
                HTML Body
                <textarea
                  rows={20}
                  value={editTemplate.body}
                  onChange={(e) => setEditTemplate({ ...editTemplate, body: e.target.value })}
                  style={{ fontFamily: "monospace", fontSize: "12px" }}
                />
              </label>
              <div className="button-row" style={{ marginTop: "16px" }}>
                <button className="primary-button" onClick={() => updateTemplate(editTemplate.id, editTemplate)}>
                  Save Changes
                </button>
                <button className="secondary-button" onClick={() => setEditTemplate(null)}>
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export { CampaignManager };

// ---------------------------------------------------------------- Knowledge graph review (DEV / UAT)
export function KnowledgeGraphReview({ onNotice, user, config }) {
  const [graph, setGraph] = useState(null);
  const [summary, setSummary] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [feedback, setFeedback] = useState([]);
  const [statusFilter, setStatusFilter] = useState("pending");
  const [teamQueue, setTeamQueue] = useState(false);
  const [selectedNode, setSelectedNode] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState(null);
  const [correction, setCorrection] = useState("");
  const [rating, setRating] = useState(3);
  const [busy, setBusy] = useState(false);
  const isAdmin = (user?.email || "").toLowerCase() === "ai.solutions@kalisoftai.in" || (user?.role || "").toLowerCase() === "admin";

  const load = async () => {
    try {
      const [nextSummary, nextGraph, nextReviews, nextFeedback, uat] = await Promise.all([
        request("/knowledge-graph/summary"),
        request("/knowledge-graph"),
        request(`/knowledge-graph/reviews?status=${statusFilter}&limit=200${teamQueue && isAdmin ? "&team=true" : ""}`),
        request(`/knowledge-graph/feedback${teamQueue && isAdmin ? "?team=true" : ""}`),
        request("/ops/uat"),
      ]);
      setSummary({ ...nextSummary, uat });
      setGraph(nextGraph);
      setReviews(nextReviews.items || []);
      setFeedback(nextFeedback || []);
    } catch (error) { onNotice({ type: "error", text: error.message }); }
  };
  useEffect(() => { load(); }, [statusFilter, teamQueue]);

  const build = async () => {
    setBusy(true);
    try {
      const result = await request("/knowledge-graph/build", { method: "POST" });
      onNotice({ type: "success", text: `Graph snapshot ${result.version} built: ${result.stats.nodes} nodes, ${result.stats.edges} edges.` });
      await load();
    } catch (error) { onNotice({ type: "error", text: error.message }); }
    finally { setBusy(false); }
  };

  const decide = async (item, action) => {
    try {
      await request(`/knowledge-graph/reviews/${item.edge_key}?graph_owner_id=${item.graph_owner_id || 0}`, {
        method: "POST",
        body: JSON.stringify({ action, note: item.reviewNote || "" }),
      });
      onNotice({ type: "success", text: `Relationship ${action}ed.` });
      await load();
    } catch (error) { onNotice({ type: "error", text: error.message }); }
  };

  const ask = async (event) => {
    event.preventDefault();
    if (!question.trim()) return;
    setBusy(true);
    try {
      setAnswer(await request("/knowledge-graph/chat", {
        method: "POST",
        body: JSON.stringify({ question: question.trim(), selected_node: selectedNode }),
      }));
    } catch (error) { onNotice({ type: "error", text: error.message }); }
    finally { setBusy(false); }
  };

  const submitFeedback = async () => {
    if (!answer || !question.trim()) return;
    setBusy(true);
    try {
      await request("/knowledge-graph/feedback", {
        method: "POST",
        body: JSON.stringify({
          graph_version: answer.graph_version,
          question: question.trim(),
          answer: answer.reply,
          correction,
          rating,
        }),
      });
      setCorrection("");
      onNotice({ type: "success", text: "Feedback saved for human evaluation; it does not train a model automatically." });
      await load();
    } catch (error) { onNotice({ type: "error", text: error.message }); }
    finally { setBusy(false); }
  };

  const reviewFeedback = async (item, action) => {
    try {
      await request(`/knowledge-graph/feedback/${item.id}/review?graph_owner_id=${item.graph_owner_id || 0}`, {
        method: "POST",
        body: JSON.stringify({ action, note: "Reviewed in DEV/UAT knowledge graph workspace." }),
      });
      onNotice({ type: "success", text: `Feedback sample ${action}ed for evaluation.` });
      await load();
    } catch (error) { onNotice({ type: "error", text: error.message }); }
  };

  const nodes = graph?.nodes || [];
  const edges = graph?.edges || [];
  const nodeLabels = Object.fromEntries(nodes.map((node) => [node.id, node.label || node.id]));
  const visibleEdges = selectedNode
    ? edges.filter((edge) => edge.source === selectedNode || edge.target === selectedNode)
    : edges;

  return (
    <div className="content dash knowledge-graph-page">
      <div className="page-heading">
        <div><div className="section-kicker">{summary?.environment || config?.deploy_env || "DEV / UAT"} Â· REVIEW WORKSPACE</div><h2>Knowledge graph</h2><p className="muted">Explore normalized contacts, companies, mail and visit links. Suggested relationships stay pending until reviewed.</p></div>
        <div className="button-row">
          {isAdmin && <button className="secondary-button" onClick={() => request("/sync/all", { method: "POST" }).then(() => onNotice({ type: "success", text: "Source sync completed." })).then(load).catch((error) => onNotice({ type: "error", text: error.message }))} disabled={busy}><RefreshCw size={15} /> Sync sources</button>}
          <button className="primary-button" onClick={build} disabled={busy}><Activity size={15} className={busy ? "spin" : ""} /> {busy ? "Building..." : "Build snapshot"}</button>
        </div>
      </div>
      <div className="kg-environment-note"><ShieldCheck size={16} /><span><b>{summary?.environment || config?.deploy_env || "development"}</b> Â· {summary?.uat?.uat_active ? `UAT window active until ${summary.uat.enabled_until}` : "DEV / pre-production review"} Â· {summary?.storage || "snapshot not built"} Â· {summary?.generated_at ? `updated ${String(summary.generated_at).slice(0, 16).replace("T", " ")}` : "no snapshot yet"}</span></div>

      <div className="metric-grid kg-stats">
        <Metric icon={Building2} label="Nodes" value={summary?.stats?.nodes ?? 0} detail={Object.entries(summary?.stats?.nodes_by_kind || {}).map(([kind, count]) => `${count} ${kind}`).join(" Â· ") || "no data"} accent />
        <Metric icon={Link2} label="Relationships" value={summary?.stats?.edges ?? 0} detail={`${Object.keys(summary?.stats?.edges_by_relation || {}).length} relation types`} />
        <Metric icon={Clock} label="Needs review" value={summary?.pending_reviews ?? 0} detail="suggestions are not confirmed" accent />
        <Metric icon={Database} label="Sources" value={Object.keys(summary?.stats?.sources || {}).length} detail={Object.entries(summary?.stats?.sources || {}).map(([key, count]) => `${count} ${key.replaceAll("_", " ")}`).join(" Â· ") || "sync sources first"} />
      </div>

      <div className="two-column">
        <section className="panel">
          <div className="panel-heading"><div><div className="section-kicker">ENTITY NODES</div><h3>{nodes.length} nodes</h3></div><select value={selectedNode} onChange={(event) => setSelectedNode(event.target.value)} aria-label="Filter graph by node"><option value="">All nodes</option>{nodes.map((node) => <option key={node.id} value={node.id}>{node.kind}: {node.label}</option>)}</select></div>
          <div className="kg-node-list">
            {nodes.slice(0, 300).map((node) => <button className={`kg-node ${node.id === selectedNode ? "active" : ""}`} key={node.id} onClick={() => setSelectedNode(node.id === selectedNode ? "" : node.id)}>
              <span className="kg-kind">{node.kind}</span><b>{node.label}</b><small>{node.company || node.intent || node.funnel_stage || node.date || node.source || ""}</small>
            </button>)}
            {!nodes.length && <div className="empty-state"><Database size={22} /><p>No graph snapshot yet.</p><small>Sync available data, then build a snapshot.</small></div>}
          </div>
        </section>
        <section className="panel">
          <div className="panel-heading"><div><div className="section-kicker">RELATIONSHIPS</div><h3>{visibleEdges.length} edges</h3></div><span className="status-pill">{summary?.version || "not built"}</span></div>
          <div className="kg-edge-list">
            {visibleEdges.slice(0, 300).map((edge) => <article className="kg-edge" key={edge.id}>
              <div className="kg-edge-flow"><b>{nodeLabels[edge.source] || edge.source}</b><span>{edge.relation.replaceAll("_", " ")}</span><b>{nodeLabels[edge.target] || edge.target}</b></div>
              <div className="kg-edge-meta"><span className={`status-pill ${edge.review_status === "accepted" ? "approved" : edge.review_status === "rejected" ? "rejected" : ""}`}>{edge.review_status}</span><span>{Math.round((edge.confidence || 0) * 100)}% match</span></div>
              {edge.evidence && <small className="muted">{edge.evidence}</small>}
            </article>)}
            {!visibleEdges.length && <div className="empty-state"><Link2 size={22} /><p>No relationships yet.</p><small>Choose a node or build a snapshot.</small></div>}
          </div>
        </section>
      </div>

      <section className="panel" style={{ marginTop: 14 }}>
        <div className="panel-heading"><div><div className="section-kicker">HUMAN VALIDATION</div><h3>Suggested relationships</h3></div><div className="button-row">{isAdmin && <button className={`secondary-button ${teamQueue ? "active" : ""}`} onClick={() => setTeamQueue(!teamQueue)}><Users size={15} /> {teamQueue ? "Team queue" : "My queue"}</button>}<select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="pending">Pending</option><option value="accepted">Accepted</option><option value="rejected">Rejected</option></select></div></div>
        <div className="kg-review-list">
          {reviews.map((item) => <article className="kg-review" key={`${item.graph_owner_id}-${item.edge_key}`}>
            <div className="kg-edge-flow"><b>{item.source}</b><span>{item.relation.replaceAll("_", " ")}</span><b>{item.target}</b></div>
            <p>{item.evidence}</p><small className="muted">{Math.round(item.confidence * 100)}% similarity Â· {item.graph_version}{teamQueue ? ` Â· user ${item.graph_owner_id}` : ""}</small>
            {item.status === "pending" && <div className="button-row"><button className="primary-button" onClick={() => decide(item, "accept")}><Check size={15} /> Accept</button><button className="secondary-button danger-button" onClick={() => decide(item, "reject")}><X size={15} /> Reject</button></div>}
            {item.status !== "pending" && <span className={`status-pill ${item.status === "accepted" ? "approved" : "rejected"}`}>{item.status} by {item.reviewer}</span>}
          </article>)}
          {!reviews.length && <div className="empty-state"><Check size={22} /><p>No {statusFilter} relationships.</p></div>}
        </div>
      </section>

      <section className="panel" style={{ marginTop: 14 }}>
        <div className="panel-heading"><div><div className="section-kicker">GRAPH ASSISTANT</div><h3>Ask, verify, then give feedback</h3></div><Bot size={19} className="muted" /></div>
        <form onSubmit={ask} className="kg-chat-form"><select value={selectedNode} onChange={(event) => setSelectedNode(event.target.value)}><option value="">Whole graph</option>{nodes.map((node) => <option key={node.id} value={node.id}>{node.kind}: {node.label}</option>)}</select><textarea value={question} onChange={(event) => setQuestion(event.target.value)} rows={2} placeholder="Ask about a company, source, or relationship..." /><button className="primary-button" disabled={busy || !summary?.version}><Send size={15} /> {busy ? "Reviewing..." : "Ask about graph"}</button></form>
        {answer && <div className="kg-chat-answer"><div className="chat-head"><b>{answer.model} Â· {answer.provider}</b><small>{answer.cost_micros} micro-USD</small></div><p>{answer.reply}</p><div className="kg-feedback-form"><label>Rating<select value={rating} onChange={(event) => setRating(Number(event.target.value))}><option value={5}>Helpful</option><option value={4}>Mostly helpful</option><option value={3}>Needs review</option><option value={2}>Mostly incorrect</option><option value={1}>Incorrect</option></select></label><label>Correction / evidence<textarea rows={2} value={correction} onChange={(event) => setCorrection(event.target.value)} placeholder="Optional correction for human evaluation" /></label><button className="secondary-button" onClick={submitFeedback} disabled={busy}><MessageSquarePlus size={15} /> Submit feedback</button></div></div>}
        <small className="muted">Feedback is stored for human evaluation; it does not update model weights automatically.</small>
      </section>
      {!!feedback.length && <section className="panel" style={{ marginTop: 14 }}><div className="panel-heading"><div><div className="section-kicker">HUMAN-EVALUATED CHAT SAMPLES</div><h3>{feedback.length} recent sample(s)</h3></div><span className="status-pill">{teamQueue ? "team" : "mine"}</span></div><div className="kg-feedback-history-list">{feedback.slice(0, 20).map((item) => <article className="kg-review" key={`${item.graph_owner_id || user?.id}-${item.id}`}><div className="chat-head"><b>Rating {item.rating}/5 Â· {item.status}</b><small>{String(item.created_at).slice(0, 16).replace("T", " ")}{item.graph_owner_id ? ` Â· user ${item.graph_owner_id}` : ""}</small></div><p><b>Question:</b> {item.question}</p>{item.correction && <p><b>Human correction:</b> {item.correction}</p>}{item.review_note && <small className="muted">Reviewer note: {item.review_note}</small>}{isAdmin && item.status === "pending_evaluation" && <div className="button-row"><button className="primary-button" onClick={() => reviewFeedback(item, "accept")}><Check size={15} /> Accept sample</button><button className="secondary-button danger-button" onClick={() => reviewFeedback(item, "reject")}><X size={15} /> Reject</button></div>}</article>)}</div></section>}
    </div>
  );
}

// ---------------------------------------------------------------- Review hub
// Human-review console (ai.solutions admin): sync-all + 2h refresh status,
// subtask approvals with model confidence, and the issues log.
export function ReviewHub({ onNotice, user }) {
  const isAdmin = (user?.email || "").toLowerCase() === "ai.solutions@kalisoftai.in" || (user?.role || "").toLowerCase() === "admin";
  const [syncStatus, setSyncStatus] = useState(null);
  const [approvals, setApprovals] = useState({ pending: 0, items: [] });
  const [issues, setIssues] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    try {
      const [s, a] = await Promise.all([request("/sync/status"), request("/approvals")]);
      setSyncStatus(s); setApprovals(a); setError("");
      if (isAdmin) {
        try { setIssues(await request("/approvals/issues")); } catch { setIssues(null); }
      }
    } catch (err) { setError(err.message); }
  };
  useEffect(() => { load(); const t = setInterval(load, 2 * 60 * 60 * 1000); return () => clearInterval(t); }, []);

  const syncAll = async () => {
    setBusy(true);
    try {
      const result = await request("/sync/all", { method: "POST" });
      onNotice({ type: result.ok === false ? "error" : "success", text: result.ok === false ? "Sync finished with errors." : "All data synced from GCS." });
      await load();
    } catch (err) { onNotice({ type: "error", text: err.message }); }
    finally { setBusy(false); }
  };
  const generate = async () => {
    setBusy(true);
    try {
      const result = await request("/approvals/generate", { method: "POST" });
      onNotice({ type: "success", text: `${result.created} subtask(s) proposed for review.` });
      await load();
    } catch (err) { onNotice({ type: "error", text: err.message }); }
    finally { setBusy(false); }
  };
  const decide = async (id, action) => {
    try {
      await request(`/approvals/${id}/decide`, { method: "POST", body: JSON.stringify({ action }) });
      onNotice({ type: "success", text: `Subtask ${action}d.` });
      await load();
    } catch (err) { onNotice({ type: "error", text: err.message }); }
  };

  const jobs = syncStatus?.jobs || {};
  const pending = approvals.items.filter((i) => i.status === "pending");
  const decided = approvals.items.filter((i) => i.status !== "pending");

  return (
    <div className="content dash">
      <div className="page-heading">
        <div><div className="section-kicker">FUTURE SCOPE / HUMAN REVIEW</div><h2>Subtasks &amp; sync control</h2>
          <p className="muted">Cost-effective Gemma â†’ Gemini-Flash proposals stay pending until you accept them. Data auto-refreshes every {syncStatus?.refresh_interval_minutes || 120} minutes.</p></div>
        <div style={{ display: "flex", gap: 8 }}>
          {isAdmin && <button className="secondary-button" onClick={generate} disabled={busy}><Sparkles size={15} /> Propose subtasks</button>}
          {isAdmin && <button className="primary-button" onClick={syncAll} disabled={busy}><RefreshCw size={15} /> {busy ? "Syncingâ€¦" : "Sync all now"}</button>}
          <button className="secondary-button" onClick={load}><RefreshCw size={15} /> Refresh</button>
        </div>
      </div>
      {error && <div className="config-warning"><ShieldCheck size={18} /><span>{error}</span></div>}

      <section className="panel">
        <div className="panel-heading"><div><div className="section-kicker">DATA SYNC</div><h3>Last sync per source</h3></div><Database size={19} className="muted" /></div>
        <div className="table-wrap"><table><thead><tr><th>Source</th><th>Status</th><th>Finished</th></tr></thead><tbody>
          {Object.entries(jobs).map(([job, info]) => (
            <tr key={job}><td><b>{job.replace(/_/g, " ")}</b></td>
              <td><span className={`status-pill ${info.status === "ok" ? "approved" : info.status === "never" ? "" : "rejected"}`}>{info.status}</span></td>
              <td>{info.finished_at ? String(info.finished_at).slice(0, 19).replace("T", " ") : "â€”"}</td></tr>
          ))}
        </tbody></table></div>
      </section>

      <section className="panel">
        <div className="panel-heading"><div><div className="section-kicker">PENDING ACCEPTANCE</div><h3>{pending.length} subtask(s) awaiting review</h3></div><Sparkles size={19} className="muted" /></div>
        {!pending.length && <div className="empty-state"><Check size={22} /><p>No pending subtasks. Use "Propose subtasks" to generate refined tasks.</p></div>}
        {pending.map((item) => (
          <div className="panel form-panel" key={item.id} style={{ marginBottom: 12 }}>
            <div className="panel-heading"><div><div className="section-kicker">{item.area} Â· {item.source}</div><h3>{item.title}</h3></div>
              <span className="status-pill">{Math.round((item.confidence || 0) * 100)}% conf</span></div>
            {item.detail && <p className="muted">{item.detail}</p>}
            {isAdmin && <div style={{ display: "flex", gap: 8 }}>
              <button className="primary-button" onClick={() => decide(item.id, "approve")}><Check size={15} /> Accept</button>
              <button className="secondary-button" onClick={() => decide(item.id, "reject")}><X size={15} /> Reject</button>
            </div>}
          </div>
        ))}
      </section>

      {decided.length > 0 && <section className="panel">
        <div className="panel-heading"><div><div className="section-kicker">DECIDED</div><h3>Reviewed subtasks</h3></div><Clock size={19} className="muted" /></div>
        <div className="table-wrap"><table><thead><tr><th>Subtask</th><th>Confidence</th><th>Status</th><th>By</th></tr></thead><tbody>
          {decided.slice(0, 20).map((item) => (
            <tr key={item.id}><td><b>{item.title}</b><small className="muted"> {item.area}</small></td>
              <td>{Math.round((item.confidence || 0) * 100)}%</td>
              <td><span className={`status-pill ${item.status === "approved" ? "approved" : "rejected"}`}>{item.status}</span></td>
              <td>{item.decided_by || "â€”"}</td></tr>
          ))}
        </tbody></table></div>
      </section>}

      {isAdmin && issues && <section className="panel">
        <div className="panel-heading"><div><div className="section-kicker">ISSUES LOG (ai.solutions only)</div><h3>Sync &amp; audit errors</h3></div><ShieldCheck size={19} className="muted" /></div>
        <div className="table-wrap"><table><thead><tr><th>Type</th><th>Name</th><th>Status</th><th>Detail</th><th>When</th></tr></thead><tbody>
          {(issues.sync_failures || []).map((f) => (
            <tr key={`sync-${f.id}`}><td>sync</td><td><b>{f.job}</b></td><td><span className="status-pill rejected">{f.status}</span></td><td>{f.detail}</td><td>{f.finished_at ? String(f.finished_at).slice(0, 19).replace("T", " ") : "â€”"}</td></tr>
          ))}
          {(issues.audit_errors || []).map((e) => (
            <tr key={`audit-${e.id}`}><td>audit</td><td><b>{e.action}</b></td><td><span className="status-pill rejected">{e.status}</span></td><td>{e.resource_type}</td><td>{String(e.created_at).slice(0, 19).replace("T", " ")}</td></tr>
          ))}
          {!(issues.sync_failures || []).length && !(issues.audit_errors || []).length && (
            <tr><td colSpan={5}><div className="empty-state"><Check size={22} /><p>No issues recorded.</p></div></td></tr>
          )}
        </tbody></table></div>
      </section>}
    </div>
  );
}

