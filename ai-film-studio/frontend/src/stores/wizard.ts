import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { Category } from "@/types";

interface WizardState {
  step: number;
  category: Category | null;
  topic: string;
  description: string;
  title: string;
  visualStyle: string;
  template: string;
  duration: number;
  aspect: string;
  set: (patch: Partial<Omit<WizardState, "set" | "next" | "back" | "reset" | "start">>) => void;
  next: () => void;
  back: () => void;
  start: (category: Category) => void;
  reset: () => void;
}

const initial = {
  step: 0,
  category: null as Category | null,
  topic: "",
  description: "",
  title: "",
  visualStyle: "cinematic",
  template: "insight",
  duration: 45,
  aspect: "16:9",
};

export const useWizardStore = create<WizardState>()(
  persist(
    (set) => ({
      ...initial,
      set: (patch) => set(patch),
      next: () => set((state) => ({ step: Math.min(state.step + 1, 4) })),
      back: () => set((state) => ({ step: Math.max(state.step - 1, 0) })),
      start: (category) => set({ ...initial, category, step: 1 }),
      reset: () => set({ ...initial }),
    }),
    { name: "ai-film-studio-wizard" },
  ),
);
