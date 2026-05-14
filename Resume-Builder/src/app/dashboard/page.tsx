import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { desc, eq } from "drizzle-orm";
import { db } from "@lib/db";
import { resumes } from "@lib/db/schema";
import { ResumeCard } from "@/components/dashboard/resume-card";
import { NewResumeButton } from "@/components/dashboard/new-resume-button";
import { DashboardToasts } from "@/components/dashboard/DashboardToasts";
import { ensureProfile } from "@/lib/profile";
import type { Resume } from "@/lib/api";
import type { ResumeData } from "@appTypes/resume";
import type { InferSelectModel } from "drizzle-orm";

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<{ resumeNotFound?: string }>;
}) {
  const { userId } = await auth();

  if (!userId) {
    redirect("/sign-in");
  }

  // Ensure profile exists for this user (creates if doesn't exist)
  try {
    await ensureProfile(userId);
  } catch (error) {
    console.error("Failed to ensure profile:", error);
    // Continue anyway - profile creation might fail if tables don't exist
  }

  const { resumeNotFound } = await searchParams;

  let userResumes: InferSelectModel<typeof resumes>[] = [];
  try {
    userResumes = await db
      .select()
      .from(resumes)
      .where(eq(resumes.userId, userId))
      .orderBy(desc(resumes.updatedAt));
  } catch (error) {
    console.error("Database query error:", error);
    // If tables don't exist yet, return empty array
    // User should run: npx drizzle-kit push
    userResumes = [];
  }

  return (
    <main className="container mx-auto px-4 py-8">
      <DashboardToasts resumeNotFound={Boolean(resumeNotFound)} />
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-3xl font-semibold tracking-tight">My Resumes</h1>
        <NewResumeButton />
      </div>

      {userResumes.length === 0 ? (
        <div className="flex min-h-[400px] flex-col items-center justify-center rounded-lg border border-dashed">
          <div className="flex flex-col items-center gap-4 text-center">
            <h2 className="text-xl font-semibold">Create your first resume</h2>
            <p className="text-muted-foreground max-w-md">
              Start from a professional template and export a polished PDF in minutes.
            </p>
            <NewResumeButton />
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {userResumes.map((resume) => (
            <ResumeCard
              key={resume.id}
              resume={{
                ...resume,
                data: resume.data as ResumeData,
              } as Resume}
            />
          ))}
        </div>
      )}
    </main>
  );
}
