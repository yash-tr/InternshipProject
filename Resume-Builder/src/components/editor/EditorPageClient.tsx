"use client";

import { useEffect } from "react";
import { useResumeStore } from "@/lib/resume-store";
import { EditorLayout } from "./EditorLayout";
import { UnsavedChangesGuard } from "./UnsavedChangesGuard";
import type { ResumeData } from "@appTypes/resume";

export interface EditorInitialData {
  id: string;
  title: string;
  templateId: string;
  data: ResumeData;
}

interface EditorPageClientProps {
  initialData: EditorInitialData;
}

export function EditorPageClient({ initialData }: EditorPageClientProps) {
  const setResume = useResumeStore((s) => s.setResume);

  useEffect(() => {
    setResume({
      id: initialData.id,
      title: initialData.title,
      templateId: initialData.templateId,
      data: initialData.data,
    });
  }, [initialData.id, setResume]);

  return (
    <>
      <UnsavedChangesGuard />
      <EditorLayout />
    </>
  );
}
