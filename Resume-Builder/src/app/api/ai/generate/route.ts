import { GoogleGenAI } from "@google/genai";
import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const ai = new GoogleGenAI({
  apiKey: process.env.GEMINI_API_KEY,
});

function buildPrompt(type: string, context: Record<string, unknown>): string {
  switch (type) {
    case "summary":
      return `Write a 3-sentence professional resume summary for a ${context.role ?? "professional"} with experience at: ${Array.isArray(context.companies) ? (context.companies as string[]).join(", ") : "various companies"}. Use active voice. No filler phrases. Return only the summary text.`;

    case "improve_bullet":
      return `Improve this resume bullet point. Strong action verb, quantify results if possible, keep under 20 words.
Role: ${context.role ?? "N/A"}
Original: "${context.bullet ?? ""}"
Return only the improved text.`;

    case "suggest_skills":
      return `Suggest 8 skills for a ${context.role ?? "professional"} professional. Exclude: ${Array.isArray(context.existingSkills) ? (context.existingSkills as string[]).join(", ") || "none" : "none"}. Return a JSON array of strings only. No markdown, no explanation. Example: ["TypeScript", "Node.js"]`;

    default:
      throw new Error("Unknown type");
  }
}

export async function POST(req: Request) {
  const { userId } = await auth();
  if (!userId) {
    return new NextResponse("Unauthorized", { status: 401 });
  }

  if (!process.env.GEMINI_API_KEY) {
    return new NextResponse("GEMINI_API_KEY not configured", { status: 500 });
  }

  const { type, context } = (await req.json()) as {
    type: string;
    context: Record<string, unknown>;
  };

  const prompt = buildPrompt(type, context);

  const response = await ai.models.generateContent({
    model: "gemini-3-flash-preview",
    contents: prompt,
  });

  const text = (response?.text ?? "").trim();

  if (type === "suggest_skills") {
    try {
      const parsed = JSON.parse(text) as unknown;
      const arr = Array.isArray(parsed) ? parsed : [text];
      return NextResponse.json({ result: arr });
    } catch {
      const skills = text
        .split("\n")
        .map((s) => s.replace(/^[-*\d.]\s*/, "").trim())
        .filter(Boolean);
      return NextResponse.json({ result: skills });
    }
  }

  return NextResponse.json({ result: text });
}
