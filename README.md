# Internship & Portfolio Repository

**Author:** Yash Tripathi  
**Team:** Product Engineering  

This monorepo is a portfolio of **three parallel threads**:

1. **Internship deliverables** — time-boxed snapshots (`week-8` … `week-12`) of a large **Ruby on Rails + React** resume and job platform, showing how features, reliability, and compliance evolved week over week.  
2. **Resume-Builder** — a **standalone, production-style** resume product built with **Next.js** and TypeScript: authentication, PostgreSQL, AI-assisted writing, and PDF export—deployed independently of the internship Rails trees.  
3. **CRM AI Calling Agent** — a **standalone FastAPI** backend for an **AI voice assistant** wired to **Salesforce**, **Twilio**, **ElevenLabs**, and **OpenRouter**, with agents, webhooks, outbound calling, analytics, and a security-minded service layout.

Each top-level folder installs and runs on its own; this document gives a **single high-level map** and **technical specs** so reviewers can orient quickly before opening nested READMEs.

---

## Repository map

| Path | What it is |
|------|------------|
| [`week-8/`](week-8/) | Earlier Rails foundations—resume/domain models, templates, PDF and background-job oriented backend work |
| [`week-9/`](week-9/) | Product reliability and UX—automation fixes, resume parsing flow, Redux/modals, event surfaces ([detail](week-9/README.md)) |
| [`week-10/`](week-10/) | Integrated Rails API + React app—Sidekiq, analytics hooks, “production-shaped” full stack ([detail](week-10/README.md)) |
| [`week-11/`](week-11/) | Compliance and recruiter tooling—policy misconduct, flagging, portal restrictions, Mixpanel ([detail](week-11/README.md)) |
| [`week-12/`](week-12/) | Scale-oriented job portal work—tags rollout, click optimization, misconduct enforcement, highlights, Sidekiq workers, React control center ([detail](week-12/README.md)) |
| [`Resume-Builder/`](Resume-Builder/) | Standalone **Next.js** resume SaaS—Clerk, Neon, Drizzle, Gemini, PDF templates ([detail](Resume-Builder/README.md)) |
| [`CRM AGENT/`](CRM%20AGENT/) | Standalone **FastAPI** AI calling platform—Twilio voice, Salesforce CRM, speech + LLM, LangGraph-style agents ([detail](CRM%20AGENT/README.md)) |

---

## All technology stacks (complete inventory)

This section lists **every major language, framework, library, service, and tool** referenced across the monorepo. Per-project deep dives follow in sections 1–3.

### Internship track (`week-8` … `week-12`)

| Category | Technologies |
|----------|----------------|
| **Languages** | **Ruby 3.2.0** · **JavaScript / JSX** (React apps) |
| **Backend framework** | **Ruby on Rails ~7.0** (`week-8` [Gemfile](week-8/Gemfile)) |
| **App server** | **Puma ~5** |
| **Database** | **PostgreSQL** via **`pg` ~1.1** |
| **Cache & jobs** | **Redis ~5** · **Sidekiq ~7** · **sidekiq-cron** · **sidekiq-scheduler ~4** · **redis-rails** · **connection_pool** |
| **Boot / DX** | **Bootsnap** |
| **API & HTTP** | **Jbuilder** · **rack-cors ~2** |
| **Auth & permissions** | **Devise ~4.9** · **Pundit ~2.3** |
| **Observability** | **sentry-ruby / sentry-rails ~5** · **Lograge ~1** |
| **Documents & media** | **Prawn ~2.4** (PDF) · **MiniMagick ~4.12** |
| **Utilities** | **dotenv-rails** · **Faker ~3** · **Kaminari ~1.2** |
| **Backend testing** | **RSpec Rails ~6** · **factory_bot_rails ~6.2** · **Shoulda Matchers ~5.3** · **WebMock** · **VCR ~6** |
| **Backend dev tools** | **Byebug** · **Spring** · **Listen ~3** · **Annotate ~3** |

**Front-end — [`week-9/package.json`](week-9/package.json) (Create React App):**

