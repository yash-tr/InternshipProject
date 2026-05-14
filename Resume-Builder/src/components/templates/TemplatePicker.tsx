"use client";

import { useRouter } from "next/navigation";
import { TEMPLATES } from "@lib/templates";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface TemplatePickerProps {
  plan: string;
  resumeId: string | null;
}

export function TemplatePicker({ plan, resumeId }: TemplatePickerProps) {
  const router = useRouter();

  const handleUpgrade = async () => {
    const res = await fetch("/api/user/upgrade", { method: "POST" });
    if (res.ok) {
      router.refresh();
    }
  };

  const applyTemplate = async (templateId: string) => {
    if (!resumeId) {
      router.push("/dashboard");
      return;
    }
    const res = await fetch(`/api/resume/${resumeId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ templateId }),
    });
    if (res.ok) {
      router.push(`/editor/${resumeId}`);
    }
  };

  return (
    <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
      {TEMPLATES.map((template) => {
        const isLocked =
          template.tier === "pro" && (plan === "free" || !plan);

        return (
          <Card key={template.id} className="flex flex-col">
            <CardHeader className="flex flex-row items-start justify-between space-y-0">
              <CardTitle>{template.name}</CardTitle>
              <Badge variant={template.tier === "pro" ? "default" : "secondary"}>
                {template.tier === "pro" ? "Pro" : "Free"}
              </Badge>
            </CardHeader>
            <CardContent className="flex-1">
              <p className="text-muted-foreground text-sm mb-4">
                {template.description}
              </p>
              <TemplatePreviewMock templateId={template.id} />
            </CardContent>
            <CardFooter>
              {isLocked ? (
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={handleUpgrade}
                >
                  Upgrade to Pro — Free Demo
                </Button>
              ) : (
                <Button
                  className="w-full"
                  onClick={() => applyTemplate(template.id)}
                >
                  Use Template
                </Button>
              )}
            </CardFooter>
          </Card>
        );
      })}
    </div>
  );
}

/** Lightweight HTML/CSS mockup of each template (no PDF). */
function TemplatePreviewMock({ templateId }: { templateId: string }) {
  if (templateId === "classic") {
    return (
      <div className="rounded border bg-white p-3 text-[10px] text-gray-800 shadow-sm">
        <div className="border-b border-gray-300 pb-1 font-bold text-xs">
          Your Name
        </div>
        <div className="mt-1 text-gray-500">Email · Phone · Location</div>
        <div className="mt-2 border-b border-gray-200 pb-0.5 text-[10px] font-semibold">
          Summary
        </div>
        <div className="mt-0.5 h-2 w-full bg-gray-100 rounded" />
        <div className="mt-2 border-b border-gray-200 pb-0.5 text-[10px] font-semibold">
          Experience
        </div>
        <div className="mt-0.5 h-2 w-4/5 bg-gray-100 rounded" />
      </div>
    );
  }
  if (templateId === "modern") {
    return (
      <div className="rounded border bg-white shadow-sm overflow-hidden flex text-[10px]">
        <div className="w-1/3 bg-teal-50 p-2">
          <div className="font-bold text-teal-700 text-xs">Name</div>
          <div className="mt-1 h-1.5 w-full bg-teal-100 rounded" />
          <div className="mt-2 text-teal-600 font-semibold">Skills</div>
          <div className="mt-0.5 h-1 w-full bg-teal-100 rounded" />
          <div className="mt-0.5 h-1 w-2/3 bg-teal-100 rounded" />
        </div>
        <div className="w-2/3 p-2 text-gray-700">
          <div className="border-b border-teal-200 pb-0.5 font-semibold text-teal-700">
            Summary
          </div>
          <div className="mt-0.5 h-2 w-full bg-gray-100 rounded" />
          <div className="mt-1.5 border-b border-teal-200 pb-0.5 font-semibold text-teal-700">
            Experience
          </div>
          <div className="mt-0.5 h-2 w-full bg-gray-100 rounded" />
        </div>
      </div>
    );
  }
  if (templateId === "premium") {
    return (
      <div className="rounded border bg-white shadow-sm overflow-hidden text-[10px]">
        <div className="bg-indigo-600 px-2 py-2 text-white">
          <div className="font-bold text-xs">Your Name</div>
          <div className="text-indigo-200 text-[10px]">Role / Headline</div>
        </div>
        <div className="p-2 text-gray-700">
          <div className="border-l-2 border-indigo-500 pl-1.5 font-semibold text-indigo-600">
            Experience
          </div>
          <div className="mt-0.5 flex gap-1">
            <div className="h-1.5 w-1.5 rounded-full bg-indigo-500 shrink-0 mt-0.5" />
            <div className="h-2 w-full bg-gray-100 rounded" />
          </div>
          <div className="mt-1 flex gap-1">
            <div className="h-1.5 w-1.5 rounded-full bg-indigo-500 shrink-0 mt-0.5" />
            <div className="h-2 w-4/5 bg-gray-100 rounded" />
          </div>
        </div>
      </div>
    );
  }
  return null;
}
