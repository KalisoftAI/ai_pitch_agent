import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export function formatRelative(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  const diff = Date.now() - date.getTime();
  const minutes = Math.round(diff / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  return formatDate(value);
}

export function formatBytes(bytes: number) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

export function formatNumber(value: number) {
  return new Intl.NumberFormat().format(value);
}

export function formatCurrency(value: number) {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: value < 1 ? 4 : 2,
  }).format(value);
}

export function titleCase(value: string) {
  return value
    .replace(/[-_]/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function parseParagraphs(content: string) {
  return content
    .split(/\n\s*\n/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean);
}

export function estimateWordCount(content: string) {
  return content.trim() ? content.trim().split(/\s+/).length : 0;
}

export function estimateReadSeconds(content: string) {
  return Math.round((estimateWordCount(content) / 150) * 60);
}

export const CATEGORY_META: Record<
  string,
  { label: string; short: string; accent: string; description: string }
> = {
  "business-tips": {
    label: "Business Tips",
    short: "Business",
    accent: "from-violet-500/30 to-fuchsia-500/10",
    description: "Sharp, practical advice for founders and operators.",
  },
  "erp-walkthrough": {
    label: "ERP & Production App Walkthroughs",
    short: "ERP",
    accent: "from-cyan-500/30 to-sky-500/10",
    description: "Step-by-step product tours that make complex workflows feel simple.",
  },
  "financial-education": {
    label: "Financial Education",
    short: "Finance",
    accent: "from-emerald-500/30 to-teal-500/10",
    description: "Clear explanations of money, cash flow, and financial decisions.",
  },
};

export const VISUAL_STYLES = [
  { id: "cinematic", label: "Cinematic", description: "Deep shadows, slow reveals, premium grade." },
  { id: "editorial", label: "Editorial", description: "Clean typography and magazine-like layouts." },
  { id: "neon", label: "Neon Studio", description: "Dark stage, vivid violet and cyan highlights." },
  { id: "minimal", label: "Minimal", description: "Lots of space, calm motion, crisp type." },
];

export const TEMPLATES = [
  { id: "insight", label: "Insight", description: "Hook, context, framework, proof, action." },
  { id: "walkthrough", label: "Walkthrough", description: "Problem, screen tour, result, next step." },
  { id: "explainer", label: "Explainer", description: "Question, simple model, example, takeaway." },
];

export const ASPECT_RATIOS = ["16:9", "9:16", "1:1", "4:5"];