| Category | Technologies |
|----------|----------------|
| **Runtime** | **React 18.2** · **React DOM 18.2** |
| **Bundler / toolchain** | **react-scripts 5.0.1** (CRA) |
| **State & routing** | **Redux Toolkit ~1.9.7** · **react-redux ~8.1.3** · **React Router DOM ~6.15** |
| **Styling** | **styled-components ~6.0.7** |
| **Quality** | **web-vitals ~3.4** · ESLint preset via **react-app** |

**Front-end — [`week-12/package.json`](week-12/package.json) (control center):**

| Category | Technologies |
|----------|----------------|
| **Runtime** | **React 18.3** · **React DOM 18.3** |
| **Build & dev** | **Vite ~5.1.6** · **@vitejs/plugin-react ~4.2** |
| **Testing** | **Vitest ~1.5** |
| **Linting** | **ESLint ~8.57** · **eslint-plugin-react ~7.34** |

**Infrastructure & delivery (internship artifacts):**

| Category | Technologies |
|----------|----------------|
| **Containers** | **Docker** · **Docker Compose 3.8** — **PostgreSQL 15-alpine** · **Redis 7-alpine** · **nginx alpine** ([`week-10/config/docker`](week-10/config/docker)) |
| **CI/CD** | **GitHub Actions** — **Ubuntu** runners, **Postgres 15** + **Redis 7-alpine** service containers ([`week-10/.github/workflows/ci.yml`](week-10/.github/workflows/ci.yml)) |
| **Product analytics / data (per week READMEs)** | **Mixpanel** · **Metabase** |
| **Error tracking** | **Sentry** (Rails + React ecosystem as wired in coursework) |

**Note:** Week folders are **snapshots**; Rails source for Docker in `week-10` is built from **`week-8`** context (see `docker-compose.yml`). Front-end stacks differ by week (**CRA** vs **Vite**).

### Resume-Builder ([`Resume-Builder/package.json`](Resume-Builder/package.json))

**Runtime & framework**

- **Next.js 16.1.6** · **React 19.2.3** · **React DOM 19.2.3**
- **TypeScript ~5**

**Auth, data, API**

- **@clerk/nextjs ^7** · **@neondatabase/serverless ^1** · **Drizzle ORM ^0.45** · **drizzle-kit ^0.31**

**Forms, validation, IDs**

- **react-hook-form ^7** · **@hookform/resolvers ^5** · **Zod ^4** · **@paralleldrive/cuid2 ^3**

**PDF & AI**

- **@react-pdf/renderer ^4.3** · **@google/genai ^1.45**

**UI / styling**

- **Tailwind CSS ^4** · **@tailwindcss/postcss ^4** · **tw-animate-css ^1**
- **Radix UI** (`radix-ui ^1`) · **shadcn** (`shadcn ^4`) · **class-variance-authority ^0.7** · **clsx ^2** · **tailwind-merge ^3**
- **lucide-react ^0.577** · **next-themes ^0.4** · **Sonner ^2** (toasts)

**Client state & dates**

- **Zustand ^5** · **date-fns ^4**

**Developer tooling**

- **ESLint ^9** · **eslint-config-next 16.1.6** · **@types/node ^20** · **@types/react ^19** · **@types/react-dom ^19**

### CRM AI Calling Agent ([`CRM AGENT/requirements.txt`](CRM%20AGENT/requirements.txt), [`pyproject.toml`](CRM%20AGENT/pyproject.toml))

**Core**

- **Python ≥ 3.11** · **FastAPI 0.104.1** · **Uvicorn [standard] 0.24.0**
- **Pydantic ≥ 2.5** · **pydantic-settings ≥ 2.4** · **python-multipart 0.0.6** · **python-dotenv 1.0.0**

**HTTP & async**

- **httpx 0.25.2** · **aiohttp 3.9.1**

**Data**

- **SQLAlchemy 2.0.23** · **Alembic 1.13.0** · **psycopg2-binary 2.9.9** · **aiosqlite 0.19.0** (testing)

**Cache & messaging-related**

- **redis 5.0.1**

**Integrations**

