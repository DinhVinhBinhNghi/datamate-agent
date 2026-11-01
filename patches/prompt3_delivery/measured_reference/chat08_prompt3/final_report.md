# Chat 08 Prompt 3 — repair

ĐÃ XÁC MINH: 15 Prompt 2 errors were intent-routing errors: 3 three-month revenue lists, 11 size-specific cup totals, 1 customer ranking. The repaired evaluator traversed 3,000 train questions. Among the currently classified analogue targets, all 122 were correct, 0 wrong and 0 abstain. This does not mean all 3,000 questions are supported.

| Sub-capability | Exact train | Gate |
|---|---:|---|
| AOV | 27/27 | pass |
| Percent revenue growth | 27/27 | pass; excludes three-month lists |
| Max revenue day | 13/13 | pass |
| Exact product quantity | 15/15 | pass |
| Size M/L cup total | 12/12 | pass; temporal holdout only, no independent business holdout |
| Product ranking | 12/12 | pass; customer ranking excluded |
| Customer spend ranking | 16/16 | pass; order-frequency intent excluded |

Candidate B is the parent (18/1,000, SHA `0eb7eb9f730bf8f0cbafb8dc3db5fe73b4f75bef99086dfcd5e21591ccf8c66a`). Candidate G adds 6 (24 total); H adds 7 (25 total); I composes all passed buckets with Prompt 2 capabilities and adds 19 (37 total). All are structurally valid with zero unexpected parent diffs in the measured local run. Public correctness and leaderboard score remain unknown. None was submitted.

The forensic CSVs document each original failure. Empty fields such as raw sample/tie set mean the evidence was not measured; they are not claims of absence. Business holdout is unavailable for size-specific totals. Another public archetype was not enabled.

Recommendation: review Candidate I evidence and Windows rerun before deciding whether to spend a submission slot. Candidate B remains the best-known leaderboard result and rollback.
