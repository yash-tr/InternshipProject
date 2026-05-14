import type { Metadata } from "next";
import {
  ClerkProvider,
  Show,
  SignInButton,
  SignUpButton,
  UserButton,
} from "@clerk/nextjs";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/sonner";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Resume Builder",
  description: "AI-powered resume builder",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <ClerkProvider>
          <header className="flex items-center justify-between border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
            <div className="font-semibold">Resume Builder</div>
            <nav className="flex items-center gap-3">
              <Show when="signed-out">
                <SignInButton />
                <SignUpButton />
              </Show>
              <Show when="signed-in">
                <UserButton />
              </Show>
            </nav>
          </header>
          {children}
          <footer className="border-t border-zinc-200 px-4 py-3 text-center text-xs text-zinc-500 dark:border-zinc-800 dark:text-zinc-500">
            Built by{" "}
            <a
              href="mailto:tripathiyash1004@gmail.com"
              className="font-medium text-zinc-700 underline underline-offset-2 hover:text-zinc-900 dark:text-zinc-300 dark:hover:text-zinc-100"
            >
              Yash Tripathi
            </a>{" "}
            &middot; tripathiyash1004@gmail.com
          </footer>
          <Toaster />
        </ClerkProvider>
      </body>
    </html>
  );
}
