import React, { useEffect, useState } from "react";
import {
  Mail, Users, Send, CheckCircle, Clock, X, RefreshCw, Eye, Trash2, Play,
} from "lucide-react";

const API = "/api";
const readToken = () => sessionStorage.getItem("sales_token") || "";

async function request(path, options = {}) {
  const headers = { "Content-Type": "application/json" };
  const token = readToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${API}${path}`, { ...options, headers });
  if (!response.ok) {
    let message = "Request failed";
    try { message = (await response.json()).detail || message; } catch { /* ignore */ }
    throw new Error(message);
  }
  return response.status === 204 ? null : response.json();
}

export function CampaignManager({ onNotice }) {
  const [templates, setTemplates] = useState([]);
  const [campaigns, setCampaigns] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState("");
  const [selectedSource, setSelectedSource] = useState("marketing");
  const [selectedCategories, setSelectedCategories] = useState([]);
  const [availableCategories, setAvailableCategories] = useState({});
  const [contacts, setContacts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [previewCampaign, setPreviewCampaign] = useState(null);
  const [previewMessages, setPreviewMessages] = useState([]);

  useEffect(() => {
    loadTemplates();
    loadCampaigns();
  }, []);

  const loadTemplates = async () => {
    try {
      const data = await request("/templates");
      setTemplates(data);
    } catch (error) {
      onNotice({ type: "error", text: error.message });
    }
  };

  const loadCampaigns = async () => {
    try {
      const data = await request("/campaigns/list");
      setCampaigns(data);
    } catch (error) {
      onNotice({ type: "error", text: error.message });
    }
  };

  const loadContacts = async () => {
    setLoading(true);
    try {
      const data = await request(`/campaigns/load-contacts?source=${selectedSource}`, {
        method: "POST",
      });
      setContacts(data.contacts);
      setAvailableCategories(data.by_category);
      setSelectedCategories([]);
      onNotice({ type: "success", text: `Loaded ${data.total} contacts` });
    } catch (error) {
      onNotice({ type: "error", text: error.message });
    } finally {
      setLoading(false);
    }
  };

  const createCampaign = async () => {
    if (!selectedTemplate) {
      onNotice({ type: "error", text: "Please select a template" });
      return;
    }

    setLoading(true);
    try {
      const result = await request("/campaigns/create", {
        method: "POST",
        body: JSON.stringify({
          template_id: parseInt(selectedTemplate),
          contact_source: selectedSource,
          categories: selectedCategories,
        }),
      });
      onNotice({ type: "success", text: result.message });
      await loadCampaigns();
      setSelectedTemplate("");
      setSelectedCategories([]);
      setContacts([]);
    } catch (error) {
      onNotice({ type: "error", text: error.message });
    } finally {
      setLoading(false);
    }
  };

  const approveCampaign = async (id) => {
    try {
      await request(`/campaigns/${id}/approve`, { method: "POST" });
      onNotice({ type: "success", text: "Campaign approved" });
      await loadCampaigns();
    } catch (error) {
      onNotice({ type: "error", text: error.message });
    }
  };

  const deleteCampaign = async (id) => {
    if (!window.confirm("Delete this campaign?")) return;
    try {
      await request(`/campaigns/${id}`, { method: "DELETE" });
      onNotice({ type: "success", text: "Campaign deleted" });
      await loadCampaigns();
    } catch (error) {
      onNotice({ type: "error", text: error.message });
    }
  };

  const viewCampaignMessages = async (id) => {
    try {
      const messages = await request(`/campaigns/${id}/messages`);
      setPreviewCampaign(campaigns.find(c => c.id === id));
      setPreviewMessages(messages);
    } catch (error) {
      onNotice({ type: "error", text: error.message });
    }
  };

  const toggleCategory = (category) => {
    setSelectedCategories(prev =>
      prev.includes(category)
        ? prev.filter(c => c !== category)
        : [...prev, category]
    );
  };

  return (
    <div className="content">
      <div className="page-heading">
        <div>
          <div className="section-kicker">EMAIL CAMPAIGNS</div>
          <h2>Campaign Manager</h2>
          <p className="muted">Create and manage category-wise email campaigns</p>
        </div>
        <button className="secondary-button" onClick={loadCampaigns}>
          <RefreshCw size={16} /> Refresh
        </button>
      </div>

      {/* Create Campaign Section */}
      <div className="panel" style={{ marginBottom: "24px" }}>
        <div className="panel-heading">
          <div>
            <div className="section-kicker">NEW CAMPAIGN</div>
            <h3>Create Campaign</h3>
          </div>
        </div>

        <div className="form-grid" style={{ gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "16px" }}>
          <div>
            <label style={{ display: "block", marginBottom: "8px", fontWeight: "500" }}>
              Select Template
            </label>
            <select
              value={selectedTemplate}
              onChange={(e) => setSelectedTemplate(e.target.value)}
              style={{ width: "100%", padding: "8px", borderRadius: "6px", border: "1px solid var(--line)" }}
            >
              <option value="">Choose a template...</option>
              {templates.map(t => (
                <option key={t.id} value={t.id}>
                  {t.name} ({t.channel})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ display: "block", marginBottom: "8px", fontWeight: "500" }}>
              Contact Source
            </label>
            <div style={{ display: "flex", gap: "8px" }}>
              <button
                className={selectedSource === "marketing" ? "primary-button" : "secondary-button"}
                onClick={() => setSelectedSource("marketing")}
                style={{ flex: 1, padding: "8px" }}
              >
                <Users size={16} /> Marketing List
              </button>
              <button
                className={selectedSource === "erp" ? "primary-button" : "secondary-button"}
                onClick={() => setSelectedSource("erp")}
                style={{ flex: 1, padding: "8px" }}
              >
                <Mail size={16} /> ERP Customers
              </button>
            </div>
          </div>
        </div>

        <div style={{ marginBottom: "16px" }}>
          <button
            className="secondary-button"
            onClick={loadContacts}
            disabled={loading}
            style={{ width: "100%", padding: "10px" }}
          >
            {loading ? "Loading..." : "Load Contacts"}
          </button>
        </div>

        {contacts.length > 0 && (
          <>
            <div style={{ marginBottom: "16px" }}>
              <h4 style={{ marginBottom: "8px" }}>
                Categories ({Object.keys(availableCategories).length})
              </h4>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                {Object.entries(availableCategories).map(([category, count]) => (
                  <label
                    key={category}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                      padding: "6px 12px",
                      borderRadius: "6px",
                      border: `1px solid ${selectedCategories.includes(category) ? "var(--primary)" : "var(--line)"}`,
                      background: selectedCategories.includes(category) ? "var(--primary-light)" : "transparent",
                      cursor: "pointer",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={selectedCategories.includes(category)}
                      onChange={() => toggleCategory(category)}
                    />
                    <span>{category}</span>
                    <span style={{ color: "var(--muted)", fontSize: "12px" }}>({count})</span>
                  </label>
                ))}
              </div>
            </div>

            <div style={{ padding: "12px", background: "var(--bg-hover)", borderRadius: "8px", marginBottom: "16px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <strong>{contacts.length}</strong> contacts selected
                  {selectedCategories.length > 0 && (
                    <span style={{ marginLeft: "8px", color: "var(--muted)" }}>
                      from {selectedCategories.length} categories
                    </span>
                  )}
                </div>
              </div>
            </div>

            <button
              className="primary-button"
              onClick={createCampaign}
              disabled={loading}
              style={{ width: "100%", padding: "12px" }}
            >
              <Send size={16} /> Create Campaign
            </button>
          </>
        )}
      </div>

      {/* Campaigns List */}
      <div className="panel">
        <div className="panel-heading">
          <div>
            <div className="section-kicker">CAMPAIGNS</div>
            <h3>Your Campaigns</h3>
          </div>
        </div>

        {campaigns.length === 0 ? (
          <div className="empty-state">
            <Mail size={22} />
            <p>No campaigns yet</p>
            <small>Create a campaign to get started</small>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Channel</th>
                  <th>Total</th>
                  <th>Sent</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {campaigns.map(campaign => (
                  <tr key={campaign.id}>
                    <td><strong>{campaign.name}</strong></td>
                    <td>
                      <span className="template-channel">{campaign.channel}</span>
                    </td>
                    <td>{campaign.total}</td>
                    <td>{campaign.sent}</td>
                    <td>
                      <span className={`status-pill ${campaign.status}`}>
                        {campaign.status === "approved" && <CheckCircle size={12} />}
                        {campaign.status === "pending_review" && <Clock size={12} />}
                        {campaign.status}
                      </span>
                    </td>
                    <td>{new Date(campaign.created_at).toLocaleDateString()}</td>
                    <td>
                      <div style={{ display: "flex", gap: "4px" }}>
                        <button
                          className="icon-button"
                          onClick={() => viewCampaignMessages(campaign.id)}
                          title="View Messages"
                        >
                          <Eye size={16} />
                        </button>
                        {campaign.status === "pending_review" && (
                          <button
                            className="icon-button"
                            onClick={() => approveCampaign(campaign.id)}
                            title="Approve"
                          >
                            <Play size={16} />
                          </button>
                        )}
                        <button
                          className="icon-button danger"
                          onClick={() => deleteCampaign(campaign.id)}
                          title="Delete"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Preview Modal */}
      {previewCampaign && (
        <div className="modal-overlay" onClick={() => setPreviewCampaign(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: "800px" }}>
            <div className="modal-header">
              <h2>{previewCampaign.name} - Messages</h2>
              <button className="icon-button" onClick={() => setPreviewCampaign(null)}>
                <X size={20} />
              </button>
            </div>
            <div className="modal-body" style={{ maxHeight: "600px", overflowY: "auto" }}>
              {previewMessages.length === 0 ? (
                <div className="empty-state">
                  <p>No messages in this campaign</p>
                </div>
              ) : (
                <div style={{ display: "grid", gap: "12px" }}>
                  {previewMessages.map(msg => (
                    <div key={msg.id} className="panel" style={{ padding: "16px" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                        <strong>{msg.to}</strong>
                        <span className={`status-pill ${msg.status}`}>{msg.status}</span>
                      </div>
                      <div style={{ fontSize: "14px", marginBottom: "8px" }}>
                        <strong>Subject:</strong> {msg.subject}
                      </div>
                      <div style={{ fontSize: "13px", color: "var(--muted)", lineHeight: "1.5" }}>
                        {msg.body_preview}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
