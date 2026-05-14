Here’s a concise, production-ready Final PRD with workflow and design for your Salesforce-triggered, context-aware autonomous AI calling agent. It preserves autonomous LLM behavior but keeps calls/tokens bounded, cost-controlled, and compliant.

AI Calling Agent — Final PRD, Workflow, and Design (Autonomous, Cost-Optimized)

1) Product Overview
- Goal: An autonomous AI voice agent that triggers on Salesforce lead events, enriches context, scores value/state, plans the call, and executes a real-time outbound call via Twilio to qualify, nurture, and progress deals—logging everything back to Salesforce.
- Autonomy principle: LLM-driven reasoning is retained where it adds unique value (planning, complex turns), within a deterministic state machine and strict cost/latency budgets.

2) Scope (MVP)
- Trigger: Salesforce Lead/Contact create/update.
- Enrichment: CRM first, gated vendor lookups (Apollo if licensed; LinkedIn via approved partner only).
- Value/State: Rules first, small LLM for ambiguity.
- Planning: 1 pre-call LLM plan per lead.
- Call: Twilio outbound, streaming STT/TTS, FSM dialog; selective per-turn LLM only when templates don’t cover.
- Writeback: Tasks + lead/contact updates; dispositions; follow-ups.
- Observability: Node-level metrics, token/call budgets, tracing.

3) Key Non-Goals (MVP)
- No unapproved data sources (no scraping).
- No unlimited agent loops; strict caps on external calls and LLM turns.
- No multi-lingual beyond en-US initially.

4) Success Metrics and SLAs
- p95 pre-dial latency ≤ 8s.
- Median external calls/lead ≤ 1 (non-VIP), ≤ 2 (VIP).
- LLM calls: typical ≤ 2 per lead (planner + 0–1 runtime); VIP ≤ 3.
- Answered call rate, meeting-booked rate, qualification rate (tracked).
- Cache hit rate ≥ 30% by week 2.
- STT first-token latency ≤ 600 ms; TTS first audio ≤ 800 ms.

5) Compliance and Risk
- Telephony: DNC/consent flags, calling windows by region, TrustHub/KYC, STIR/SHAKEN where applicable.
- Data: PII redaction in logs; configurable retention; encrypt recordings optional/opt-in.
- LinkedIn: Only via approved partner APIs if available; otherwise bypass.
- Audit: Store plan, decisions, and dispositions with timestamps.

6) Technical Stack
- Orchestration: LangGraph (or Python FSM) with explicit nodes and guards.
- Backend: FastAPI (Python 3.11+).
- CRM: Salesforce Platform Events/CDC intake; Bulk API for writes.
- Telephony: Twilio Programmable Voice (streaming).
- STT/TTS: ElevenLabs for both (primary), Twilio STT fallback.
- LLM: OpenRouter small model for planner/classifier; larger model disabled by default (can enable for VIP).
- Cache: In-memory + optional Redis (enrichment, classifications, plans, TTS).
- Storage: Salesforce + local SQLite/Cloud DB for logs and metrics.
- Deployment: Containerized; dev/staging/prod envs.

7) High-Level Architecture
- Salesforce Events → Intake Service → Normalize/Cache → Enrichment (gated) → Value/State → LLM Plan → Compliance Gate → Twilio Call (FSM with STT/TTS) → Selective runtime LLM for complex turns → Outcome → Salesforce Writeback → Metrics/Tracing.

8) Detailed Workflow (LangGraph/FSM Nodes)

A. Salesforce Intake
- Input: Platform Event/CDC payload.
- Actions: Debounce rapid updates; dedupe by leadId/externalId; enqueue with priority (value score if present).
- Output: Lead context stub.
- Failure: Retry on transient; idempotent processing.

B. Normalize + Cache Gate
- Normalize phone/domain/company/title; query caches:
  - enrichment:{domain/company} TTL=7d
  - state:{leadId} TTL=24h
- Decision: If enough CRM data present or recent, skip external enrichment.

