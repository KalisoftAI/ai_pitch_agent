import assert from "node:assert/strict";
import http from "node:http";
import { test } from "node:test";

import { createGateway } from "../src/server.mjs";
import { signBody } from "../src/webhook.mjs";

async function withGateway(overrides, fn) {
  const gateway = createGateway({ host: "127.0.0.1", port: 0, mode: "mock", token: "test-token", ...overrides });
  await gateway.transport.start();
  await new Promise((resolve) => gateway.server.listen(0, "127.0.0.1", resolve));
  const base = `http://127.0.0.1:${gateway.server.address().port}`;
  try {
    await fn({ base, gateway });
  } finally {
    await new Promise((resolve) => gateway.server.close(resolve));
  }
}

test("health endpoint is public and reports mock mode", async () => {
  await withGateway({}, async ({ base }) => {
    const res = await fetch(`${base}/health`);
    assert.equal(res.status, 200);
    const body = await res.json();
    assert.equal(body.status, "ok");
    assert.equal(body.mode, "mock");
    assert.equal(body.logged_in, true);
  });
});

test("send requires a valid gateway token", async () => {
  await withGateway({}, async ({ base }) => {
    const unauth = await fetch(`${base}/send`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ to: "alice", text: "hi" }),
    });
    assert.equal(unauth.status, 401);

    const ok = await fetch(`${base}/send`, {
      method: "POST",
      headers: { "content-type": "application/json", "x-gateway-token": "test-token" },
      body: JSON.stringify({ to: "alice", text: "hi" }),
    });
    assert.equal(ok.status, 200);
    const body = await ok.json();
    assert.equal(body.ok, true);
    assert.equal(body.to, "alice");
    assert.equal(body.status, "sent");
  });
});

test("send validates required fields", async () => {
  await withGateway({}, async ({ base }) => {
    const res = await fetch(`${base}/send`, {
      method: "POST",
      headers: { "content-type": "application/json", "x-gateway-token": "test-token" },
      body: JSON.stringify({ to: "alice" }),
    });
    assert.equal(res.status, 400);
  });
});

test("inbound simulation forwards a signed webhook", async () => {
  const received = [];
  const receiver = http.createServer((req, res) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => {
      received.push({ body: Buffer.concat(chunks).toString("utf8"), signature: req.headers["x-wechaty-signature"] });
      res.writeHead(200);
      res.end("ok");
    });
  });
  await new Promise((resolve) => receiver.listen(0, "127.0.0.1", resolve));
  const webhookUrl = `http://127.0.0.1:${receiver.address().port}/hook`;

  try {
    await withGateway(
      { webhookUrl, webhookSecret: "shared-secret" },
      async ({ base }) => {
        const res = await fetch(`${base}/simulate/inbound`, {
          method: "POST",
          headers: { "content-type": "application/json", "x-gateway-token": "test-token" },
          body: JSON.stringify({ from: "bob", text: "Are you hiring?" }),
        });
        assert.equal(res.status, 200);
      },
    );
    assert.equal(received.length, 1);
    assert.equal(received[0].signature, signBody("shared-secret", received[0].body));
    assert.match(received[0].body, /Are you hiring\?/);
  } finally {
    await new Promise((resolve) => receiver.close(resolve));
  }
});

test("messages endpoint returns recent activity", async () => {
  await withGateway({}, async ({ base }) => {
    await fetch(`${base}/send`, {
      method: "POST",
      headers: { "content-type": "application/json", "x-gateway-token": "test-token" },
      body: JSON.stringify({ to: "carol", text: "hello" }),
    });
    const res = await fetch(`${base}/messages`, { headers: { "x-gateway-token": "test-token" } });
    assert.equal(res.status, 200);
    const body = await res.json();
    assert.ok(body.count >= 1);
    assert.equal(body.messages.at(-1).direction, "outbound");
  });
});
