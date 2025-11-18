# Week 12 – Job Portal Scale & Compliance

## Overview
- Rolled job tags to 100% of users and removed legacy feature flags with safe client migration.
- Delivered the Click Optimization Service that boosts job relevance via interaction signals.
- Implemented end-to-end career misconduct enforcement with audit-ready actions.
- Fixed production careers hub access regression caused by race conditions.
- Built the Job Highlight creation service, metadata schema, admin tooling, and migration.

## Structure
- `app/controllers/api/v1` – JSON APIs for job tags, click optimization, misconduct enforcement, and highlights.
- `app/services` – Business logic for rollout orchestration, ranking, policy enforcement, and highlighting.
- `app/models` – Lightweight POROs representing new data structures.
- `app/workers` – Sidekiq workers for highlight creation and block-state repairs.
- `config/routes.rb` – Route declarations for the new endpoints.
- `db/migrate` – PostgreSQL migration enabling highlight metadata and indexes.
- `scripts/manual_highlight_runner.rb` – Admin-safe manual trigger for highlight backfill.
- `docs/incident_report.md` – Write-up of the careers hub access issue and remediation.
- `spec/services` – RSpec coverage for the primary services.
- `src/` – Vite + React control center to exercise Week 12 APIs (job tags, optimization, misconduct admin, highlight orchestration).

## Testing & Validation
- `bundle exec rspec spec/services` for Ruby service specs.
- Manual smoke across staging/UAT for job tags, misconduct enforcement, click optimization, and highlight creation.
- Canary plus production validation steps documented inside each service’s comments.
- Frontend: `npm install && npm run dev` inside `week-12/` to launch the React control center.

## Deployment Notes
- Run the migration before enabling highlight services: `bundle exec rails db:migrate`.
- Ensure `CLICK_OPTIMIZATION_SERVICE_URL` and Mixpanel tokens are configured.
- Sidekiq queues `highlights` and `policy_enforcement` must be scaled to at least 2 workers each.

