# Chat 08 Prompt 2 — capability expansion report

Generated from the attached D:\ZALO snapshot and the extracted train/public data. This run is read-only with respect to raw data and does not submit anything.

## Verified freeze

- Baseline SHA-256: `c8c57a2cca00047099c293c5ba642d864d9b706132891bb43858cfc605cf7ea6` — matched before and after.
- Candidate B SHA-256: `0eb7eb9f730bf8f0cbafb8dc3db5fe73b4f75bef99086dfcd5e21591ccf8c66a` — matched before and after.
- Candidate B remains the parent of every generated candidate; existing non-abstain rows are never overwritten.

## Measured train gates

| Family | Train target | Development | Holdout | Correct | Wrong | False positive | Public gate |
|---|---:|---:|---:|---:|---:|---:|---|
| average order value | 27 | 17 | 10 | 27 | 0 | 0 | PASS |
| max revenue day | 13 | 9 | 4 | 13 | 0 | 0 | PASS |
| customer spend ranking | 14 | 11 | 3 | 14 | 0 | 0 | PASS |
| revenue growth | 30 | 18 | 12 | 27 | 3 | 0 | BLOCKED |
| product quantity | 26 | 8 | 18 | 15 | 11 | 0 | BLOCKED |
| product ranking | 13 | 9 | 4 | 12 | 1 | 0 | BLOCKED |

The evaluator traversed all 3,000 train questions. `false positive` means an answer emitted outside the classifier-generated target set; inventory-label disagreements are reported separately because the Chat 08 inventory is audit evidence, not answer gold.

## Controlled public artifacts

| Candidate | Families | Changed from B | Answered | Status |
|---|---|---:|---:|---|
| C derived sales | AOV + max revenue day | 5 | 23/1000 | structurally valid |
| D customer | customer spend ranking | 1 | 19/1000 | structurally valid |
| E product | quantity + ranking | 0 | — | not created; train gate failed |
| F composed | C + D | 6 | 24/1000 | structurally valid |

Public accuracy is unknown. No row is claimed correct from leaderboard inference, and no candidate is submitted automatically.

## Capability design

The capability layer exposes minimum `sales`, `products`, and `customers` views per enabled business. It retains provenance and uses explicit semantic roles from each business config. It does not rewrite raw files or union all businesses into a common physical table.

The verified implementation scope is the `monthly_excel_sales_lines` archetype for train `biz_102`, `biz_103`, `biz_104` and public `dev_002`. No new public archetype was enabled because no additional business had both adapter evidence and exact train holdout proof in this prompt.

## Remaining blockers

- Revenue growth has three train errors and remains disabled.
- Product quantity has eleven train errors; product parsing/group semantics require narrower intents and unit/category evidence.
- Product ranking has one train error and remains disabled under the zero-wrong rule.
- Customer loyalty/frequency, product groups, revenue share, debt, inventory, and new public archetypes remain unsupported.
- Candidate leaderboard accuracy remains unavailable until the user chooses to submit externally.
