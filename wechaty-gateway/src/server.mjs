/**
 * Kalisoft Wechaty gateway.
 *
 * Bridges the Python FastAPI service to Wechaty:
 *   POST /send              -> send a WhatsApp/WeChat text message
 *   POST /simulate/inbound  -> inject an inbound message (mock mode only)
 *   GET  /health            -> liveness + mode + login state
 *   GET  /qr                -> latest login QR (live mode)
 *   GET  /messages          -> recent inbound/outbound records
 *
 * Inbound messages are forwarded to WECHATY_WEBHOOK_URL with an HMAC-SHA256
 * signature so the backend can verify authenticity.
 */
import http from "node:http";
import { pathToFileURL } from "node:url";

import { createTransport } from "./transport.mjs";
import { signBody } from "./webhook.mjs";

const DEFAULTS = {
  host: process.env.WECHATY_GATEWAY_HOST || "0.0.0.0",
  port: Number(process.env.PORT || process.env.WECHATY_GATEWAY_PORT || 8788),
  mode: process.env.WECHATY_GATEWAY_MODE || "mock",
  puppet: process.env.WECHATY_PUPPET || "wechaty-puppet-wechat4u",
  token: process.env.WECHATY_GATEWAY_TOKEN || "",
  webhookUrl: process.env.WECHATY_WEBHOOK_URL || "",
  webhookSecret: process.env.WECHATY_WEBHOOK_SECRET || "",
  maxBodyBytes: Number(process.env.WECHATY_MAX_BODY_BYTES || 1_048_576),
  maxMessages: Number(process.env.WECHATY_MAX_MESSAGES || 100),
};

function sendJson(res, status, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(status, { "content-type": "application/json", "content-length": Buffer.byteLength(body) });
  res.end(body);
}

function readBody(req, limit) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on("data", (chunk) => {
      size += chunk.length;
      if (size > limit) {
        reject(Object.assign(new Error("request body too large"), { statusCode: 413 }));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on("end", () => resolve(Buffer.concat(chunks)));
    req.on("error", reject);
  });
}

function authorized(req, token) {
  if (!token) return true; // token disabled (local dev only)
  const header = req.headers["x-gateway-token"];
  const auth = req.headers["authorization"] || "";
  const bearer = auth.toLowerCase().startsWith("bearer ") ? auth.slice(7) : "";
  return header === token || bearer === token;
}

export function createGateway(overrides = {}) {
  const config = { ...DEFAULTS, ...overrides };
  const transport = overrides.transport || createTransport({ mode: config.mode, puppet: config.puppet });
  const messages = [];

  async function forwardInbound(record) {
    messages.push({ direction: "inbound", ...record });
    if (messages.length > config.maxMessages) messages.shift();
    if (!config.webhookUrl) return;
    try {
      const raw = JSON.stringify(record);
      await fetch(config.webhookUrl, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-wechaty-signature": signBody(config.webhookSecret, raw),
        },
        body: raw,
      });
    } catch (error) {
      console.error("[gateway] webhook forward failed:", error.message);
    }
  }
  transport.onInbound(forwardInbound);

  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, "http://localhost");
    const route = `${req.method} ${url.pathname}`;

    try {
      if (route === "GET /health") {
        return sendJson(res, 200, { status: "ok", ...transport.status() });
      }
      if (!authorized(req, config.token)) {
        return sendJson(res, 401, { detail: "invalid gateway token" });
      }
      if (route === "GET /qr") {
        if (!transport.qr) return sendJson(res, 404, { detail: "no QR available" });
        return sendJson(res, 200, { qr: transport.qr, status: transport.statusText });
      }
      if (route === "GET /messages") {
        return sendJson(res, 200, { count: messages.length, messages });
      }
      if (route === "POST /send") {
        const body = JSON.parse((await readBody(req, config.maxBodyBytes)).toString("utf8") || "{}");
        if (!body.to || !body.text) return sendJson(res, 400, { detail: "'to' and 'text' are required" });
        const result = await transport.send(body.to, body.text);
        messages.push({ direction: "outbound", ...result });
        if (messages.length > config.maxMessages) messages.shift();
        return sendJson(res, 200, { ok: true, ...result });
      }
      if (route === "POST /simulate/inbound" && typeof transport.simulateInbound === "function") {
        const body = JSON.parse((await readBody(req, config.maxBodyBytes)).toString("utf8") || "{}");
        const record = await transport.simulateInbound(body);
        return sendJson(res, 200, { ok: true, ...record });
      }
      return sendJson(res, 404, { detail: "not found" });
    } catch (error) {
      const status = error.statusCode || 500;
      return sendJson(res, status, { detail: error.message });
    }
  });

  return { server, transport, config, messages };
}

export async function startGateway(overrides = {}) {
  const gateway = createGateway(overrides);
  await gateway.transport.start();
  await new Promise((resolve) => gateway.server.listen(gateway.config.port, gateway.config.host, resolve));
  const address = gateway.server.address();
  console.log(`[gateway] listening on http://${gateway.config.host}:${address.port} (mode=${gateway.config.mode})`);
  return gateway;
}

const isMain = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
if (isMain) {
  startGateway().catch((error) => {
    console.error("[gateway] failed to start:", error);
    process.exit(1);
  });
  const shutdown = async () => {
    console.log("[gateway] shutting down");
    process.exit(0);
  };
  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
}
