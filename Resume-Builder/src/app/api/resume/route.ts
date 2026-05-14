import { auth } from "@clerk/nextjs/server";
import { createId } from "@paralleldrive/cuid2";
import { desc, eq } from "drizzle-orm";
import { NextResponse } from "next/server";
import { db } from "@lib/db";
import { resumes } from "@lib/db/schema";
import { ensureProfile } from "@/lib/profile";
import { defaultResumeData } from "@appTypes/resume";

// GET — list user's resumes
export async function GET() {
  const { userId } = await auth();
  if (!userId) {
    return new NextResponse("Unauthorized", { status: 401 });
  }

  const rows = await db
    .select()
    .from(resumes)
    .where(eq(resumes.userId, userId))
    .orderBy(desc(resumes.updatedAt));

  return NextResponse.json(rows);
}

// POST — create new resume, ID generated here not in DB
export async function POST() {
  const { userId } = await auth();
  if (!userId) {
    return new NextResponse("Unauthorized", { status: 401 });
  }

  // Ensure profile exists before creating resume
  try {
    await ensureProfile(userId);
  } catch (error) {
    console.error("Failed to ensure profile:", error);
    return new NextResponse("Failed to create profile", { status: 500 });
  }

  const id = createId();
  await db.insert(resumes).values({
    id,
    userId,
    data: defaultResumeData,
  });

  return NextResponse.json({ id });
}
