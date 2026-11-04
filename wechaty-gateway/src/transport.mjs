/**
 * Wechaty transports.
 *
 * - MockTransport: zero-dependency simulator. Logs in immediately and records
 *   outbound messages + simulated inbound messages. Used for local tests and CI.
 * - LiveTransport: real Wechaty bot. Lazily imports the `wechaty` package so the
 *   gateway still boots (mock mode) when the optional dependency is absent.
 */

export class MockTransport {
  constructor() {
    this.mode = "mock";
    this.loggedIn = false;
    this.qr = null;
    this.statusText = "mock-ready";
    this.user = { id: "mock-bot", name: "Kalisoft Mock Bot" };
    this._inbound = null;
  }

  onInbound(handler) {
    this._inbound = handler;
  }

  async start() {
    this.loggedIn = true;
    this.statusText = "mock-logged-in";
    return this;
  }

  async stop() {
    this.loggedIn = false;
    this.statusText = "mock-stopped";
  }

  async send(to, text) {
    return {
      id: `mock-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      to,
      text,
      status: "sent",
      provider: "mock",
    };
  }

  async simulateInbound({ from = "mock-contact", text = "", room = null } = {}) {
    const record = {
      id: `mock-in-${Date.now()}`,
      from,
      from_name: from,
      room,
      text,
      timestamp: Date.now(),
      provider: "mock",
    };
    if (this._inbound) await this._inbound(record);
    return record;
  }

  status() {
    return {
      mode: this.mode,
      puppet: "mock",
      logged_in: this.loggedIn,
      status_text: this.statusText,
      user: this.user,
      qr_available: Boolean(this.qr),
    };
  }
}

export class LiveTransport {
  constructor({ puppet } = {}) {
    this.mode = "live";
    this.puppet = puppet || "wechaty-puppet-wechat4u";
    this.loggedIn = false;
    this.qr = null;
    this.statusText = "starting";
    this.user = null;
    this.wechaty = null;
    this._inbound = null;
  }

  onInbound(handler) {
    this._inbound = handler;
  }

  async start() {
    const { WechatyBuilder } = await import("wechaty");
    this.wechaty = WechatyBuilder.build({ name: "kalisoft-gateway", puppet: this.puppet });

    this.wechaty
      .on("scan", (qrcode, status) => {
        this.qr = qrcode;
        this.statusText = `scan:${status}`;
      })
      .on("login", (user) => {
        this.loggedIn = true;
        this.statusText = "logged-in";
        this.user = { id: user.id, name: typeof user.name === "function" ? user.name() : user.name };
      })
      .on("logout", () => {
        this.loggedIn = false;
        this.statusText = "logged-out";
      })
      .on("message", async (message) => {
        if (message.self()) return;
        const from = message.from();
        const room = message.room();
        const record = {
          id: message.id,
          from: from ? from.id : "",
          from_name: from && from.name ? from.name() : "",
          room: room ? room.id : null,
          text: message.text(),
          timestamp: Date.now(),
          provider: "wechaty",
        };
        if (this._inbound) await this._inbound(record);
      });

    await this.wechaty.start();
    return this;
  }

  async stop() {
    if (this.wechaty) await this.wechaty.stop();
    this.loggedIn = false;
  }

  async send(to, text) {
    if (!this.wechaty) throw new Error("wechaty is not started");
    const contact = this.wechaty.Contact.load(to);
    const sent = await contact.say(text);
    return {
      id: (sent && sent.id) || `live-${Date.now()}`,
      to,
      text,
      status: "sent",
      provider: "wechaty",
    };
  }

  status() {
    return {
      mode: this.mode,
      puppet: this.puppet,
      logged_in: this.loggedIn,
      status_text: this.statusText,
      user: this.user,
      qr_available: Boolean(this.qr),
    };
  }
}

export function createTransport(config = {}) {
  if (config.mode === "live") return new LiveTransport({ puppet: config.puppet });
  return new MockTransport();
}
