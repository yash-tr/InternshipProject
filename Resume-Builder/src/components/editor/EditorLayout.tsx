"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useResumeStore } from "@/lib/resume-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { ArrowLeft as ArrowLeftIcon } from "lucide-react";
import { PersonalInfo } from "./sections/PersonalInfo";
import { Summary } from "./sections/Summary";
import { WorkExperience } from "./sections/WorkExperience";
import { Education } from "./sections/Education";
import { Skills } from "./sections/Skills";

const PDFDownloadButton = dynamic(
  () =>
    import("@/components/pdf/PDFDownloadButton").then((m) => m.PDFDownloadButton),
  {
    ssr: false,
    loading: () => (
      <Button variant="outline" size="sm" disabled>
        Preparing…
      </Button>
    ),
  }
);

const PDFPreviewPanel = dynamic(
  () =>
    import("@/components/pdf/PDFPreviewPanel").then((m) => m.PDFPreviewPanel),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full min-h-[400px] items-center justify-center rounded-lg border border-dashed text-muted-foreground">
        Loading preview…
      </div>
    ),
  }
);

export function EditorLayout() {
  const id = useResumeStore((s) => s.id);
  const title = useResumeStore((s) => s.title);
  const updateTitle = useResumeStore((s) => s.updateTitle);
  const saving = useResumeStore((s) => s.saving);
  const dirty = useResumeStore((s) => s.dirty);
  const saveResume = useResumeStore((s) => s.saveResume);
  const [activeTab, setActiveTab] = useState<"edit" | "preview">("edit");

  const saveRef = useRef(saveResume);
  useEffect(() => {
    saveRef.current = saveResume;
  }, [saveResume]);

  const statusLabel = saving
    ? "Saving…"
    : dirty
      ? "Unsaved changes"
      : "Saved";
  const statusVariant = saving
    ? "bg-muted text-muted-foreground"
    : dirty
      ? "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400"
      : "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400";

  const titleSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const scheduleTitleSave = () => {
    if (titleSaveTimer.current) {
      clearTimeout(titleSaveTimer.current);
    }
    titleSaveTimer.current = setTimeout(() => {
      void saveRef.current();
    }, 600);
  };

  return (
    <div className="flex h-screen flex-col">
      <header className="flex shrink-0 items-center gap-3 border-b px-4 py-3">
        <Button variant="ghost" size="icon" className="shrink-0" asChild>
          <Link href="/dashboard" aria-label="Back to resumes">
            <ArrowLeftIcon className="h-4 w-4" />
          </Link>
        </Button>
        <Input
          value={title}
          onChange={(e) => updateTitle(e.target.value)}
          onBlur={scheduleTitleSave}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              e.currentTarget.blur();
              scheduleTitleSave();
            }
          }}
          className="max-w-xs border-0 text-lg font-semibold shadow-none focus-visible:ring-0"
          placeholder="Resume title"
        />
        <span
          className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium", statusVariant)}
        >
          {statusLabel}
        </span>
        <Button
          type="button"
          variant="default"
          size="sm"
          onClick={async () => {
            try {
              await saveResume();
            } catch {
              toast.error("Failed to save. Please try again.");
            }
          }}
          disabled={saving || !dirty}
        >
          Save
        </Button>
        {id ? (
          <Button variant="outline" size="sm" asChild>
            <Link href={`/templates?resumeId=${id}`}>Change template</Link>
          </Button>
        ) : null}
        <span className="ml-auto">
          <DownloadButtonWrapper />
        </span>
      </header>

      <div className="flex flex-1 min-h-0 lg:flex-row flex-col">
        {/* Desktop: 60/40 split */}
        <div className="hidden lg:flex flex-1 min-h-0 overflow-hidden">
          <div className="w-[60%] overflow-y-auto border-r p-6">
            <ResumeForm />
          </div>
          <div className="w-[40%] overflow-y-auto bg-muted/30 p-6 flex flex-col">
            <PDFPreviewPanel />
          </div>
        </div>

        {/* Mobile: tabs */}
        <Tabs
          value={activeTab}
          onValueChange={(v) => setActiveTab(v as "edit" | "preview")}
          className="flex flex-1 flex-col lg:hidden overflow-hidden"
        >
          <TabsList className="mx-4 mt-2 shrink-0 w-auto">
            <TabsTrigger value="edit">Edit</TabsTrigger>
            <TabsTrigger value="preview">Preview</TabsTrigger>
          </TabsList>
          <TabsContent value="edit" className="flex-1 overflow-y-auto mt-0 p-4">
            <ResumeForm />
          </TabsContent>
          <TabsContent value="preview" className="flex-1 overflow-y-auto mt-0 p-4 bg-muted/30 flex flex-col">
            <PDFPreviewPanel />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

function DownloadButtonWrapper() {
  const data = useResumeStore((s) => s.data);
  const templateId = useResumeStore((s) => s.templateId);
  return <PDFDownloadButton data={data} templateId={templateId} />;
}

function ResumeForm() {
  return (
    <div className="space-y-8">
      <PersonalInfo />
      <Summary />
      <WorkExperience />
      <Education />
      <Skills />
    </div>
  );
}

