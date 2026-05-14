import type { ResumeData } from "@appTypes/resume";

export interface Resume {
  id: string;
  userId: string;
  title: string | null;
  templateId: string | null;
  data: ResumeData;
  createdAt: Date | null;
  updatedAt: Date | null;
}

export interface CreateResumeResponse {
  id: string;
}

export interface UpdateResumeRequest {
  data?: ResumeData;
  title?: string;
  templateId?: string;
}

/**
 * List all resumes for the current user
 */
export async function listResumes(): Promise<Resume[]> {
  const res = await fetch("/api/resume");
  if (!res.ok) {
    throw new Error(`Failed to list resumes: ${res.statusText}`);
  }
  return res.json();
}

/**
 * Create a new resume
 */
export async function createResume(): Promise<CreateResumeResponse> {
  const res = await fetch("/api/resume", {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error(`Failed to create resume: ${res.statusText}`);
  }
  return res.json();
}

/**
 * Get a single resume by ID
 */
export async function getResume(id: string): Promise<Resume> {
  const res = await fetch(`/api/resume/${id}`);
  if (!res.ok) {
    if (res.status === 404) {
      throw new Error(`Resume not found: ${id}`);
    }
    throw new Error(`Failed to get resume: ${res.statusText}`);
  }
  return res.json();
}

/**
 * Update a resume
 */
export async function updateResume(
  id: string,
  updates: UpdateResumeRequest
): Promise<Resume> {
  const res = await fetch(`/api/resume/${id}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(updates),
  });
  if (!res.ok) {
    if (res.status === 404) {
      throw new Error(`Resume not found: ${id}`);
    }
    throw new Error(`Failed to update resume: ${res.statusText}`);
  }
  return res.json();
}

/**
 * Delete a resume
 */
export async function deleteResume(id: string): Promise<void> {
  const res = await fetch(`/api/resume/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    if (res.status === 404) {
      throw new Error(`Resume not found: ${id}`);
    }
    throw new Error(`Failed to delete resume: ${res.statusText}`);
  }
}
