"use client";

import { useResumeStore } from "@/lib/resume-store";
import { Button } from "@/components/ui/button";

export function UpdatePreviewButton() {
  const refreshPreview = useResumeStore((s) => s.refreshPreview);

  return (
    <Button
      type="button"
      variant="secondary"
      size="sm"
      onClick={refreshPreview}
    >
      Update preview
    </Button>
  );
}
