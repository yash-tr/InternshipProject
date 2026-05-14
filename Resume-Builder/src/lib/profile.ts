import { currentUser } from "@clerk/nextjs/server";
import { eq } from "drizzle-orm";
import { db } from "@lib/db";
import { profiles } from "@lib/db/schema";

/**
 * Ensures a profile exists for the current user.
 * Creates one if it doesn't exist, using Clerk user data.
 * Returns the profile ID.
 */
export async function ensureProfile(userId: string): Promise<string> {
  // Check if profile already exists
  const [existing] = await db
    .select()
    .from(profiles)
    .where(eq(profiles.id, userId))
    .limit(1);

  if (existing) {
    return existing.id;
  }

  // Get user email from Clerk
  const user = await currentUser();
  if (!user) {
    throw new Error("User not found in Clerk");
  }

  const email = user.emailAddresses[0]?.emailAddress || user.primaryEmailAddress?.emailAddress;
  if (!email) {
    throw new Error("User email not found");
  }

  // Create new profile
  // Handle race condition: if profile was created between check and insert
  try {
    await db.insert(profiles).values({
      id: userId,
      email,
      plan: "free",
    });
  } catch (error: any) {
    // If profile already exists (unique constraint violation), that's fine
    // Check again to return the existing profile
    const [existing] = await db
      .select()
      .from(profiles)
      .where(eq(profiles.id, userId))
      .limit(1);
    
    if (existing) {
      return existing.id;
    }
    
    // If it's a different error, rethrow it
    throw error;
  }

  return userId;
}

/**
 * Get the current user's profile (including plan). Returns null if not found.
 */
export async function getProfile(userId: string) {
  const [profile] = await db
    .select()
    .from(profiles)
    .where(eq(profiles.id, userId))
    .limit(1);
  return profile ?? null;
}
