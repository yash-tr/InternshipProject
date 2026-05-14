import { neon } from "@neondatabase/serverless";
import { drizzle } from "drizzle-orm/neon-http";
import * as schema from "./schema";

if (!process.env.DATABASE_URL) {
  throw new Error("DATABASE_URL environment variable is not set");
}

// Validate DATABASE_URL format
const dbUrl = process.env.DATABASE_URL;
if (!dbUrl.startsWith("postgresql://") && !dbUrl.startsWith("postgres://")) {
  throw new Error(
    `Invalid DATABASE_URL format. Expected postgresql:// or postgres://, got: ${dbUrl.substring(0, 20)}...`
  );
}

const sql = neon(dbUrl);

export const db = drizzle(sql, { schema });

