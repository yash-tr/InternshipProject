import { auth } from "@clerk/nextjs/server";
import { eq } from "drizzle-orm";
import { NextResponse } from "next/server";
import { db } from "@lib/db";
import { resumes } from "@lib/db/schema";
import type { ResumeData } from "@appTypes/resume";

// GET — get a single resume by ID (verify ownership)
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { userId } = await auth();
  if (!userId) {
    return new NextResponse("Unauthorized", { status: 401 });
  }

  const { id } = await params;
  const [resume] = await db
    .select()
    .from(resumes)
    .where(eq(resumes.id, id))
    .limit(1);

  if (!resume) {
    return new NextResponse("Not Found", { status: 404 });
  }

  if (resume.userId !== userId) {
    return new NextResponse("Forbidden", { status: 403 });
  }

  return NextResponse.json(resume);
}

// PUT — update resume (verify ownership, update data, title, templateId, and set updatedAt)
export async function PUT(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { userId } = await auth();
  if (!userId) {
    return new NextResponse("Unauthorized", { status: 401 });
  }

  const { id } = await params;
  const [existing] = await db
    .select()
    .from(resumes)
    .where(eq(resumes.id, id))
    .limit(1);

  if (!existing) {
    return new NextResponse("Not Found", { status: 404 });
  }

  if (existing.userId !== userId) {
    return new NextResponse("Forbidden", { status: 403 });
  }

  const body = await request.json();
  const { data, title, templateId } = body as {
    data?: ResumeData;
    title?: string;
    templateId?: string;
  };

  const [updated] = await db
    .update(resumes)
    .set({
      data: data ?? existing.data,
      title: title ?? existing.title,
      templateId: templateId ?? existing.templateId,
      updatedAt: new Date(),
    })
    .where(eq(resumes.id, id))
    .returning();

  return NextResponse.json(updated);
}

// DELETE — delete resume (verify ownership)
export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { userId } = await auth();
  if (!userId) {
    return new NextResponse("Unauthorized", { status: 401 });
  }

  const { id } = await params;
  const [existing] = await db
    .select()
    .from(resumes)
    .where(eq(resumes.id, id))
    .limit(1);

  if (!existing) {
    return new NextResponse("Not Found", { status: 404 });
  }

  if (existing.userId !== userId) {
    return new NextResponse("Forbidden", { status: 403 });
  }

  await db.delete(resumes).where(eq(resumes.id, id));

  return new NextResponse(null, { status: 204 });
}
