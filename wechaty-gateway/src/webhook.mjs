import { createHmac, timingSafeEqual } from "node:crypto";

/** Sign a raw request body with HMAC-SHA256: `sha256=<hex>`. */
export function signBody(secret, rawBody) {
  const mac = createHmac("sha256", secret || "").update(rawBody).digest("hex");
  return `sha256=${mac}`;
}

/** Constant-time verification of an inbound signature header. */
export function verifySignature(secret, rawBody, header) {
  if (!secret || !header) return false;
  const expected = Buffer.from(signBody(secret, rawBody));
  const provided = Buffer.from(String(header));
  if (expected.length !== provided.length) return false;
  return timingSafeEqual(expected, provided);
}
