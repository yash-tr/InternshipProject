import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { ensureProfile, getProfile } from "@/lib/profile";
import { TemplatePicker } from "@/components/templates/TemplatePicker";

export default async function TemplatesPage({
  searchParams,
}: {
  searchParams: Promise<{ resumeId?: string }>;
}) {
  const { userId } = await auth();
  if (!userId) {
    redirect("/sign-in");
  }

  await ensureProfile(userId);
  const profile = await getProfile(userId);
  const plan = profile?.plan ?? "free";
  const { resumeId } = await searchParams;

  return (
    <main className="container mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-semibold tracking-tight">
          Choose a template
        </h1>
        <p className="text-muted-foreground mt-1">
          Select a template for your resume. Pro templates require an upgrade.
        </p>
      </div>
      <TemplatePicker plan={plan} resumeId={resumeId ?? null} />
    </main>
  );
}
