import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";

export default async function Home() {
  const { userId } = await auth();

  if (userId) {
    redirect("/dashboard");
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex flex-col items-center gap-6 text-center">
        <h1 className="text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
          Resume Builder
        </h1>
        <p className="max-w-md text-lg leading-8 text-zinc-600 dark:text-zinc-400">
          Sign in to start creating and exporting tailored resumes.
        </p>
        <p className="mt-8 text-xs text-zinc-400 dark:text-zinc-600">
          Built by Yash Tripathi &middot; tripathiyash1004@gmail.com
        </p>
      </main>
    </div>
  );
}
