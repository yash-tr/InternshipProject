# Mixpanel Event Updates – Week 12

| Event | Trigger | Properties |
| --- | --- | --- |
| `click_optimization.rank` | `ClickOptimizationService#rank!` | `job_count`, `context` |
| `job_highlight.created` | Highlight creation API/Admin action | `job_id` |
| `career_misconduct.block` | Admin block action | `target_id`, `reason`, `policy_version` |
| `career_misconduct.unblock` | Admin unblock action | `target_id`, `policy_version` |

## Notes
- Impression vs click events share `impression_token` allowing funnel attribution.
- Ensure the new events are whitelisted in Mixpanel’s schema to avoid dropped data.

