"use client";

import { useResumeStore } from "@/lib/resume-store";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { UpdatePreviewButton } from "../UpdatePreviewButton";
import { AIAssistButton } from "../AIAssistButton";
import { aiApi } from "@/lib/ai";

export function Summary() {
  const { data, updateData } = useResumeStore();

  const handleAcceptSummary = (result: string | string[]) => {
    const text = typeof result === "string" ? result : result[0] ?? "";
    updateData({ summary: text });
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle>Summary</CardTitle>
        <UpdatePreviewButton />
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-2">
          <Label htmlFor="summary">Professional summary</Label>
          <Textarea
            id="summary"
            value={data.summary}
            onChange={(e) => updateData({ summary: e.target.value })}
            placeholder="A brief overview of your experience and goals..."
            rows={4}
            className="resize-none"
          />
        </div>
        <AIAssistButton
          label="Generate with AI"
          onGenerate={async () => {
            const res = await aiApi.generateSummary(data);
            return (res as { result: string }).result;
          }}
          onAccept={handleAcceptSummary}
        />
      </CardContent>
    </Card>
  );
}
