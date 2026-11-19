import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  BarChart3, Camera, Check, Copy, FileUp, Film, RefreshCw, ScanLine, Send, Settings2, Sparkles, TrendingUp, X,
} from "lucide-react";

const API = "/api";
const readToken = () => sessionStorage.getItem("sales_token") || "";

const DEFAULT_TOGGLES = {
  whatsapp_auto_send_enabled: false,
  whatsapp_daily_hard_cap: 49,
  human_review_required: true,
  erp_auto_followup_trigger: true,
  barcode_mobile_scan_enabled: true,
  youtube_free_tier_cron_enabled: true,
  sales_pitch_kpi_overlay: true,
};

const EMPTY_SCAN = {
  barcode: "",
  sku: "STRETCH-FILM-23MIC",
  net_weight_kg: "25",
  customer_name: "",
  customer_email: "",
  customer_whatsapp: "",
  trigger_followup: true,
};

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

async function copyText(text) {
  if (!text) return;
  await navigator.clipboard.writeText(text);
}

function Switch({ checked, disabled, onChange }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={Boolean(checked)}
      className={`so-switch ${checked ? "on" : ""}`}
      disabled={disabled}
      onClick={() => onChange(!checked)}
    >
      <span />
    </button>
  );
}

function ToggleRow({ label, hint, checked, disabled, onChange }) {
  return (
    <div className="so-toggle-row">
      <div><b>{label}</b><small>{hint}</small></div>
      <Switch checked={checked} disabled={disabled} onChange={onChange} />
    </div>
  );
}

