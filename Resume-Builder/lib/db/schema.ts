import { pgTable, text, jsonb, timestamp } from "drizzle-orm/pg-core";

export const profiles = pgTable("profiles", {
  id: text("id").primaryKey(),
  email: text("email").notNull(),
  plan: text("plan").default("free"),
  createdAt: timestamp("created_at").defaultNow(),
});

export const resumes = pgTable("resumes", {
  id: text("id").primaryKey(), // CUID2 set in app, not DB default
  userId: text("user_id")
    .references(() => profiles.id, { onDelete: "cascade" })
    .notNull(),
  title: text("title").default("Untitled Resume"),
  templateId: text("template_id").default("classic"),
  data: jsonb("data").notNull().default({}),
  createdAt: timestamp("created_at").defaultNow(),
  updatedAt: timestamp("updated_at").defaultNow(),
});

