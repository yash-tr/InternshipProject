"use client";

import { useResumeStore } from "@/lib/resume-store";
import { createId } from "@paralleldrive/cuid2";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { UpdatePreviewButton } from "../UpdatePreviewButton";
import type { ResumeEducationItem } from "@appTypes/resume";

export function Education() {
  const { data, updateData } = useResumeStore();
  const education = data.education;

  const addEntry = () => {
    const newEntry: ResumeEducationItem = {
      id: createId(),
      school: "",
      degree: "",
      fieldOfStudy: "",
      location: "",
      startDate: "",
      endDate: "",
      current: false,
    };
    updateData({ education: [...education, newEntry] });
  };

  const removeEntry = (id: string) => {
    updateData({
      education: education.filter((e) => e.id !== id),
    });
  };

  const updateEntry = (id: string, patch: Partial<ResumeEducationItem>) => {
    updateData({
      education: education.map((e) =>
        e.id === id ? { ...e, ...patch } : e
      ),
    });
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Education</CardTitle>
        <div className="flex items-center gap-2">
          <UpdatePreviewButton />
          <Button type="button" variant="outline" size="sm" onClick={addEntry}>
            Add entry
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {education.map((entry) => (
          <div key={entry.id} className="rounded-lg border p-4 space-y-4">
            <div className="grid gap-2">
              <Label>Institution</Label>
              <Input
                value={entry.school}
                onChange={(e) => updateEntry(entry.id, { school: e.target.value })}
                placeholder="School or university"
              />
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <div>
                <Label>Degree</Label>
                <Input
                  value={entry.degree}
                  onChange={(e) => updateEntry(entry.id, { degree: e.target.value })}
                  placeholder="e.g. B.S."
                />
              </div>
              <div>
                <Label>Field of study</Label>
                <Input
                  value={entry.fieldOfStudy}
                  onChange={(e) => updateEntry(entry.id, { fieldOfStudy: e.target.value })}
                  placeholder="e.g. Computer Science"
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
                  placeholder="e.g. 2018"
                />
              </div>
              <div>
                <Label>End date</Label>
                <Input
                  type="text"
                  value={entry.endDate}
                  onChange={(e) => updateEntry(entry.id, { endDate: e.target.value })}
                  placeholder="e.g. 2022"
                  disabled={entry.current}
                />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id={`edu-current-${entry.id}`}
                checked={entry.current}
                onChange={(e) => updateEntry(entry.id, { current: e.target.checked })}
                className="h-4 w-4 rounded border"
              />
              <Label htmlFor={`edu-current-${entry.id}`}>Currently enrolled</Label>
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
