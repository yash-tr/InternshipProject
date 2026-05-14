import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { eq } from "drizzle-orm";
import { db } from "@lib/db";
import { resumes } from "@lib/db/schema";
import { EditorPageClient } from "@/components/editor/EditorPageClient";
import { defaultResumeData, type ResumeData } from "@appTypes/resume";

export default async function EditorPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { userId } = await auth();
  if (!userId) {
    redirect("/sign-in");
  }

  const { id } = await params;
  const [resume] = await db
    .select()
    .from(resumes)
    .where(eq(resumes.id, id))
    .limit(1);

  if (!resume || resume.userId !== userId) {
    redirect("/dashboard?resumeNotFound=1");
  }

  const rawData = (resume.data ?? {}) as Partial<ResumeData>;
  const data: ResumeData = {
    ...defaultResumeData,
    ...rawData,
    contact: { ...defaultResumeData.contact, ...rawData.contact },
    experiences: rawData.experiences ?? defaultResumeData.experiences,
    education: rawData.education ?? defaultResumeData.education,
    projects: rawData.projects ?? defaultResumeData.projects,
    skills: rawData.skills ?? defaultResumeData.skills,
  };

  const initialData = {
    id: resume.id,
    title: resume.title ?? "Untitled Resume",
    templateId: resume.templateId ?? "classic",
    data,
  };

  return <EditorPageClient initialData={initialData} />;
}