C. Enrichment (Gated)
- Sources in order: CRM/internal → Apollo (if licensed) → LinkedIn partner (if approved) → Web search (VIP only, missing critical info).
- Caps: Non-VIP max 1 external call; VIP max 2; no retries on 4xx; retry 5xx up to 2 with jitter.
- Cache results; compute a confidence score; if low confidence, proceed CRM-only (don’t keep calling vendors).

D. Value Scoring (Rules → Small LLM on gray zone)
- Rules: revenue band, employee count, role, region, ICP tags → score 0–100 and tier A/B/C.
- Gray zone (e.g., 45–55): call small LLM classifier with max_tokens ≤ 64, JSON output.
- Output: ai_value_score__c, ai_value_tier__c.

E. State Classification (Rules → Small LLM on notes ambiguity)
- Rules: lifecycle stage, last tasks/opportunity status → state ∈ {spread_client, checking_out, returning, new}.
- Ambiguous/missing: small LLM on recent notes max_tokens ≤ 64; cache 24h.
- Output: ai_state__c.

F. LLM Call Plan (Autonomous Planner)
- Single LLM call before dialing to produce:
  - Goals, slot schema, objection categories, tone, 3–5 opener variants, fallback phrases, closing options.
- Input: CRM context, enrichment, value tier, state.
- Output: Strict JSON; stored as plan; cache 24h keyed by leadId+hash(context).
- Token cap: e.g., 400–600 tokens.

G. Compliance Gate
- DNC/consent, regional windows, caller ID, throughput, daily/hourly caps.
- If blocked: create follow-up task; do not dial.

H. Outbound Call (Twilio) + Voice Loop
- Setup: Twilio REST create call; TwiML for gather/stream; enable barge-in via VAD.
- STT: ElevenLabs primary; Twilio STT fallback; chunked 20–30s recordings for async backup.
- TTS: ElevenLabs; cache static prompts; SSML for pace.
- FSM States:
  - Init → Opener → Qualify → Objection → Close → Wrap-up → End.
  - Transitions based on slot filling, user intent, timers.
- Runtime LLM Policy:
  - Use planner’s openers and templates first.
  - Invoke small LLM only when template_coverage=false or complex_objection=true.
  - Per-turn cap: max_tokens ≤ 80; 1–2 runtime LLM calls typical; VIP can allow 2–3.
  - Hard guard: live-call LLM budget; abort extra attempts.
- Max turns: 10; detect voicemail; leave concise template voicemail if allowed.
- Safety rails: abuse/harassment keyword detector → hangup + DNC; “handoff” phrase triggers warm transfer.

I. Outcome and Salesforce Writeback
- Fields:
  - ai_value_score__c, ai_value_tier__c, ai_state__c, ai_playbook__c
  - ai_last_call_sid__c, ai_last_call_disposition__c
  - ai_summary__c (structured), ai_next_step__c, ai_meeting_link_sent__c
- Task: Completed call with disposition, summary, next step.
- Idempotency: keyed by call SID + leadId; Bulk API batching; retry on lock/contention.

J. Metrics, Tracing, and Budgets
- Track per lead/call:
  - external_calls_used vs budget
  - llm_calls_used vs budget (pre-call and runtime)
  - tokens_in/out, TTFT, STT latency, TTS latency
  - cache hits (enrichment, plan, opener)
  - call outcomes: answered, booked, qualified
- Waterfall traces per node; prune slow/costly branches.

9) Dialog and Content Design
- Plan-first autonomy: The planner yields goals, slots, opener variants, and objection maps that the FSM consults.
- Templates prioritized:
  - Common objections: price/timing/authority/competitor.
  - Qualification slots: role, email, company, timeline, pain.
- VIP flavor: Optional single LLM paraphrase for opener to match tone/persona.
- Output constraints: responses ≤ 25–30s spoken; one question per turn.

10) Cost Controls (Hard Budgets)
- External calls: Non-VIP ≤ 1, VIP ≤ 2; no web search unless VIP and missing critical data.
- LLM calls:
  - Planner: 1 per lead (cached 24h).
  - Runtime: Non-VIP ≤ 1; VIP ≤ 2–3.