- **twilio 8.10.3** · **elevenlabs 2.9.1** · **openai ≥ 1.86.0** (OpenRouter-compatible)

**Agents & LLM ecosystem**

- **langgraph 0.6.4** · **langchain 0.3.27** · **langchain-core 0.3.74** · **langchain-community 0.3.27** · **langchain-openai 0.3.28** · **langfuse 3.2.2**

**Web scraping & parsing**

- **beautifulsoup4 4.12.2** · **scrapy 2.11.0** · **selenium 4.15.2** · **lxml 4.9.3**

**Logic & time**

- **python-statemachine 2.3.6** · **pytz 2023.3**

**Security**

- **python-jose[cryptography] 3.3.0** · **passlib[bcrypt] 1.7.4** · **cryptography**

**Observability**

- **structlog 23.2.0** · **prometheus-client 0.19.0** · **sentry-sdk[fastapi] 1.38.0**

**Testing**

- **pytest 7.4.3** · **pytest-asyncio 0.21.1** · **pytest-mock 3.12.0**

**Optional dev tooling (`pyproject.toml`)**

- **black** · **isort** · **flake8** · **mypy**

### Repository-wide tooling

- **Git** · **GitHub** (remote hosting, Actions CI where configured)
- **Git LFS** — `*.mp4` tracked as LFS ([`.gitattributes`](.gitattributes))

---

## 1. Internship track: Resume Builder / job platform (week snapshots)

### What this thread demonstrates

The **week-*** folders document a single product direction—a resume and job marketplace backed by **Rails**—as scope grew from core authoring features toward **operations**, **trust & safety**, and **portal-scale** behavior. Front ends are **React** (with **Redux Toolkit** where noted in week READMEs); data and jobs rely on **PostgreSQL**, **Redis**, and **Sidekiq**.

### Capability themes (read across weeks)

| Theme | Examples |
|-------|-----------|
| **Core product** | Auth, resume CRUD, templates, PDF generation, dashboards, promotional/event flows |
| **Performance & reliability** | Code splitting and lazy loading, async PDF and cleanup jobs, caching, structured logging and error tracking |
| **Governance** | Policy misconduct surfaces, recruiter flagging, access blockers for violators |
| **Scale & discovery** | Job tags at scale, click optimization, highlight metadata, migrations and workers coordinated with APIs |

### Rails-oriented quick start

Use the week folder your coursework specifies (often **`week-10/`** for the canonical integrated snapshot):

```bash
cd week-10
bundle install
rails db:create db:migrate db:seed
redis-server
bundle exec sidekiq
rails server
```

**Example seeded users (week-10-style):**

- Free: `free@example.com` / `password123`  
- Premium: `premium@example.com` / `password123`  

**Week-12 React control center:** from [`week-12/`](week-12/), run `npm install && npm run dev` to exercise newer APIs as documented in [`week-12/README.md`](week-12/README.md).

---

## 2. Resume-Builder (standalone Next.js application)

**Folder:** [`Resume-Builder/`](Resume-Builder/)  
**Live demo:** https://resumebuilder-lime-seven.vercel.app  

### One-line description

A **full-stack resume builder**: users sign in with **Clerk**, persist resumes in **PostgreSQL** (**Neon**) via **Drizzle ORM** and Route Handlers, edit structured sections in the browser, pick **PDF templates**, optionally use **Google Gemini** for AI-assisted copy, and download polished PDFs.

### Feature overview

- **Lifecycle:** Dashboard listing → create/open resume → section editors (personal info, summary, roles, education, skills) → explicit save with dirty-state and unsaved navigation guard  
- **Templates:** **Classic** and **Modern** (free), **Premium** (simulated “upgrade to Pro”; no real billing in-repo)  
- **PDF:** Live preview panel (desktop split / mobile tabs), batched preview refresh, download via `@react-pdf/renderer`  
- **AI (Gemini):** Summary generation, bullet rewrites, skill suggestions with selective apply  
- **UX:** Loading skeletons, toasts (Sonner), responsive layout, Zod-backed validation patterns  

### Technical specification

