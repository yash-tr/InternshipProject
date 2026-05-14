"use client";

import { useEffect } from "react";
import { useResumeStore } from "@/lib/resume-store";

export function UnsavedChangesGuard() {
  const dirty = useResumeStore((s) => s.dirty);
  const saving = useResumeStore((s) => s.saving);

  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => {
      if (dirty || saving) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty, saving]);

  return null;
}

