import React, { useEffect, useMemo, useState } from "react";
import {
  BarChart3, Check, CheckCircle, Clock, Database, Eye,   FileDown, Mail, MessageCircle,
  RefreshCw, Send, ShieldCheck, UploadCloud, Users, X,
} from "lucide-react";

const API = "/api/outreach-whatsapp";
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
    try { message = (await response.json()).detail || message; } catch { /* response may not be JSON */ }
    throw new Error(typeof message === "string" ? message : JSON.stringify(message));
  }
  return response.status === 204 ? null : response.json();
}

const emptyTemplate = { name: "", category: "general", body: "", variables: [] };

export function OutreachWhatsApp({ onNotice }) {
  const [status, setStatus] = useState(null);
  const [config, setConfig] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [rates, setRates] = useState([]);
  const [contacts, setContacts] = useState([]);
  const [pendingContacts, setPendingContacts] = useState([]);
  const [campaigns, setCampaigns] = useState([]);
  const [dashboard, setDashboard] = useState(null);
  const [templateForm, setTemplateForm] = useState(emptyTemplate);
  const [editingTemplate, setEditingTemplate] = useState(0);
  const [rateForm, setRateForm] = useState({ product_id: "", rate: "", effective_date: "", notes: "" });
  const [campaignForm, setCampaignForm] = useState({ name: "", template_id: "", rate_ids: [], contact_ids: [], segment: "" });
  const [previews, setPreviews] = useState([]);
  const [selectedCampaign, setSelectedCampaign] = useState(null);
  const [files, setFiles] = useState([]);
  const [busy, setBusy] = useState(false);

  const notifyError = (error) => onNotice?.({ type: "error", text: error.message || String(error) });
  const notifySuccess = (text) => onNotice?.({ type: "success", text });

  const loadAll = async () => {
    setBusy(true);
    try {
      const [s, t, r, c, p, camps, d, cfg] = await Promise.all([
        request("/status"),
        request("/templates"),
        request("/rates"),
        request("/contacts?approved_only=true&limit=500"),
        request("/contacts?approved_only=false&limit=500"),
        request("/campaigns"),
        request("/dashboard?days=30"),
        fetch("/api/config").then((response) => response.json()).catch(() => ({})),
      ]);
      setStatus(s);
      setConfig(cfg);
      setTemplates(t);
      setRates(r.items || []);
      setContacts(c);
      setPendingContacts(p.filter((row) => !row.marketing_approved));
      setCampaigns(camps);
      setDashboard(d);
      setCampaignForm((form) => ({ ...form, template_id: form.template_id || String(t.find((row) => row.status === "approved")?.id || "") }));
    } catch (error) {
      notifyError(error);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  const approvedTemplates = useMemo(() => templates.filter((row) => row.status === "approved"), [templates]);
  const approvedRates = useMemo(() => rates.filter((row) => row.status === "approved"), [rates]);
  const selectedRateIds = campaignForm.rate_ids.map(Number);
  const selectedContactIds = campaignForm.contact_ids.map(Number);

  const bootstrap = async () => {
    setBusy(true);
    try {
      const result = await request("/bootstrap", { method: "POST" });
      notifySuccess(`Seeded ${result.products_created} products, ${result.rates_created} rates and ${result.templates_created} templates`);
      await loadAll();
    } catch (error) {
      notifyError(error);
    } finally {
      setBusy(false);
    }
  };

  const saveTemplate = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      if (editingTemplate) {
        await request(`/templates/${editingTemplate}`, { method: "PATCH", body: JSON.stringify(templateForm) });
        notifySuccess("Template updated and returned to review");
      } else {
        await request("/templates", { method: "POST", body: JSON.stringify(templateForm) });
        notifySuccess("Template saved as draft");
      }
      setTemplateForm(emptyTemplate);
      setEditingTemplate(0);
      await loadAll();
    } catch (error) {
      notifyError(error);
    } finally {
      setBusy(false);
    }
  };

  const editTemplate = (row) => {
    setEditingTemplate(row.id);
    setTemplateForm({ name: row.name, category: row.category, body: row.body, variables: row.variables || [] });
  };

  const approveTemplate = async (id) => {
    try {
      await request(`/templates/${id}/approve`, { method: "POST" });
      notifySuccess("Template approved");
      await loadAll();
    } catch (error) {
      notifyError(error);
    }
  };

  const previewTemplate = async (templateId) => {
    setBusy(true);
    try {
      const result = await request("/templates/preview", {
        method: "POST",
        body: JSON.stringify({
          template_id: templateId,
          rate_ids: selectedRateIds,
          contact_ids: selectedContactIds.slice(0, 10),
          limit: 10,
        }),
      });
      setPreviews(result.previews || []);
    } catch (error) {
      notifyError(error);
    } finally {
      setBusy(false);
    }
  };

  const submitRate = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      await request("/rates", {
        method: "POST",
        body: JSON.stringify({
          product_id: Number(rateForm.product_id),
          rate: Number(rateForm.rate),
          effective_date: rateForm.effective_date,
          notes: rateForm.notes,
        }),
      });
      setRateForm({ product_id: "", rate: "", effective_date: "", notes: "" });
      notifySuccess("Rate submitted for approval");
      await loadAll();
    } catch (error) {
      notifyError(error);
    } finally {
      setBusy(false);
    }
  };

  const reviewRate = async (id, decision) => {
    try {
      await request(`/rates/${id}/review`, { method: "POST", body: JSON.stringify({ decision }) });
      notifySuccess(`Rate ${decision}`);
      await loadAll();
    } catch (error) {
      notifyError(error);
    }
  };

  const approveContact = async (id) => {
    try {
      await request(`/contacts/${id}/approve`, { method: "POST" });
      notifySuccess("Contact approved for marketing");
      await loadAll();
    } catch (error) {
      notifyError(error);
    }
  };

  const toggleId = (key, id) => {
    setCampaignForm((form) => {
      const values = form[key].map(Number);
      return {
        ...form,
        [key]: (values.includes(id) ? values.filter((value) => value !== id) : [...values, id]).map(String),
      };
    });
  };

  const createCampaign = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      const campaign = await request("/campaigns", {
        method: "POST",
        body: JSON.stringify({
          ...campaignForm,
          template_id: Number(campaignForm.template_id),
          rate_ids: selectedRateIds,
          contact_ids: selectedContactIds,
        }),
      });
      notifySuccess(`Campaign created with ${campaign.total} recipients`);
      setSelectedCampaign(await request(`/campaigns/${campaign.id}`));
      await loadAll();
    } catch (error) {
      notifyError(error);
    } finally {
      setBusy(false);
    }
  };

  const campaignAction = async (id, action) => {
    setBusy(true);
    try {
      const result = await request(`/campaigns/${id}/${action}`, { method: "POST" });
      notifySuccess(action === "approve" ? "Campaign approved" : `Sent ${result.sent}, failed ${result.failed}`);
      setSelectedCampaign(await request(`/campaigns/${id}`));
      await loadAll();
    } catch (error) {
      notifyError(error);
    } finally {
      setBusy(false);
    }
  };

  const importFiles = async (event) => {
    event.preventDefault();
    if (!files.length) {
      notifyError(new Error("Choose one or more ZIP/PDF files"));
      return;
    }
    setBusy(true);
    try {
      const body = new FormData();
      files.forEach((file) => body.append("files", file));
      const result = await request("/import/sales-data", { method: "POST", body });
      notifySuccess(`Imported ${result.created} new and ${result.updated} existing contacts`);
      setFiles([]);
      await loadAll();
    } catch (error) {
      notifyError(error);
    } finally {
      setBusy(false);
    }
  };

  const totals = dashboard?.totals || {};
  const products = Array.from(new Map(approvedRates.map((rate) => [rate.product_id, rate.product_name])).entries());

  return (
    <section className="panel studio-panel outreach-whatsapp">
      <div className="panel-heading">
        <div>
          <div className="section-kicker">OUTREACH / WHATSAPP AUTOMATION</div>
          <h3>Rate-driven smart campaigns</h3>
          <p className="muted">Import sales chats and catalogues, approve contacts and rates, review personalised messages, then send with link tracking.</p>
        </div>
        <div className="button-row">
          <button className="secondary-button" onClick={loadAll} disabled={busy}><RefreshCw size={14}/> Refresh</button>
          <button className="primary-button" onClick={bootstrap} disabled={busy}><SparklesIcon/> Bootstrap samples</button>
        </div>
      </div>

      <div className="outreach-chip-row">
        <span className="outreach-chip"><MessageCircle size={13}/> WhatsApp {status?.enabled ? "enabled" : "disabled"}</span>
        <span className="outreach-chip"><Database size={13}/> Gateway {status?.gateway?.available ? "online" : "offline"}</span>
        <span className="outreach-chip"><CheckCircle size={13}/> {templates.length} templates</span>
        <span className="outreach-chip"><ShieldCheck size={13}/> {pendingContacts.length} contacts awaiting approval</span>
        <span className="outreach-chip"><CheckCircle size={13}/> SSO {config?.google_signin_configured ? "ready" : "not configured"}</span>
        <span className="outreach-chip"><Mail size={13}/> Mail {config?.mail_sending_configured ? "ready" : "not configured"}</span>
      </div>

      <div className="marketing-stat-grid wa-stat-grid">
        <div className="marketing-stat"><small>Sent</small><b>{totals.sent || 0}</b></div>
        <div className="marketing-stat"><small>Delivered</small><b>{totals.delivered || 0}</b><span>{dashboard?.rates?.delivery_rate || 0}%</span></div>
        <div className="marketing-stat"><small>Read</small><b>{totals.read || 0}</b><span>{dashboard?.rates?.read_rate || 0}%</span></div>
        <div className="marketing-stat"><small>Failed</small><b>{totals.failed || 0}</b></div>
        <div className="marketing-stat"><small>Link clicks</small><b>{totals.link_clicks || 0}</b><span>{dashboard?.rates?.click_rate || 0}%</span></div>
        <div className="marketing-stat"><small>Catalogue opens</small><b>{totals.catalog_downloads || 0}</b><span>{dashboard?.rates?.catalog_open_rate || 0}%</span></div>
        <div className="marketing-stat"><small>Landing time</small><b>{totals.landing_seconds || 0}s</b></div>
      </div>

      <div className="wa-grid">
        <div className="wa-card">
          <div className="panel-heading"><div><div className="section-kicker">SALES DATA</div><h4>Import chats &amp; catalogues</h4></div></div>
          <form onSubmit={importFiles}>
            <input
              type="file"
              multiple
              accept=".zip,.pdf,.xlsx,.xls,.csv,.json,.vcf"
              onChange={(event) => setFiles(Array.from(event.target.files || []))}
            />
            <p className="muted">ZIP exports and PDF catalogues are stored as unapproved sources until a person reviews them.</p>
            <button className="primary-button" disabled={busy}><UploadCloud size={14}/> Import sales data</button>
          </form>
        </div>

        <div className="wa-card">
          <div className="panel-heading"><div><div className="section-kicker">DAILY RATES</div><h4>Submit a rate</h4></div></div>
          <form onSubmit={submitRate} className="wa-form">
            <label>Product
              <select value={rateForm.product_id} onChange={(event) => setRateForm({ ...rateForm, product_id: event.target.value })} required>
                <option value="">Select product</option>
                {products.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
                {rates.map((rate) => <option key={`all-${rate.id}`} value={rate.product_id}>{rate.product_name || `Product ${rate.product_id}`}</option>)}
              </select>
            </label>
            <label>Rate (INR / kg)<input type="number" min="1" step="0.01" value={rateForm.rate} onChange={(event) => setRateForm({ ...rateForm, rate: event.target.value })} required /></label>
            <label>Effective date<input type="date" value={rateForm.effective_date} onChange={(event) => setRateForm({ ...rateForm, effective_date: event.target.value })} /></label>
            <label>Notes<input value={rateForm.notes} onChange={(event) => setRateForm({ ...rateForm, notes: event.target.value })} /></label>
            <button className="primary-button" disabled={busy}><Send size={14}/> Submit for approval</button>
          </form>
          <div className="wa-list">
            {rates.slice(0, 12).map((rate) => (
              <div key={rate.id} className="wa-row">
                <span><b>{rate.product_name || `Product ${rate.product_id}`}</b><small>₹{rate.rate}/{rate.unit} · {rate.effective_date} · {rate.status}</small></span>
                {rate.status === "pending" && <span className="button-row"><button className="secondary-button" onClick={() => reviewRate(rate.id, "approved")}>Approve</button><button className="secondary-button" onClick={() => reviewRate(rate.id, "rejected")}>Reject</button></span>}
              </div>
            ))}
            {!rates.length && <small className="muted">No rates yet. Bootstrap samples or submit a rate.</small>}
          </div>
        </div>

        <div className="wa-card">
          <div className="panel-heading"><div><div className="section-kicker">SMART TEMPLATES</div><h4>Template studio</h4></div></div>
          <form onSubmit={saveTemplate} className="wa-form">
            <label>Name<input value={templateForm.name} onChange={(event) => setTemplateForm({ ...templateForm, name: event.target.value })} required /></label>
            <label>Category<input value={templateForm.category} onChange={(event) => setTemplateForm({ ...templateForm, category: event.target.value })} /></label>
            <label>Message body<textarea rows="6" value={templateForm.body} onChange={(event) => setTemplateForm({ ...templateForm, body: event.target.value })} placeholder="Namaste {name} ji, today's rate for {product} is {rate}. Catalogue: {catalog_url}" required /></label>
            <div className="button-row">
              <button className="primary-button" disabled={busy}><Check size={14}/> {editingTemplate ? "Update" : "Save draft"}</button>
              {editingTemplate && <button type="button" className="secondary-button" onClick={() => { setEditingTemplate(0); setTemplateForm(emptyTemplate); }}>Cancel</button>}
            </div>
          </form>
          <div className="wa-list">
            {templates.map((template) => (
              <div key={template.id} className="wa-row">
                <span><b>{template.name}</b><small>{template.status} · v{template.version} · {template.category}</small></span>
                <span className="button-row">
                  <button className="secondary-button" onClick={() => editTemplate(template)}><EditIcon/></button>
                  <button className="secondary-button" onClick={() => previewTemplate(template.id)}><Eye size={14}/></button>
                  {template.status !== "approved" && <button className="secondary-button" onClick={() => approveTemplate(template.id)}>Approve</button>}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="wa-card">
          <div className="panel-heading"><div><div className="section-kicker">CONTACTS</div><h4>Marketing approvals</h4></div></div>
          <div className="wa-list">
            {pendingContacts.map((contact) => (
              <div key={`pending-${contact.id}`} className="wa-row">
                <span><b>{contact.company}</b><small>{contact.phone || "No phone"} · {contact.segment} · {String(contact.source_reference || "").slice(0, 60)}</small></span>
                <button className="secondary-button" onClick={() => approveContact(contact.id)}>Approve</button>
              </div>
            ))}
            {!pendingContacts.length && <small className="muted">All imported contacts are reviewed.</small>}
            <div className="wa-subhead"><Users size={14}/> {contacts.length} approved contacts</div>
            {contacts.slice(0, 8).map((contact) => (
              <div key={contact.id} className="wa-row">
                <span><b>{contact.company}</b><small>{contact.name || "No name"} · {contact.phone || "No phone"} · {contact.segment}</small></span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="wa-grid wa-grid-bottom">
        <div className="wa-card">
          <div className="panel-heading"><div><div className="section-kicker">CAMPAIGN BUILDER</div><h4>Review before sending</h4></div></div>
          <form onSubmit={createCampaign} className="wa-form">
            <label>Campaign name<input value={campaignForm.name} onChange={(event) => setCampaignForm({ ...campaignForm, name: event.target.value })} required /></label>
            <label>Approved template
              <select value={campaignForm.template_id} onChange={(event) => setCampaignForm({ ...campaignForm, template_id: event.target.value })} required>
                <option value="">Select template</option>
                {approvedTemplates.map((template) => <option key={template.id} value={template.id}>{template.name}</option>)}
              </select>
            </label>
            <label>Segment override
              <select value={campaignForm.segment} onChange={(event) => setCampaignForm({ ...campaignForm, segment: event.target.value })}>
                <option value="">All approved contacts</option>
                <option value="hot">Hot</option>
                <option value="follow_up">Follow-up</option>
                <option value="leads">Leads</option>
              </select>
            </label>
            <div>
              <b>Rates in message</b>
              <div className="wa-checks">
                {approvedRates.map((rate) => (
                  <label key={rate.id}><input type="checkbox" checked={selectedRateIds.includes(rate.id)} onChange={() => toggleId("rate_ids", rate.id)} /> {rate.product_name} ₹{rate.rate}/{rate.unit}</label>
                ))}
                {!approvedRates.length && <small className="muted">No approved rates.</small>}
              </div>
            </div>
            <div>
              <b>Recipients</b>
              <div className="wa-checks wa-checks-scroll">
                {contacts.map((contact) => (
                  <label key={contact.id}><input type="checkbox" checked={selectedContactIds.includes(contact.id)} onChange={() => toggleId("contact_ids", contact.id)} /> {contact.company}</label>
                ))}
                {!contacts.length && <small className="muted">No approved contacts.</small>}
              </div>
            </div>
            <button className="primary-button" disabled={busy}><Send size={14}/> Build campaign</button>
          </form>

          {selectedCampaign && (
            <div className="wa-campaign">
              <div className="wa-subhead"><BarChart3 size={14}/> {selectedCampaign.name} · {selectedCampaign.status}</div>
              <div className="button-row">
                {selectedCampaign.status === "pending_review" && <button className="primary-button" onClick={() => campaignAction(selectedCampaign.id, "approve")}>Approve campaign</button>}
                {selectedCampaign.status === "approved" && <button className="primary-button" onClick={() => campaignAction(selectedCampaign.id, "send")}>Send WhatsApp</button>}
              </div>
              {(selectedCampaign.messages || []).slice(0, 5).map((message) => (
                <details key={message.id} className="wa-message">
                  <summary>{message.company || message.name} · {message.status}</summary>
                  <pre>{message.rendered_body}</pre>
                </details>
              ))}
            </div>
          )}
        </div>

        <div className="wa-card">
          <div className="panel-heading"><div><div className="section-kicker">ENGAGEMENT</div><h4>Contact-wise response</h4></div></div>
          <div className="wa-list">
            {(dashboard?.contacts || []).map((row) => (
              <div key={row.contact_id} className="wa-row">
                <span><b>{row.company || row.name || `Contact ${row.contact_id}`}</b><small>{row.phone || "No phone"} · read {row.read} · clicks {row.clicks} · {Math.round(row.engagement_ms / 1000)}s</small></span>
                {row.failed ? <X size={14}/> : row.read ? <CheckCircle size={14}/> : <Clock size={14}/>}
              </div>
            ))}
            {!(dashboard?.contacts || []).length && <small className="muted">No engagement yet.</small>}
          </div>
          <div className="wa-subhead"><FileDown size={14}/> Campaigns</div>
          <div className="wa-list">
            {campaigns.map((campaign) => (
              <div key={campaign.id} className="wa-row">
                <span><b>{campaign.name}</b><small>{campaign.status} · {campaign.sent_count}/{campaign.total} sent · {campaign.read_count} read</small></span>
                <button className="secondary-button" onClick={async () => setSelectedCampaign(await request(`/campaigns/${campaign.id}`))}>Open</button>
              </div>
            ))}
            {!campaigns.length && <small className="muted">No campaigns yet.</small>}
          </div>
        </div>
      </div>

      {!!previews.length && (
        <div className="wa-card wa-previews">
          <div className="panel-heading"><div><div className="section-kicker">PREVIEW</div><h4>Personalised messages</h4></div><button className="secondary-button" onClick={() => setPreviews([])}><X size={14}/> Close</button></div>
          {previews.map((preview) => (
            <details key={`${preview.contact_id}-${preview.name}`} className="wa-message" open={previews.length === 1}>
              <summary>{preview.company}</summary>
              <pre>{preview.body}</pre>
            </details>
          ))}
        </div>
      )}
    </section>
  );
}

function SparklesIcon() {
  return <Check size={14}/>;
}

function EditIcon() {
  return <span aria-hidden="true">✎</span>;
}
