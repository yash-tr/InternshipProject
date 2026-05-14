"use client";

import { useResumeStore } from "@/lib/resume-store";
import { createId } from "@paralleldrive/cuid2";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { UpdatePreviewButton } from "../UpdatePreviewButton";
import { AIAssistButton } from "../AIAssistButton";
import { aiApi } from "@/lib/ai";
import type { ResumeExperienceItem } from "@appTypes/resume";

export function WorkExperience() {
  const { data, updateData } = useResumeStore();
  const experiences = data.experiences;

  const addEntry = () => {
    const newEntry: ResumeExperienceItem = {
      id: createId(),
      company: "",
      role: "",
      location: "",
      startDate: "",
      endDate: "",
      current: false,
      summary: "",
      highlights: [],
    };
    updateData({ experiences: [...experiences, newEntry] });
  };

  const removeEntry = (id: string) => {
    updateData({
      experiences: experiences.filter((e) => e.id !== id),
    });
  };

  const updateEntry = (id: string, patch: Partial<ResumeExperienceItem>) => {
    updateData({
      experiences: experiences.map((e) =>
        e.id === id ? { ...e, ...patch } : e
      ),
    });
  };

  const updateHighlight = (
    entryId: string,
    index: number,
    value: string
  ) => {
    updateData({
      experiences: experiences.map((e) => {
        if (e.id !== entryId) return e;
        const next = [...e.highlights];
        next[index] = value;
        return { ...e, highlights: next };
      }),
    });
  };

  const addHighlight = (entryId: string) => {
    updateData({
      experiences: experiences.map((e) =>
        e.id === entryId
          ? { ...e, highlights: [...e.highlights, ""] }
          : e
      ),
    });
  };

  const removeHighlight = (entryId: string, index: number) => {
    updateData({
      experiences: experiences.map((e) => {
        if (e.id !== entryId) return e;
        return {
          ...e,
          highlights: e.highlights.filter((_, i) => i !== index),
        };
      }),
    });
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Work experience</CardTitle>
        <div className="flex items-center gap-2">
          <UpdatePreviewButton />
          <Button type="button" variant="outline" size="sm" onClick={addEntry}>
            Add entry
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {experiences.map((entry) => (
          <div
            key={entry.id}
            className="rounded-lg border p-4 space-y-4"
          >
            <div className="grid gap-2 sm:grid-cols-2">
              <div>
                <Label>Company</Label>
                <Input
                  value={entry.company}
                  onChange={(e) => updateEntry(entry.id, { company: e.target.value })}
                  placeholder="Company name"
                />
              </div>
              <div>
                <Label>Role</Label>
                <Input
                  value={entry.role}
                  onChange={(e) => updateEntry(entry.id, { role: e.target.value })}
                  placeholder="Job title"
                />
              </div>
            </div>
            <div className="grid gap-2">
              <Label>Location</Label>
              <Input
                value={entry.location}
                onChange={(e) => updateEntry(entry.id, { location: e.target.value })}
                placeholder="City, Country"
              />
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <div>
                <Label>Start date</Label>
                <Input
                  type="text"
                  value={entry.startDate}
                  onChange={(e) => updateEntry(entry.id, { startDate: e.target.value })}
                  placeholder="e.g. Jan 2020"
                />
              </div>
              <div>
                <Label>End date</Label>
                <Input
                  type="text"
                  value={entry.endDate}
                  onChange={(e) => updateEntry(entry.id, { endDate: e.target.value })}
                  placeholder="e.g. Present"
                  disabled={entry.current}
                />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id={`current-${entry.id}`}
                checked={entry.current}
                onChange={(e) => updateEntry(entry.id, { current: e.target.checked })}
                className="h-4 w-4 rounded border"
              />
              <Label htmlFor={`current-${entry.id}`}>Current role</Label>
            </div>
            <div className="grid gap-2">
              <Label>Summary</Label>
              <Input
                value={entry.summary}
                onChange={(e) => updateEntry(entry.id, { summary: e.target.value })}
                placeholder="Brief role description"
              />
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>Bullet points</Label>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => addHighlight(entry.id)}
                >
                  Add bullet
                </Button>
              </div>
              {entry.highlights.length === 0 && (
                <p className="text-xs text-muted-foreground">
                  Click + to add an achievement.
                </p>
              )}
              {entry.highlights.map((bullet, i) => (
                <div key={i} className="flex gap-2 items-start">
                  <Input
                    value={bullet}
                    onChange={(e) => updateHighlight(entry.id, i, e.target.value)}
                    placeholder="Achievement or responsibility"
                    className="flex-1"
                  />
                  <AIAssistButton
                    label="AI Improve"
                    size="icon"
                    variant="ghost"
                    onGenerate={async () => {
                      const res = await aiApi.improveBullet(bullet, entry.role);
                      return (res as { result: string }).result;
                    }}
                    onAccept={(result) => {
                      const text = typeof result === "string" ? result : result[0] ?? "";
                      updateHighlight(entry.id, i, text);
                    }}
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => removeHighlight(entry.id, i)}
                    aria-label="Remove bullet"
                  >
                    ×
                  </Button>
                </div>
              ))}
            </div>
            <Button
              type="button"
              variant="destructive"
              size="sm"
              onClick={() => removeEntry(entry.id)}
            >
              Remove entry
            </Button>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
