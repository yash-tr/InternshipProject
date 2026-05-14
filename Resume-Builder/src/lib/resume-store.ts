"use client";

import { create } from "zustand";
import type { ResumeData } from "@appTypes/resume";
import { defaultResumeData } from "@appTypes/resume";
import { updateResume } from "@/lib/api";

function cloneData(data: ResumeData): ResumeData {
  return JSON.parse(JSON.stringify(data)) as ResumeData;
}

export interface ResumeStore {
  id: string | null;
  title: string;
  templateId: string;
  data: ResumeData;
  /** Snapshot used for PDF preview; only updated when user clicks "Update preview" */
  previewData: ResumeData;
  /** True when user has edited since last save (or load) */
  dirty: boolean;
  saving: boolean;
  setResume: (r: {
    id: string;
    title: string;
    templateId: string;
    data: ResumeData;
  }) => void;
  updateData: (patch: Partial<ResumeData>) => void;
  updateTitle: (title: string) => void;
  setTemplate: (templateId: string) => void;
  /** Copy current data into preview so PDF re-renders in batches (reduces load) */
  refreshPreview: () => void;
  /** Persist current state to API (no auto-save on keystroke) */
  saveResume: () => Promise<void>;
}

export const useResumeStore = create<ResumeStore>((set, get) => ({
  id: null,
  title: "",
  templateId: "classic",
  data: defaultResumeData,
  previewData: cloneData(defaultResumeData),
  dirty: false,
  saving: false,

  setResume: (r) =>
    set({
      id: r.id,
      title: r.title,
      templateId: r.templateId,
      data: r.data,
      previewData: cloneData(r.data),
      dirty: false,
    }),

  refreshPreview: () =>
    set({ previewData: cloneData(get().data) }),

  updateData: (patch) => {
    set((s) => ({ data: { ...s.data, ...patch }, dirty: true }));
  },

  updateTitle: (title) => {
    set({ title, dirty: true });
  },

  setTemplate: (templateId) => {
    set({ templateId, dirty: true });
  },

  saveResume: async () => {
    const { id, title, templateId, data } = get();
    if (!id) return;
    set({ saving: true });
    try {
      await updateResume(id, { title, templateId, data });
      set({ dirty: false });
    } finally {
      set({ saving: false });
    }
  },
}));
