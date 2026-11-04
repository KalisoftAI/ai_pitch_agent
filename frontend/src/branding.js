// Centralized brand assets - official company logos (files live in public/).
// Import from here instead of hardcoding logo paths in components.
// BASE_URL keeps paths correct for both Vite dev and FastAPI /static serving.
const BASE = import.meta.env.BASE_URL || "/";
export const KALISOFT_LOGO = `${BASE}kalisoft-ai-logo.png`; // KalisoftAI (transparent bg)
export const KALIKA_LOGO = `${BASE}kalika-logo.png`; // Kalika Enterprises (white bg wordmark)
