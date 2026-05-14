import { z } from "zod";

export const resumeContactSchema = z.object({
  fullName: z.string().min(1),
  email: z.string().email(),
  phone: z.string().optional().default(""),
  location: z.string().optional().default(""),
  headline: z.string().optional().default(""),
  website: z.string().url().optional().or(z.literal("")),
  linkedin: z.string().url().optional().or(z.literal("")),
  github: z.string().url().optional().or(z.literal("")),
});

export const resumeExperienceItemSchema = z.object({
  id: z.string(),
  company: z.string().min(1),
  role: z.string().min(1),
  location: z.string().optional().default(""),
  startDate: z.string().min(1),
  endDate: z.string().optional().default(""),
  current: z.boolean().default(false),
  summary: z.string().optional().default(""),
  highlights: z.array(z.string()).default([]),
});

export const resumeEducationItemSchema = z.object({
  id: z.string(),
  school: z.string().min(1),
  degree: z.string().optional().default(""),
  fieldOfStudy: z.string().optional().default(""),
  location: z.string().optional().default(""),
  startDate: z.string().optional().default(""),
  endDate: z.string().optional().default(""),
  current: z.boolean().default(false),
});

export const resumeProjectItemSchema = z.object({
  id: z.string(),
  name: z.string().min(1),
  link: z.string().url().optional().or(z.literal("")),
  description: z.string().optional().default(""),
  technologies: z.array(z.string()).default([]),
});

export const resumeSkillGroupSchema = z.object({
  id: z.string(),
  label: z.string().min(1),
  skills: z.array(z.string()).default([]),
});

export const resumeDataSchema = z.object({
  contact: resumeContactSchema,
  summary: z.string().optional().default(""),
  experiences: z.array(resumeExperienceItemSchema).default([]),
  education: z.array(resumeEducationItemSchema).default([]),
  projects: z.array(resumeProjectItemSchema).default([]),
  skills: z.array(resumeSkillGroupSchema).default([]),
  extras: z.record(z.string(), z.unknown()).optional().default({}),
});

export type ResumeDataInput = z.input<typeof resumeDataSchema>;
export type ResumeData = z.output<typeof resumeDataSchema>;

