"use client";

import { useResumeStore } from "@/lib/resume-store";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { UpdatePreviewButton } from "../UpdatePreviewButton";

export function PersonalInfo() {
  const { data, updateData } = useResumeStore();
  const c = data.contact;

  const update = (field: keyof typeof c, value: string) => {
    updateData({
      contact: { ...c, [field]: value },
    });
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle>Personal info</CardTitle>
        <UpdatePreviewButton />
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-2">
          <Label htmlFor="fullName">Full name</Label>
          <Input
            id="fullName"
            value={c.fullName}
            onChange={(e) => update("fullName", e.target.value)}
            placeholder="Your name"
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            value={c.email}
            onChange={(e) => update("email", e.target.value)}
            placeholder="email@example.com"
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="phone">Phone</Label>
          <Input
            id="phone"
            value={c.phone}
            onChange={(e) => update("phone", e.target.value)}
            placeholder="+1 234 567 8900"
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="location">Location</Label>
          <Input
            id="location"
            value={c.location}
            onChange={(e) => update("location", e.target.value)}
            placeholder="City, Country"
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="headline">Headline</Label>
          <Input
            id="headline"
            value={c.headline}
            onChange={(e) => update("headline", e.target.value)}
            placeholder="e.g. Software Engineer"
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="website">Website</Label>
          <Input
            id="website"
            value={c.website ?? ""}
            onChange={(e) => update("website", e.target.value)}
            placeholder="https://..."
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="linkedin">LinkedIn</Label>
          <Input
            id="linkedin"
            value={c.linkedin ?? ""}
            onChange={(e) => update("linkedin", e.target.value)}
            placeholder="https://linkedin.com/in/..."
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="github">GitHub</Label>
          <Input
            id="github"
            value={c.github ?? ""}
            onChange={(e) => update("github", e.target.value)}
            placeholder="https://github.com/..."
          />
        </div>
      </CardContent>
    </Card>
  );
}
