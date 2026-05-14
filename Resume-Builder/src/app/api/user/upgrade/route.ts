import { auth } from "@clerk/nextjs/server";
import { eq } from "drizzle-orm";
import { NextResponse } from "next/server";
import { db } from "@lib/db";
import { profiles } from "@lib/db/schema";

/**
 * Simulated upgrade: sets profiles.plan = 'pro' (no payment).
 */
export async function POST() {
  const { userId } = await auth();
  if (!userId) {
    return new NextResponse("Unauthorized", { status: 401 });
  }

  await db
    .update(profiles)
    .set({ plan: "pro" })
    .where(eq(profiles.id, userId));

  return NextResponse.json({ plan: "pro" });
}
