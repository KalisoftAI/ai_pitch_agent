const INVISIBLE_RE = /[\u0000-\u001f\u007f-\u009f\u00ad\u200b\u200c\u200d\u2060\ufeff]/g;
const EMAIL_RE = /^[A-Z0-9._%+-]+@[A-Z0-9](?:[A-Z0-9.-]*[A-Z0-9])?\.[A-Z]{2,}$/i;
const TRIM_RE = /^[\s<>()\[\]{}"',;:]+|[\s<>()\[\]{}"',;:]+$/g;

export function normalizeEmail(value) {
  const text = String(value == null ? "" : value).replace(INVISIBLE_RE, "").trim().toLowerCase();
  if (!text) return "";
  const candidates = text.split(/[\s,;|]+/);
  for (const raw of candidates) {
    const candidate = raw.replace(TRIM_RE, "");
    if (EMAIL_RE.test(candidate)) return candidate;
  }
  const fallback = text.replace(TRIM_RE, "");
  return fallback.includes("@") ? fallback : "";
}

export function validEmail(value) {
  const candidate = normalizeEmail(value);
  return EMAIL_RE.test(candidate);
}

export function normalizePhone(value) {
  return String(value == null ? "" : value).replace(INVISIBLE_RE, "").replace(/\D/g, "");
}

export function validPhone(value) {
  return normalizePhone(value).length >= 8;
}

export function filterByChannel(rows, channel) {
  const list = Array.isArray(rows) ? rows : [];
  if (channel === "email") return list.filter((row) => validEmail(row.email));
  if (channel === "whatsapp" || channel === "phone") return list.filter((row) => validPhone(row.phone));
  if (channel === "both") return list.filter((row) => validEmail(row.email) || validPhone(row.phone));
  return list;
}
