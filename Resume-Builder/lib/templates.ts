export const TEMPLATES = [
  {
    id: "classic",
    name: "Classic",
    tier: "free",
    description: "Traditional, ATS-friendly",
  },
  {
    id: "modern",
    name: "Modern",
    tier: "free",
    description: "Two-column, visual",
  },
  {
    id: "premium",
    name: "Premium",
    tier: "pro",
    description: "Bold header, timeline layout",
  },
] as const;

export type TemplateId = (typeof TEMPLATES)[number]["id"];
export type TemplateTier = (typeof TEMPLATES)[number]["tier"];
