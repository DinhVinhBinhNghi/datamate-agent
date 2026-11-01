# DataMate Chat09 — checkpoint (2026-10-31)

## Scope and environment

Only train/public ZIP data and handoffs 01–08 were mounted. `D:\ZALO` source/config/tests, frozen baseline/B/G submission files and Chat08 measured artifacts were unavailable here. Raw ZIPs read only. No Windows code was changed, no submission was made. The scripts in `patch/` are a portable, separate patch, not an installed repo change.

## A — foundation

| Gate | Status | Evidence / resume |
|---|---|---|
| Baseline/B/G hashes | Pending Windows | Handoff expected hashes embedded in `patch/resume_chat09.ps1`; script fails before any source snapshot or build if mismatch. No local frozen bytes to hash. |
| Code/config snapshot | Pending Windows | `resume_chat09.ps1` snapshots src/configs/tests with hashes before new work. |
| Train/public rule differences | Scanned | `rulebook_diff.csv` has 31 textual table differences. Review material calculation differences below. |
| Explicit ruleset | Local scripts pass explicitly | `chat09_raw.py` and `sqlite_sales_view.py` reject missing/unknown rulesets. Existing repo functions could not be inspected. |

Material rulebook differences: public §1 adds exclusion of an order returned after its order period, including after as_of_date; public §1 cash shift report follows receipt time and includes debt collection, not order revenue; public §2 weekday daily average includes zero days; public §3 adds loyalty, customer AOV minimum 3 orders, cancel ranking, popularity by distinct orders, busiest day/hour, worker days; public §5 adds main supplier by count; public §6 café toppings embedded in a row are separate products, and has additional mother/baby, motor repair and phone shop rules; public §8 has status in note if no status column. Common §7 partial period must be computed; common §8 same-order exact duplicate rows counted once; common §9 tie-break by code then name. `rulebook_diff.csv` also contains lexical differences; it is a review inventory, not an automatic semantic equivalence proof.

## B — isolated candidates

| Candidate | Status | Gate/blocker |
|---|---|---|
| J | Builder prepared; candidate **not created** | Raw recomputation matches handoff: Jan/Jun/Nov 2025 AOV 70,324/69,630/72,304; max days Nov 2 and Jul 27. `build_j.py` dynamically finds 3+2 questions, requires exact G SHA, 24 answered parent, 1000 ordered IDs, preserves every answered G row, writes new file exclusively and manifest/diff. Needs Windows parent, official validator and freeze hash. |
| K | Experiment / not enabled | Canonical key and 59 raw alias groups audited (`raw_audit.json`); basic normalization test pass. Collision semantics, unit lookup, toppings, train exact and public invariant not yet fully verified. No candidate. |
| L | Parser experiment / not enabled | Anchored `3 khách` regression and `Th9` adversarial absence test pass locally. Existing planner integration, full train exact and public ranking invariant unavailable. No candidate. |
| M | Report only | `m_experiment.md`: 70 gold unanswerables; no rule fired or evaluated. False-positive rate not measured, coverage not demonstrated. No candidate. |
| N | View audit only | POS header-to-detail cardinality proven locally; 1,208/1,350 exact duplicate details in biz_123/dev_006. SQL/pandas monthly revenue agree (`sqlite_view_audit.json`). Train exact, Wilson bounds, date semantics, 10 hand checks and official integration pending. No candidate. |

Composed candidate withheld until isolated buckets have user-reported leaderboard results. Tentative review priority J, then L, K, M. This is evidence/risk ranking, not predicted leaderboard correctness. Number of frozen candidates created in this environment: **0**.

## C — opportunity matrix

`opportunity_matrix.csv`: 104 observed public `(business, family)` cells, counts from a documented heuristic classification (not gold), each with source filenames, README excerpt, proposed grain/roles, blocker, effort and stage. `dev_006` POS and `dev_002` monthly Excel have proposed train analogues; other cells remain `đã scan`. Do not interpret `mapping đề xuất` as public enabled. For CSV header-grain and other Excel archetypes, role evidence is insufficient here; prioritize a fresh schema/README audit before implementation.

## D — SQLite POS capability

`biz_123`: 33,630 headers, 64,149 raw detail rows; `dev_006`: 37,833 headers, 72,411 details. Both have one unique header per MaHoaDon, no orphan detail, exact JOIN row count equals raw detail count, four status values and returns status matches return table in view audit. Detail duplicate keys are exact duplicate rows (1,208/1,350) and must be removed **within the same order**. Never sum header money after JOIN. `sqlite_sales_view.py` computes scoped monthly revenue, order count, cancel %, AOV, prior-month growth and max-day; independent SQL/pandas revenue and daily aggregates agree for both data sets. Date source uses ISO `ThoiGianLap`; cross-check against mixed-format `NgayLap` remains. `SLQuyDoi` present, but conversion semantics not independently recomputed. No public activation: full train replay and Wilson criterion pending. Fallback is completed read-only view audit and J builder, not an unverified N.

## E — optional local LLM

`bench_llama.py` prepared for 50 train questions, business-separated few-shot, typed JSON intent with family/period/top_k and JSON grammar. llama.cpp/model absent here, so **no benchmark was run**, no comparison or latency result exists. Holdout-by-business comparison and final disagreement-only decision remain pending.

## Local checks actually run

- `python patch/chat09_raw.py --root work --out artifacts/chat09` — pass, raw audit.
- `python patch/chat09_matrix.py --root work --out artifacts/chat09` — pass, 104 cells and 31 rulebook table differences.
- `python patch/sqlite_sales_view.py --root work --out artifacts/chat09` — pass, SQL/pandas equality.
- `python patch/verify_local.py` — pass, 5 J raw outputs, K/L lexical tests, POS cardinality, J question selection.
- `python -m py_compile patch/*.py` — pass.
- No official repo tests, Windows hash checks, official validator, leaderboard submission or train-exact replay were run.

## Windows resume

Copy `patch/` to `D:\ZALO\patches\chat09_delivery` and execute:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File D:\ZALO\patches\chat09_delivery\resume_chat09.ps1 -ProjectRoot D:\ZALO -PatchRoot D:\ZALO\patches\chat09_delivery
```

This halts on hash mismatch, snapshots code/config/tests, reruns raw and SQL audits, then creates J exclusively from G. Review `artifacts\chat09\candidate_j_diff.json`; run the existing official `validate_submission` on `candidate_j_from_g.jsonl` using its actual CLI signature, record its output and hash in STATE before considering a slot. If J exists, inspect its manifest/hash and do not overwrite it. Then work K and L isolated gates, M train-wide false-positive evaluation, and N train replay/Wilson; no candidate is enabled merely because code ran.
