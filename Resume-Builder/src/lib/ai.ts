import type { ResumeData } from "@appTypes/resume";

async function post(body: object) {
  const r = await fetch("/api/ai/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const err = await r.text();
    throw new Error(err || `AI API error: ${r.status}`);
  }
  return r.json() as Promise<{ result: string } | { result: string[] }>;
}

export const aiApi = {
  generateSummary: (data: ResumeData) =>
    post({
      type: "summary",
      context: {
        role: data.experiences[0]?.role ?? data.contact?.headline ?? "professional",
        companies: data.experiences.map((e) => e.company).filter(Boolean),
      },
    }),

  improveBullet: (bullet: string, role: string) =>
    post({
      type: "improve_bullet",
      context: { bullet, role },
    }),

  suggestSkills: (role: string, existingSkills: string[]) =>
    post({
      type: "suggest_skills",
      context: { role, existingSkills },
    }),
};
