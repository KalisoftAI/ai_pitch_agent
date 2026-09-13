# Kalisoft Wechaty Gateway

HTTP bridge between the Kalisoft FastAPI sales service and [Wechaty](https://github.com/wechaty/wechaty)
(WhatsApp / WeChat conversational RPA SDK). The FastAPI app never embeds Node; it calls this
gateway over HTTP, and the gateway forwards inbound messages back to the app webhook.

## Modes

| Mode | Use | Behaviour |
|---|---|---|
| `mock` (default) | local dev, CI, tests | No Wechat account. Logs in instantly; `/send` returns a synthetic id; `/simulate/inbound` injects messages. |
| `live` | real usage | Loads `wechaty` + a puppet, prints a QR to scan, forwards real messages. |

`wechaty` and `wechaty-puppet-wechat4u` are **optionalDependencies**, so the gateway
boots and tests run even when they are not installed.

## Run

```bash
cd wechaty-gateway
cp .env.example .env        # edit token/secret
npm install                 # optional deps skipped if unavailable
npm start                   # http://localhost:8788 (mock)
npm test                    # node:test suite
```

Live mode:

```bash
WECHATY_GATEWAY_MODE=live WECHATY_PUPPET=wechaty-puppet-wechat4u npm start
# scan the QR printed by Wechaty / exposed at GET /qr
```

Hosted iPad/Windows puppets use `WECHATY_PUPPET=wechaty-puppet-service` plus
`WECHATY_PUPPET_SERVICE_TOKEN`.

## API

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | no | liveness + mode + login state |
| GET | `/qr` | yes | latest login QR (live) |
| POST | `/send` | yes | `{ "to": "<contact id>", "text": "..." }` |
| POST | `/simulate/inbound` | yes | mock-only inbound injection |
| GET | `/messages` | yes | recent inbound/outbound records |

Auth: `X-Gateway-Token: <token>` or `Authorization: Bearer <token>`.
Inbound forwards carry `X-Wechaty-Signature: sha256=<hmac>` over the raw JSON body.

## Security notes

- Use a **dedicated number/account**; automated sending risks a platform ban.
- Keep `WECHATY_GATEWAY_TOKEN` and `WECHATY_WEBHOOK_SECRET` in Secret Manager.
- The gateway is internal-only; do not expose it publicly without auth + Cloud Armor.