**Full dependency list:** see **[All technology stacks (complete inventory)](#all-technology-stacks-complete-inventory)** → Resume-Builder.

| Layer | Technology | Notes (from `package.json`) |
|-------|------------|------------------------------|
| Framework | **Next.js 16.1.6** | App Router; `next dev` / `next build` |
| UI runtime | **React 19.2.3** | Client components for editor and PDF views |
| Language | **TypeScript ~5** | Strict typing across app and `types/` |
| Auth | **@clerk/nextjs ^7** | Sign-in/up routes, session on server and client |
| Database | **Neon** (`@neondatabase/serverless`) | Serverless Postgres |
| ORM / migrations | **Drizzle ORM ^0.45**, **drizzle-kit** | Schema in `lib/db/` |
| Client state | **Zustand ^5** | Resume/editor UI state |
| Forms / validation | **react-hook-form**, **@hookform/resolvers**, **Zod ^4** | Typed forms and API payloads |
| PDF | **@react-pdf/renderer ^4.3** | Classic / Modern / Premium document components |
| AI | **@google/genai ^1.45** | Server-side generation routes |
| UI kit | **shadcn/ui**, **Radix UI**, **Tailwind CSS ^4**, **lucide-react** | Accessible primitives and styling |
| IDs | **@paralleldrive/cuid2** | Stable resume identifiers |

### Local setup (summary)

Requires **Node.js 20+**, Neon database URL, Clerk keys, and optionally a Gemini API key. Full env names and commands: [`Resume-Builder/README.md`](Resume-Builder/README.md).

```bash
cd Resume-Builder
npm install
npm run dev
```

---

## 3. CRM AI Calling Agent (standalone FastAPI backend)

**Folder:** [`CRM AGENT/`](CRM%20AGENT/)  

### One-line description

An **AI calling-agent MVP**: **FastAPI** exposes versioned **REST APIs** for **Twilio** voice webhooks, **Salesforce** events, **speech** utilities, **LLM** calls, **multi-step agents** (LangGraph / LangChain ecosystem), **outbound campaigns**, **call quality**, **objection handling**, **approvals**, **audit**, **analytics**, and **monitoring**—with **SQLAlchemy + Alembic** persistence, optional **Redis**, and production-minded logging and metrics.

### What the system is responsible for

| Concern | Implementation angle |
|---------|------------------------|
| **Telephony** | Twilio webhooks and voice-oriented flows (`twilio` SDK) |
| **CRM** | Salesforce REST integration—lead/contact oriented webhooks and services |
| **Speech** | ElevenLabs integration for voice-oriented pipelines |
| **Reasoning** | OpenRouter-compatible OpenAI client; LangGraph / LangChain for orchestration; optional **Langfuse** tracing |
| **Data** | PostgreSQL (or SQLite for dev) via SQLAlchemy 2.x; Alembic migrations |
| **Caching / perf** | Redis client; in-app cache manager and performance monitor (see `app/core` and lifespan in `app/main.py`) |
| **Observability** | **Structlog** structured logs, **Prometheus** metrics endpoint, **Sentry** FastAPI integration when `SENTRY_DSN` is set |
| **Security posture** | Dedicated security middleware stack, JWT/crypto-related deps (`python-jose`, `passlib`, `cryptography`), webhook-oriented hardening described in [`CRM AGENT/README.md`](CRM%20AGENT/README.md) |

### API surface (`/api/v1/...`)

Routers mounted under the v1 API (see [`CRM AGENT/app/api/v1/api.py`](CRM%20AGENT/app/api/v1/api.py)):

| Prefix | Purpose |
|--------|---------|
| `/webhooks` | Twilio + Salesforce inbound events (e.g. incoming call, lead created) |
| `/speech` | Speech-related endpoints backing voice UX |
| `/llm` | LLM invocation and supporting utilities |
| `/agents` | Agent orchestration endpoints |
| `/research` | Prospect / research-oriented APIs |
| `/approval` | Human-in-the-loop or workflow approvals |
| `/audit` | Audit trail oriented reads/writes |
| `/outbound-calls` | Outbound dialing campaign behavior |
| `/call-quality` | Quality monitoring hooks |
| `/objections` | Objection-handling flows |
| `/analytics` | Usage and funnel-style analytics |
| `/monitoring` | Operational monitoring endpoints |

Global routes also include **health** and **metrics** (Prometheus format), plus CORS, trusted host, and security middleware wiring in [`CRM AGENT/app/main.py`](CRM%20AGENT/app/main.py).

### Technical specification (key dependencies)

**Full pinned dependency list:** see **[All technology stacks (complete inventory)](#all-technology-stacks-complete-inventory)** → CRM AI Calling Agent.

Pinned or constrained versions below come from [`CRM AGENT/requirements.txt`](CRM%20AGENT/requirements.txt) and [`CRM AGENT/pyproject.toml`](CRM%20AGENT/pyproject.toml).

| Layer | Technology |
|-------|------------|
| Runtime | **Python ≥ 3.11** |
| Web | **FastAPI 0.104.x**, **Uvicorn [standard] 0.24.x**, **Pydantic ≥ 2.5**, **python-multipart** |
| Config | **python-dotenv**, **pydantic-settings** (requirements) |
| HTTP clients | **httpx**, **aiohttp** |
| Database | **SQLAlchemy 2.0.23**, **Alembic 1.13**, **psycopg2-binary** |
| Cache | **redis 5.x** |
| Telephony / speech | **twilio 8.10.x**, **elevenlabs 2.9.x** |
| LLM | **openai ≥ 1.86** (OpenRouter-compatible), **langgraph 0.6.x**, **langchain** stack, **langfuse** |
| Scraping / parsing (supporting services) | **beautifulsoup4**, **scrapy**, **selenium**, **lxml** |
| Dialog / state | **python-statemachine** |
| Security | **python-jose[cryptography]**, **passlib[bcrypt]**, **cryptography** |
| Observability | **structlog**, **prometheus-client**, **sentry-sdk[fastapi]** |
| Testing | **pytest**, **pytest-asyncio**, **pytest-mock**, **aiosqlite** |
| Tooling (optional dev) | **black**, **isort**, **flake8**, **mypy** per `pyproject.toml` |

Architecture narrative (Salesforce OAuth, deployment targets, formatting commands): [`CRM AGENT/README.md`](CRM%20AGENT/README.md).

### Local setup (summary)

```bash
cd "CRM AGENT"
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env         # configure Salesforce, Twilio, ElevenLabs, OpenRouter, DATABASE_URL
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Run tests: `pytest` from the same folder.

---

## Cross-project comparison

| Dimension | Internship (`week-*`) | Resume-Builder | CRM AGENT |
|-----------|----------------------|----------------|-----------|
| **Primary languages** | Ruby, JavaScript | TypeScript | Python |
| **Web frameworks** | Rails 7 · React (CRA / Vite by week) | Next.js 16 · React 19 | FastAPI |
| **Persistence** | PostgreSQL · Redis | Neon Postgres · Drizzle | PostgreSQL/SQLite · SQLAlchemy · Alembic |
| **Auth** | Devise · Pundit | Clerk | Service/API patterns (see CRM docs) |
| **External SaaS** | Mixpanel, Metabase, Sentry (as integrated) | Clerk, Neon, Gemini | Salesforce, Twilio, ElevenLabs, OpenRouter |
| **Heavy lifting** | Jobs (Sidekiq), PDF (Prawn), APIs | PDF (react-pdf), AI copy | Voice, agents, CRM webhooks |
| **Tests** | RSpec · Vitest (week-12) · CRA tests | ESLint · Next lint | pytest |

For the **full** dependency lists, use **[All technology stacks (complete inventory)](#all-technology-stacks-complete-inventory)** above.

---

## Navigation tips for reviewers

- **Coursework / grading:** Start with the **`week-*`** README that matches the submission week; code for that slice lives only under that directory.  
- **Full-stack resume product:** Deep dive [`Resume-Builder/README.md`](Resume-Builder/README.md) and the live URL above.  
- **Voice + CRM + AI backend:** Deep dive [`CRM AGENT/README.md`](CRM%20AGENT/README.md) and `app/api/v1/` for endpoint breadth.  