- Token caps:
  - Classifier/state: ≤ 64
  - Planner: ≤ 600
  - Runtime turns: ≤ 80
- KV/prompt caching: Stable system prefix; reuse plan schema; cache opener variants.

11) Priority Queue and Rate Control
- Priority queue by value tier and staleness; process A-tier first.
- Regional throttles; Twilio 429/5xx backoff with jitter; concurrency caps per number/region.

12) Data Model (Salesforce)
- Lead/Contact fields:
  - ai_value_score__c (0–100), ai_value_tier__c (A/B/C)
  - ai_state__c (enum), ai_playbook__c (text)
  - ai_last_call_sid__c (text), ai_last_call_disposition__c (enum)
  - ai_summary__c (long text, structured), ai_next_step__c (text)
- Task:
  - Subject, Type=Call, Disposition__c, Description (summary), Next_Step__c, Status=Completed, ActivityDate.

13) Security & Privacy
- Secrets via env/secret store; no secrets in logs.
- PII minimization and redaction; configurable retention for transcripts/recordings.
- Optional encryption at rest; signed URL access to recordings.

14) Environments & Feature Flags
- Envs: dev/staging/prod; separate Twilio numbers and SF sandboxes.
- Flags:
  - enable_vip_path
  - enable_partner_linkedin
  - enable_web_search
  - enable_runtime_llm_extra_turns (for experiments)

15) Failure Modes & Handling
- External vendors: Retry 5xx max 2; skip on 4xx; proceed CRM-only on low confidence.
- STT dropouts: ask once to repeat; after 2 fails → offer SMS/email follow-up.
- Voicemail detected: leave short voicemail (template) if allowed.
- LLM errors: fallback scripted phrase; log incident; do not replan within same call.

16) Testing & QA
- Unit: rules engines, cache keys/TTLs, compliance gates, plan schema validation.
- Integration: mocked Salesforce/Twilio/Apollo; golden traces.
- Voice harness: synthetic audio set for silence, accents, crosstalk; assert FSM transitions, barge-in handling.
- Load: enqueue 1 call/sec; verify back-pressure and SLA adherence.

17) Example Call Paths
- Non-VIP, clear CRM: skip enrichment; rules classify; 1 planner call; call with templates; 0 runtime LLM; writeback.
- Mid-value, ambiguous state: 1 Apollo hit; state classifier LLM (64 tok); planner; call with 0–1 runtime LLM on objection.
- VIP, missing firmographics: Apollo + web search; planner; opener paraphrase; up to 2 runtime LLMs on complex objections.

18) Implementation Notes (Interfaces and Budgets)
- Cache keys:
  - enrichment:{domain}|{company} TTL=7d
  - classifier:{leadId} TTL=24h
  - plan:{leadId}:{ctx_hash} TTL=24h
  - tts:prompt_hash TTL=30d
- Retry policy (external):
  - backoff 200ms, 500ms; max 2; retry on 502/503/504.
- Guards:
  - max_external_calls, max_llm_calls (separate counters for pre-call/runtime).
  - live-call guard to block unexpected LLM usage.

19) Model Choices (initial)
- Small LLM: mistral-nemo class via OpenRouter for classifier/plan/runtime snippets.
- Optional: upgrade planner to a stronger model for VIP only (flagged), with strict token caps.

20) Rollout Plan
- Phase 1: Deterministic runtime (planner + templates), runtime LLM disabled; measure baselines.
- Phase 2: Enable runtime LLM for complex objections on A-tier only; monitor cost/quality deltas.
- Phase 3: Enable VIP enrichment and web search; tune budgets and caches; expand playbooks.

If you want, I can map this PRD to an explicit LangGraph graph (node list, edges, per-node inputs/outputs, and retry/caching policies) and provide code stubs for the planner JSON schema, FSM transitions, and the live-call LLM guard.
