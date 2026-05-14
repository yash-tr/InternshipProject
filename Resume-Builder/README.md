# Resume Builder

A full-stack web application for creating, editing, and downloading professional resumes as PDFs — with multiple templates and optional AI-powered content assistance.
Link: https://resumebuilder-lime-seven.vercel.app
**Built by Yash Tripathi** — tripathiyash1004@gmail.com

---

## Tech Stack

| Layer          | Technology                                                  |
| -------------- | ----------------------------------------------------------- |
| Framework      | [Next.js 16](https://nextjs.org) (App Router, Turbopack)   |
| Language       | TypeScript                                                  |
| Authentication | [Clerk](https://clerk.com)                                  |
| Database       | [Neon](https://neon.tech) (Serverless PostgreSQL)           |
| ORM            | [Drizzle ORM](https://orm.drizzle.team)                     |
| State Mgmt     | [Zustand](https://zustand-demo.pmnd.rs)                    |
| PDF Generation | [@react-pdf/renderer](https://react-pdf.org)               |
| AI             | [Google Gemini](https://ai.google.dev) (`@google/genai`)   |
| UI Components  | [shadcn/ui](https://ui.shadcn.com), Radix UI, Tailwind CSS |
| Validation     | [Zod](https://zod.dev)                                      |
| Notifications  | [Sonner](https://sonner.emilkowal.ski)                      |

---

## Features Implemented

### 1. Resume Creation & Editing
- Create new resumes from the dashboard
- Inline-editable resume title
- Form sections: Personal Info, Summary, Work Experience, Education, Skills
- Add/remove work experience entries and education entries dynamically
- Add/remove bullet points per work experience entry
- Tag-based skill input
- Explicit **Save** button with dirty-state tracking ("Saved" / "Unsaved changes" / "Saving…")
- Data persisted to PostgreSQL via REST API

### 2. Resume Templates
- **Classic** (Free) — Traditional single-column, ATS-friendly layout
- **Modern** (Free) — Two-column layout with visual styling
- **Premium** (Pro/Paid) — Bold colored header with timeline layout
- Template picker page with live HTML/CSS previews
- Paid template is locked behind a simulated "Upgrade to Pro" flow (no real payment)
- Templates can be switched from the editor header

### 3. Resume Download
- Live PDF preview panel in the editor (right side on desktop, tab on mobile)
- Batched preview updates via "Update preview" button to reduce rendering load
- One-click PDF download using `@react-pdf/renderer`'s `PDFDownloadLink`
- Edit and re-download at any time

### 4. AI Assistance (Google Gemini)
- **Generate Summary** — produces a 3-sentence professional summary based on work experience
- **Improve Bullet Points** — rewrites individual bullets with strong action verbs and quantified results
- **Suggest Skills** — recommends 8 relevant skills based on role, with multi-select checkboxes to pick which ones to add
- Inline AI buttons placed contextually next to each relevant section
- Graceful error handling with toast notifications when AI is unavailable

### 5. Polish & UX
- Clerk-based authentication (sign-in, sign-up, user avatar)
- Loading skeletons for dashboard and editor routes
- Toast notifications for errors (save failure, resume not found, AI errors)
- Empty states for dashboard, work experience, and skills
- Unsaved changes guard (`beforeunload` browser warning)
- Back-to-dashboard navigation from editor
- Responsive layout: side-by-side on desktop, tabbed on mobile

---

## Setup Instructions

### Prerequisites

- **Node.js 20+** (a `.nvmrc` is included — run `nvm use` if you use nvm)
- A [Neon](https://neon.tech) PostgreSQL database
- A [Clerk](https://dashboard.clerk.com) application (for auth keys)
- *(Optional)* A [Google AI Studio](https://aistudio.google.com/apikey) API key for Gemini

### 1. Install dependencies

```bash
cd Resume-Builder
npm install
```

### 2. Configure environment variables

Copy the example file and fill in your credentials:

```bash
cp .env.example .env.local
```

Required variables in `.env.local`:

```
DATABASE_URL=postgresql://user:password@host/database?sslmode=require
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
GEMINI_API_KEY=            # optional — AI features disabled without this
```

### 3. Run database migrations

```bash
npx drizzle-kit push
```

This creates the `profiles` and `resumes` tables in your Neon database.

### 4. Start the dev server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## Project Structure

```
Resume-Builder/
├── lib/                        # Server-side utilities
│   ├── db/                     # Drizzle client & schema
│   ├── templates.ts            # Template definitions & tiers
│   └── validators.ts           # Zod schemas for API validation
├── types/
│   └── resume.ts               # Shared TypeScript interfaces (ResumeData)
├── src/
│   ├── app/
│   │   ├── api/
│   │   │   ├── ai/generate/    # POST — AI content generation
│   │   │   ├── resume/         # GET/POST — list & create resumes
│   │   │   ├── resume/[id]/    # GET/PUT/DELETE — single resume CRUD
│   │   │   └── user/upgrade/   # POST — simulate pro upgrade
│   │   ├── dashboard/          # Resume list (server component)
│   │   ├── editor/[id]/        # Resume editor (server + client)
│   │   ├── templates/          # Template picker page
│   │   ├── sign-in/            # Clerk sign-in
│   │   └── sign-up/            # Clerk sign-up
│   ├── components/
│   │   ├── dashboard/          # ResumeCard, NewResumeButton, Toasts
│   │   ├── editor/             # EditorLayout, form sections, AI button
│   │   ├── pdf/                # PDF templates & preview/download
│   │   ├── templates/          # TemplatePicker client component
│   │   └── ui/                 # shadcn/ui primitives
│   └── lib/                    # Client-side utilities
│       ├── ai.ts               # AI API helpers
│       ├── api.ts              # Resume CRUD fetch helpers
│       ├── resume-store.ts     # Zustand store
│       └── profile.ts          # User profile helpers
└── drizzle.config.ts           # Drizzle Kit configuration
```

---

## Assumptions

1. **No real payment integration** — the "Premium" template is locked behind a simulated upgrade button that sets the user's plan to `"pro"` in the database. No payment gateway is involved.
2. **Clerk handles all auth** — email/password and OAuth flows are fully managed by Clerk; no custom auth logic is needed.
3. **Single-user resumes** — each resume belongs to exactly one user; there is no sharing or collaboration.
4. **AI is optional** — if `GEMINI_API_KEY` is not set, AI buttons will show an error toast but the rest of the app works normally.
5. **PDF rendering is client-side** — `@react-pdf/renderer` runs entirely in the browser. The server never generates PDFs.

---

