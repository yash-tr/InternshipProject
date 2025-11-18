# Careers Hub Access Incident – Week 12

## Summary
User `careers_hub_2388` remained blocked after completing the final remediation task. Log inspection revealed a race between the pending-action completion handler and `PolicyEnforcementWorker`. The block state was cleared in the DB but the worker re-applied the block because it read stale pending-action data.

## Timeline
- **09:10** – Support ticket escalated; user unable to access hub.
- **09:22** – Logs showed alternating block/unblock actions with duplicate audit entries.
- **09:35** – Added trace logging to `PolicyEnforcementWorker`; reproduced issue on staging.
- **10:05** – Identified race condition between worker and synchronous completion handler.
- **11:00** – Implemented transactional update with `FOR UPDATE` locking plus `BlockStateRepairWorker`.
- **12:15** – Patched production workers, verified user regain access.

## Remediation
- Wrapped block/unblock transitions in a single transaction.
- Added `BlockStateRepairWorker` to reconcile legacy inconsistent states.
- Extended audit logging to include worker identifiers.
- Documented playbook steps for support responders.

## Validation
- Unit tests for the repair worker and enforcement service.
- Targeted staging scenario tests covering simultaneous completion/block updates.
- Production canary monitoring for 24 hours with no regressions.