export function SalesOpsStudio({ onNotice, user }) {
  const isAdmin = (user?.email || "").toLowerCase() === "ai.solutions@kalisoftai.in" || (user?.role || "").toLowerCase() === "admin";
  const [tab, setTab] = useState("controls");
  const [toggles, setToggles] = useState(DEFAULT_TOGGLES);
  const [counters, setCounters] = useState({ date: "", whatsapp_sent: 0, yt_quota_used: 0 });
  const [scans, setScans] = useState([]);
  const [trends, setTrends] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [scan, setScan] = useState(EMPTY_SCAN);
  const [scanModal, setScanModal] = useState(false);
  const [camera, setCamera] = useState({ active: false, status: "" });
  const [keywords, setKeywords] = useState("industrial stretch film manufacturing\nVCI anti corrosion bags\nstretch film extrusion plant");
  const [studio, setStudio] = useState({
    prompt_text: "Create a 25s high-contrast industrial motion-graphics video for Kalika Enterprises showing stretch film extrusion, barcode weight lock and verified scale.",
    model_choice: "local_gemma_4b",
    template_path: "sales-crm/marketing-videos/Templates/",
    aspect_ratio: "16:9",
  });
  const [refined, setRefined] = useState(null);
  const [dispatch, setDispatch] = useState({
    contact_name: "",
    company_name: "",
    phone: "",
    email: "",
    catalog_url: "",
    channels: ["email", "whatsapp"],
  });
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const timerRef = useRef(null);

  const notify = (text, type = "ok") => {
    setNotice(text);
    if (onNotice) onNotice({ type, text });
  };

  const loadAll = useCallback(async () => {
    const results = await Promise.allSettled([
      isAdmin ? request("/v1/sales-ops/admin/toggles") : Promise.resolve(null),
      request("/v1/sales-ops/youtube/trends?limit=20"),
      request("/v1/studio/templates"),
      request("/v1/sales-ops/erp/barcode-scans?limit=20"),
    ]);
    if (results[0].status === "fulfilled" && results[0].value) {
      setToggles(results[0].value.toggles || DEFAULT_TOGGLES);
      setCounters(results[0].value.daily_counters || counters);
    }
    if (results[1].status === "fulfilled") setTrends(results[1].value.items || []);
    if (results[2].status === "fulfilled") setTemplates(results[2].value.items || []);
    if (results[3].status === "fulfilled") setScans(results[3].value.items || []);
  }, [isAdmin]);

  useEffect(() => { loadAll().catch(() => {}); }, [loadAll]);
  useEffect(() => {
    if (!notice) return undefined;
    const timer = setTimeout(() => setNotice(""), 4200);
    return () => clearTimeout(timer);
  }, [notice]);

  const stopCamera = useCallback(() => {
    if (timerRef.current) window.clearTimeout(timerRef.current);
    timerRef.current = null;
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    setCamera({ active: false, status: "" });
  }, []);

  useEffect(() => () => stopCamera(), [stopCamera]);

  const startScanner = async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setScanModal(true);
      setCamera({ active: false, status: "Camera API unavailable on this device. Enter the barcode manually." });
      return;
    }
    setBusy("camera");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      streamRef.current = stream;
      setScanModal(true);
      setCamera({ active: true, status: "Camera active. Point it at a barcode." });
      window.setTimeout(() => {
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.play().catch(() => {});
        }
      }, 0);
      const Detector = window.BarcodeDetector;
      if (!Detector) {
        setCamera({ active: true, status: "Camera active. BarcodeDetector is unavailable; enter the code manually." });
        return;
      }
      const detector = new Detector({ formats: ["code_128", "code_39", "ean_13", "qr_code"] });
      const tick = async () => {
        if (!streamRef.current || !videoRef.current) return;
        try {
          const codes = await detector.detect(videoRef.current);
          if (codes.length) {
            setScan((current) => ({ ...current, barcode: codes[0].rawValue }));
            setCamera({ active: true, status: `Detected ${codes[0].rawValue}` });
            stopCamera();
            return;
          }
        } catch { /* detector may fail while the camera focuses */ }
        timerRef.current = window.setTimeout(tick, 350);
      };
      tick();
    } catch (error) {
      setScanModal(true);
      setCamera({ active: false, status: `Camera unavailable: ${error.message}` });
    } finally {
      setBusy("");
    }
  };

  const patchToggle = async (name, value) => {
    setBusy(`toggle:${name}`);
    const previous = toggles;
    setToggles((current) => ({ ...current, [name]: value }));
    try {
      const result = await request("/v1/sales-ops/admin/toggles", {
        method: "PATCH",
        body: JSON.stringify({ [name]: value }),
      });
      setToggles(result.toggles);
      setCounters(result.daily_counters || counters);
      notify(`${name.replaceAll("_", " ")} updated`);
    } catch (error) {
      setToggles(previous);
      notify(error.message, "error");
    } finally {
      setBusy("");
    }
  };

  const queueScan = async (event) => {
    event.preventDefault();
    if (!scan.barcode.trim()) { notify("Barcode is required", "error"); return; }
    setBusy("scan");
    try {
      const result = await request("/v1/sales-ops/erp/mobile-barcode-scan", {
        method: "POST",
        body: JSON.stringify({ ...scan, net_weight_kg: Number(scan.net_weight_kg) }),
      });
      notify(`Scan recorded (${result.status})`);
      setScan(EMPTY_SCAN);
      setScanModal(false);
      await loadAll();
    } catch (error) {
      notify(error.message, "error");
    } finally {
      setBusy("");
    }
  };

  const refine = async () => {
    setBusy("refine");
    try {
      const result = await request("/v1/studio/refine-and-generate", {
        method: "POST",
        body: JSON.stringify(studio),
      });
      setRefined(result);
      notify(`Prompt refined via ${result.source_mode}`);
      await loadAll();
    } catch (error) {
      notify(error.message, "error");
    } finally {
      setBusy("");
    }
  };

  const uploadAsset = async (file) => {
    if (!file) return;
    if (!isAdmin) { notify("Admin access is required for GCS uploads", "error"); return; }
    setBusy("upload");
    try {
      const form = new FormData();
      form.append("file", file);
      const result = await request("/v1/studio/upload", { method: "POST", body: form });
      setStudio((current) => ({ ...current, template_path: result.gcs_uri }));
      notify(`Uploaded ${result.path}`);
      await loadAll();
    } catch (error) {
      notify(error.message, "error");
    } finally {
      setBusy("");
    }
  };

  const discover = async () => {
    setBusy("discover");
    try {
      const list = keywords.split("\n").map((item) => item.trim()).filter(Boolean);
      const result = await request("/v1/sales-ops/youtube/discover", {
        method: "POST",
        body: JSON.stringify({ keywords: list, max_results: 8 }),
      });
      setTrends(result.signals || trends);
      notify(`Discovery complete: ${result.quota_used_today}/${result.quota_limit} quota units used`);
      await loadAll();
    } catch (error) {
      notify(error.message, "error");
    } finally {
      setBusy("");
    }
  };

  const cloneHook = (hook) => {
    setStudio((current) => ({ ...current, prompt_text: hook || current.prompt_text }));
    setTab("studio");
    notify("Hook cloned to Studio prompt");
  };

  const toggleChannel = (channel) => {
    setDispatch((current) => ({
      ...current,
      channels: current.channels.includes(channel)
        ? current.channels.filter((item) => item !== channel)
        : [...current.channels, channel],
    }));
  };

  const submitDispatch = async (approve) => {
    setBusy(approve ? "approve" : "preview");
    try {
      const result = await request("/v1/sales-ops/outreach/dispatch", {
        method: "POST",
        body: JSON.stringify({ ...dispatch, approve }),
      });
      setPreview(result);
      notify(result.status === "pending_review" ? "Campaign queued for human approval" : "Campaign dispatched");
      await loadAll();
    } catch (error) {
      notify(error.message, "error");
    } finally {
      setBusy("");
    }
  };

  const toggleDisabled = (name) => !isAdmin || busy === `toggle:${name}`;

  return (
    <div className="salesops-page">
      <div className="so-hero">
        <div>
          <div className="eyebrow">PROD BASIC / ISOLATED AUTOMATION</div>
          <h2>Sales Ops & AI Studio</h2>
          <p>All controls below use isolated /api/v1 routes. Existing ERP, auth and email workflows remain untouched.</p>
        </div>
        <div className="so-kpis">
          <div className="so-kpi"><small>Quotations</small><b>118</b><span>Rs 2.17 Cr</span></div>
          <div className="so-kpi"><small>Sales orders</small><b>91</b><span>Rs 98.69 L</span></div>
          <div className="so-kpi"><small>Dispatched</small><b>68,174 kg</b><span>110 packing lists</span></div>
          <div className="so-kpi"><small>Extrusion</small><b>7-10 T/day</b><span>Zero-waste recycling</span></div>
        </div>
      </div>

      <div className="so-tabs">
        {[
          ["controls", "Settings", Settings2],
          ["barcode", "Barcode scan", ScanLine],
          ["studio", "AI Studio", Film],
          ["trends", "Trending patterns", TrendingUp],
          ["dispatch", "Campaign composer", Send],
        ].map(([key, label, Icon]) => (
          <button key={key} className={tab === key ? "active" : ""} onClick={() => setTab(key)}>
            <Icon size={15} /> {label}
          </button>
        ))}
        <button className="so-refresh" onClick={() => loadAll().catch((error) => notify(error.message, "error"))}><RefreshCw size={15} /> Refresh</button>
      </div>

      {notice && <div className={`so-notice ${notice.includes("error") ? "error" : ""}`}>{notice}</div>}
      {!isAdmin && <div className="so-notice">Signed in as a non-admin user: automation controls are read-only.</div>}

      {tab === "controls" && (
        <div className="so-grid">
          <div className="so-card wide">
            <div className="so-card-head"><h3>Admin sliding switches</h3><span>{isAdmin ? "Live controls" : "Read only"}</span></div>
            <div className="so-toggle-list">
              <ToggleRow label="WhatsApp auto-send mode" hint="OFF = 1-click human copy; ON = auto queue up to the hard cap." checked={toggles.whatsapp_auto_send_enabled} disabled={toggleDisabled("whatsapp_auto_send_enabled")} onChange={(value) => patchToggle("whatsapp_auto_send_enabled", value)} />
              <ToggleRow label="Human review gate" hint="Require approval before any campaign dispatch." checked={toggles.human_review_required} disabled={toggleDisabled("human_review_required")} onChange={(value) => patchToggle("human_review_required", value)} />
              <ToggleRow label="ERP auto follow-up trigger" hint="Queue follow-up from sales-app-data and barcode events." checked={toggles.erp_auto_followup_trigger} disabled={toggleDisabled("erp_auto_followup_trigger")} onChange={(value) => patchToggle("erp_auto_followup_trigger", value)} />
              <ToggleRow label="Mobile camera barcode + weight sync" hint="Allow camera barcode capture and weight confirmation." checked={toggles.barcode_mobile_scan_enabled} disabled={toggleDisabled("barcode_mobile_scan_enabled")} onChange={(value) => patchToggle("barcode_mobile_scan_enabled", value)} />
              <ToggleRow label="YouTube free-tier cron" hint="Strict 4,000 / 10,000 unit daily guard." checked={toggles.youtube_free_tier_cron_enabled} disabled={toggleDisabled("youtube_free_tier_cron_enabled")} onChange={(value) => patchToggle("youtube_free_tier_cron_enabled", value)} />
              <ToggleRow label="Sales pitch KPI overlay" hint="Inject verified 118 quotes / Rs 2.17 Cr / 7-10 T/day facts." checked={toggles.sales_pitch_kpi_overlay} disabled={toggleDisabled("sales_pitch_kpi_overlay")} onChange={(value) => patchToggle("sales_pitch_kpi_overlay", value)} />
            </div>
            <label className="so-field">
              <span>WhatsApp daily hard cap</span>
              <select
                value={toggles.whatsapp_daily_hard_cap}
                disabled={!isAdmin || busy === "toggle:whatsapp_daily_hard_cap"}
                onChange={(event) => patchToggle("whatsapp_daily_hard_cap", Number(event.target.value))}
              >
                {Array.from({ length: 49 }, (_, index) => index + 1).map((value) => <option key={value} value={value}>{value} messages/day</option>)}
              </select>
            </label>
          </div>
          <div className="so-card">
            <div className="so-card-head"><h3>Today's safe counters</h3><span>{counters.date || "today"}</span></div>
            <div className="so-counter-grid">
              <div><small>WhatsApp queued</small><b>{counters.whatsapp_sent || 0}</b><span>/ {toggles.whatsapp_daily_hard_cap}</span></div>
              <div><small>YouTube quota</small><b>{counters.yt_quota_used || 0}</b><span>/ 4000 guard</span></div>
              <div><small>Human review</small><b>{toggles.human_review_required ? "ON" : "OFF"}</b><span>approval gate</span></div>
            </div>
            <div className="so-callout"><BarChart3 size={18} /><span>Feature flags are stored in the isolated admin_feature_flags table. No ERP auth/RBAC table is changed.</span></div>
          </div>
        </div>
      )}

      {tab === "barcode" && (
        <div className="so-grid">
          <div className="so-card">
            <div className="so-card-head"><h3>Mobile barcode scan</h3><span>Camera + weight lock</span></div>
            <button className="primary-button" type="button" onClick={startScanner} disabled={busy === "camera" || !toggles.barcode_mobile_scan_enabled}><Camera size={16} /> Open camera scanner</button>
            <form className="so-form" onSubmit={queueScan}>
              <label className="so-field"><span>Barcode value</span><input value={scan.barcode} onChange={(event) => setScan({ ...scan, barcode: event.target.value })} placeholder="KLK-SF23-500MM-0842" /></label>
              <div className="so-form-grid">
                <label className="so-field"><span>SKU</span><input value={scan.sku} onChange={(event) => setScan({ ...scan, sku: event.target.value })} /></label>
                <label className="so-field"><span>Net weight (kg)</span><input type="number" step="0.001" min="0.001" max="5000" value={scan.net_weight_kg} onChange={(event) => setScan({ ...scan, net_weight_kg: event.target.value })} /></label>
              </div>
              <label className="so-field"><span>Customer name</span><input value={scan.customer_name} onChange={(event) => setScan({ ...scan, customer_name: event.target.value })} /></label>
              <div className="so-form-grid">
                <label className="so-field"><span>Customer email</span><input value={scan.customer_email} onChange={(event) => setScan({ ...scan, customer_email: event.target.value })} /></label>
                <label className="so-field"><span>Customer WhatsApp</span><input value={scan.customer_whatsapp} onChange={(event) => setScan({ ...scan, customer_whatsapp: event.target.value })} /></label>
              </div>
              <label className="so-check"><input type="checkbox" checked={scan.trigger_followup} onChange={(event) => setScan({ ...scan, trigger_followup: event.target.checked })} /> Queue ERP follow-up</label>
              <button className="primary-button" type="submit" disabled={busy === "scan" || !toggles.barcode_mobile_scan_enabled}>Queue follow-up</button>
            </form>
          </div>
          <div className="so-card">
            <div className="so-card-head"><h3>Recent scan log</h3><span>{scans.length} events</span></div>
            <div className="so-list">
              {scans.length === 0 && <div className="so-empty">No barcode scans recorded yet.</div>}
              {scans.map((item) => (
                <div className="so-list-row" key={item.id}>
                  <div><b>{item.barcode}</b><small>{item.customer_name || "Unnamed customer"} · {item.net_weight_kg} kg</small></div>
                  <span className="so-pill">{item.followup_status}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {tab === "studio" && (
        <div className="so-grid">
          <div className="so-card wide">
            <div className="so-card-head"><h3>AI Film Studio prompt refine</h3><span>Verified KPI guardrails</span></div>
            <div className="so-form-grid three">
              <label className="so-field"><span>Model</span>
                <select value={studio.model_choice} onChange={(event) => setStudio({ ...studio, model_choice: event.target.value })}>
                  <option value="local_gemma_4b">Local Gemma 4B ($0.00)</option>
                  <option value="zero_llm_fast">Zero-LLM fast ($0.00)</option>
                  <option value="gcp_flash_lite">GCP Flash-Lite</option>
                  <option value="gcp_gemma_27b">GCP Gemma 27B</option>
                </select>
              </label>
              <label className="so-field"><span>Template</span>
                <select value={studio.template_path} onChange={(event) => setStudio({ ...studio, template_path: event.target.value })}>
                  {templates.map((item) => <option key={item.path} value={item.path || item.gcs_uri}>{item.name}</option>)}
                </select>
              </label>
              <label className="so-field"><span>Aspect ratio</span>
                <select value={studio.aspect_ratio} onChange={(event) => setStudio({ ...studio, aspect_ratio: event.target.value })}>
                  <option value="16:9">16:9</option><option value="9:16">9:16</option>
                </select>
              </label>
            </div>
            <label className="so-field"><span>Prompt</span><textarea rows="7" value={studio.prompt_text} onChange={(event) => setStudio({ ...studio, prompt_text: event.target.value })} /></label>
            <div className="so-actions">
              <button className="primary-button" onClick={refine} disabled={busy === "refine"}><Sparkles size={16} /> Refine prompt</button>
              <label className="upload-button"><FileUp size={16} /> Easy upload<input type="file" hidden onChange={(event) => uploadAsset(event.target.files?.[0])} /></label>
              <div className="so-dropzone" onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); uploadAsset(event.dataTransfer.files?.[0]); }}>
                Drag a video, PDF, logo or JSON template here
              </div>
            </div>
            {refined && (
              <div className="so-result">
                <div className="so-card-head"><h4>Refined output</h4><span>{refined.source_mode} · ${refined.cost_usd}</span></div>
                <pre>{refined.refined_prompt}</pre>
                <button className="secondary-button" onClick={() => copyText(refined.refined_prompt)}><Copy size={15} /> Copy prompt</button>
              </div>
            )}
          </div>
        </div>
      )}

      {tab === "trends" && (
        <div className="so-grid">
          <div className="so-card">
            <div className="so-card-head"><h3>YouTube dynamic discovery</h3><span>40 searches/day ceiling</span></div>
            <label className="so-field"><span>Industrial keyphrases (one per line)</span><textarea rows="5" value={keywords} onChange={(event) => setKeywords(event.target.value)} /></label>
            <button className="primary-button" onClick={discover} disabled={busy === "discover"}><TrendingUp size={16} /> Discover patterns</button>
          </div>
          <div className="so-card">
            <div className="so-card-head"><h3>Hook pattern library</h3><span>{trends.length} signals</span></div>
            <div className="so-list">
              {trends.length === 0 && <div className="so-empty">Run discovery to populate trending hooks.</div>}
              {trends.map((item) => (
                <div className="so-list-row column" key={item.id || item.video_url}>
                  <div><b>{item.title}</b><small>{item.query} · {item.source_mode}</small></div>
                  <div className="so-actions compact"><a href={item.video_url} target="_blank" rel="noreferrer">Open</a><button className="secondary-button" onClick={() => cloneHook(item.hook_pattern || item.title)}>Clone to Studio</button></div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {tab === "dispatch" && (
        <div className="so-grid">
          <div className="so-card">
            <div className="so-card-head"><h3>Omni-channel campaign composer</h3><span>Email + WA + YT + IG</span></div>
            <div className="so-form-grid">
              <label className="so-field"><span>Contact name</span><input value={dispatch.contact_name} onChange={(event) => setDispatch({ ...dispatch, contact_name: event.target.value })} /></label>
              <label className="so-field"><span>Company</span><input value={dispatch.company_name} onChange={(event) => setDispatch({ ...dispatch, company_name: event.target.value })} /></label>
              <label className="so-field"><span>Phone</span><input value={dispatch.phone} onChange={(event) => setDispatch({ ...dispatch, phone: event.target.value })} /></label>
              <label className="so-field"><span>Email</span><input value={dispatch.email} onChange={(event) => setDispatch({ ...dispatch, email: event.target.value })} /></label>
            </div>
            <label className="so-field"><span>Catalogue URL</span><input value={dispatch.catalog_url} onChange={(event) => setDispatch({ ...dispatch, catalog_url: event.target.value })} placeholder="/api/public/catalog/catalog" /></label>
            <div className="so-channel-pills">
              {["email", "whatsapp", "youtube", "instagram"].map((channel) => (
                <button key={channel} className={dispatch.channels.includes(channel) ? "active" : ""} onClick={() => toggleChannel(channel)}>{channel}</button>
              ))}
            </div>
            <div className="so-actions">
              <button className="primary-button" onClick={() => submitDispatch(false)} disabled={busy === "preview"}>Preview & queue</button>
              <button className="secondary-button" onClick={() => submitDispatch(true)} disabled={busy === "approve" || !isAdmin}><Check size={15} /> Approve & dispatch</button>
            </div>
          </div>
          <div className="so-card">
            <div className="so-card-head"><h3>Side-by-side preview</h3><span>{preview ? preview.status : "not generated"}</span></div>
            {!preview && <div className="so-empty">Generate a preview to see Email, WhatsApp, YouTube and Instagram copy together.</div>}
            {preview && (
              <div className="so-preview-grid">
                <div className="so-result"><h4>Email</h4><b>{preview.email.subject}</b><pre>{preview.email.body}</pre><button className="secondary-button" onClick={() => copyText(preview.email.body)}><Copy size={14} /> Copy</button></div>
                <div className="so-result"><h4>WhatsApp</h4><pre>{preview.whatsapp.message_text}</pre><div className="so-actions compact"><a href={preview.whatsapp.one_click_whatsapp_url} target="_blank" rel="noreferrer">Open WhatsApp</a><button className="secondary-button" onClick={() => copyText(preview.whatsapp.message_text)}><Copy size={14} /> Copy</button></div></div>
                <div className="so-result"><h4>YouTube</h4><b>{preview.youtube_title}</b><pre>{preview.youtube_description}</pre></div>
                <div className="so-result"><h4>Instagram</h4><pre>{preview.instagram_caption}</pre></div>
              </div>
            )}
          </div>
        </div>
      )}

      {scanModal && (
        <div className="modal-overlay" onClick={() => stopCamera()}>
          <div className="modal-content so-scan-modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header"><h3>Barcode camera scanner</h3><button className="icon-button" onClick={() => stopCamera()} aria-label="Close scanner"><X size={20} /></button></div>
            <div className="modal-body">
              <video ref={videoRef} className="so-scan-video" autoPlay playsInline />
              <p>{camera.status || "Starting camera..."}</p>
              <div className="so-form-grid">
                <label className="so-field"><span>Detected barcode</span><input value={scan.barcode} onChange={(event) => setScan({ ...scan, barcode: event.target.value })} /></label>
                <label className="so-field"><span>Net weight (kg)</span><input type="number" step="0.001" value={scan.net_weight_kg} onChange={(event) => setScan({ ...scan, net_weight_kg: event.target.value })} /></label>
              </div>
              <div className="so-actions"><button className="primary-button" onClick={queueScan}>Queue follow-up</button><button className="secondary-button" onClick={() => stopCamera()}>Close</button></div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
