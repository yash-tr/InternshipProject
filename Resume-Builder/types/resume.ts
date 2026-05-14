export interface ResumeContact {
  fullName: string;
  email: string;
  phone: string;
  location: string;
  headline: string;
  website?: string;
  linkedin?: string;
  github?: string;
}

export interface ResumeExperienceItem {
  id: string;
  company: string;
  role: string;
  location: string;
  startDate: string;
  endDate: string;
  current: boolean;
  summary: string;
  highlights: string[];
}

export interface ResumeEducationItem {
  id: string;
  school: string;
  degree: string;
  fieldOfStudy: string;
  location: string;
  startDate: string;
  endDate: string;
  current: boolean;
}

export interface ResumeProjectItem {
  id: string;
  name: string;
  link?: string;
  description: string;
  technologies: string[];
}

export interface ResumeSkillGroup {
  id: string;
  label: string;
  skills: string[];
}

export interface ResumeData {
  contact: ResumeContact;
  summary: string;
  experiences: ResumeExperienceItem[];
  education: ResumeEducationItem[];
  projects: ResumeProjectItem[];
  skills: ResumeSkillGroup[];
  extras?: Record<string, unknown>;
}

export const defaultResumeData: ResumeData = {
  contact: {
    fullName: "",
    email: "",
    phone: "",
    location: "",
    headline: "",
    website: "",
    linkedin: "",
    github: "",
  },
  summary: "",
  experiences: [],
  education: [],
  projects: [],
  skills: [],
  extras: {},
};

