# DataMate — Chat 08 handoff

Ngày chốt: 2026-10-31  
Project root thật: `D:\ZALO`  
Mục đích: chuyển đầy đủ trạng thái audit, capability expansion, Prompt 2–3, kết quả leaderboard và blocker sang chat lập kế hoạch tiếp theo.

## 1. Kết luận điều hành

- **ĐÃ XÁC MINH:** inventory đọc đủ 3.000 train questions, 3.000 train answers và 1.000 public questions; có 30 train businesses và 14 public businesses; không mất hoặc trùng question ID.
- **ĐÃ XÁC MINH:** schema/archetype scan đọc 502 sheet/table của đủ 44 businesses, không business nào lỗi scan.
- **ĐÃ XÁC MINH:** baseline `chat07_public_20261030_181131` có 10 câu trả lời, leaderboard người dùng báo `0.010`, SHA-256 khớp.
- **ĐÃ XÁC MINH:** Candidate B `wave1_public_revenue_20261030_220018` có 18 câu trả lời, leaderboard người dùng báo `0.018`, SHA-256 khớp; đây vẫn là rollback an toàn.
- **ĐÃ XÁC MINH THEO LEADERBOARD NGƯỜI DÙNG:** Candidate G có 24 câu trả lời và đạt `0.024`. G hiện là **best-known leaderboard candidate**.
- **ĐÃ XÁC MINH:** Candidate G chỉ khác B ở sáu câu revenue-growth của `dev_002`; delta leaderboard `+0.006` bằng đúng upside tối đa của bucket sáu câu. Theo quy ước dự án, vẫn không biến public thành answer gold theo từng câu.
- **ĐÃ XÁC MINH:** Candidate H và I structurally valid nhưng **không được nộp** vì forensic public phát hiện lỗi semantics thật, được mô tả ở §8.
- **ĐÃ XÁC MINH:** không candidate C, D, F, H hoặc I nào được submit. Candidate F chỉ từng là best-local trước Prompt 3, không có leaderboard score.

## 2. Frozen submissions và rollback chain

| Artifact | Answered | Leaderboard | SHA-256 | Trạng thái |
|---|---:|---:|---|---|
| Baseline `chat07_public_20261030_181131` | 10/1.000 | 0.010 | `c8c57a2cca00047099c293c5ba642d864d9b706132891bb43858cfc605cf7ea6` | rollback gốc, giữ nguyên |
| Candidate B `wave1_public_revenue_20261030_220018` | 18/1.000 | 0.018 | `0eb7eb9f730bf8f0cbafb8dc3db5fe73b4f75bef99086dfcd5e21591ccf8c66a` | rollback an toàn |
| Candidate G `chat08_prompt3_20261031_221000_candidate_g_growth_percent` | 24/1.000 | **0.024** | `3af7a104c16e41249419c9cc9260ac68ef80c68141e8df32b4af2880952b88dd` | best-known, đã submit bởi người dùng |

Candidate G trên Windows:

```text
D:\ZALO\artifacts\submissions\submission_chat08_prompt3_20261031_221000_candidate_g_growth_percent.jsonl
```

Quy tắc parent từ chat sau:

1. G là parent ưu tiên vì đã qua local gates và leaderboard tốt hơn B.
2. B tiếp tục được giữ làm rollback cấp 1.
3. Baseline tiếp tục được giữ làm rollback gốc.
4. Không sửa đè bất kỳ file frozen submission nào; candidate mới phải là file mới và diff được kiểm soát.

## 3. Nhóm 1 — tái dựng trạng thái dự án

Đã đọc handoff Chat 01–07, Wave 1 closeout, manifest, metrics, diff, validation và submission artifacts có sẵn. Các mốc ban đầu đã được đối chiếu bằng bytes/hash trên Windows sau đó:

- Baseline: 1.000 dòng; 10 answer, 990 abstain; hash đúng.
- Candidate B: 1.000 dòng; 18 answer, 982 abstain; hash đúng.
- Candidate B chỉ thêm tám direct-revenue questions của `dev_002` so với baseline.
- Wave 1 train target direct revenue trên `biz_102`, `biz_103`, `biz_104`: 29 đúng, 0 sai, 0 abstain, 0 false positive theo closeout artifacts.
- Leaderboard B tăng từ `0.010` lên `0.018`; kết quả chỉ được dùng như tín hiệu bucket, không tạo public answer labels.

Đã phân biệt rõ các mức:

```text
data audited
  != loader tồn tại
  != business logic tồn tại
  != planner nhận diện
  != train exact validation
  != public enabled
  != leaderboard-confirmed
```

Việc evaluator chạy qua 3.000 câu chỉ có nghĩa đã duyệt toàn tập; không có nghĩa hệ thống hỗ trợ cả 3.000 câu.

## 4. Nhóm 2 — inventory 4.000 câu

Inventory là multi-label. Mỗi câu có đúng một `primary_family`, có thể có nhiều secondary family, required capabilities và ambiguity flags. `classifier_confidence` là evidence rule-based, không phải xác suất đúng.

### Validation inventory

| Split | Questions | Unique IDs | Businesses | Unknown | Ambiguous |
|---|---:|---:|---:|---:|---:|
| Train | 3.000 | 3.000 | 30 | 311 | 684 |
| Public | 1.000 | 1.000 | 14 | 132 | 299 |

- Missing primary family: 0 ở cả hai split.
- Duplicate question IDs: 0 ở cả hai split.
- Manual stratified review: 95 câu; 93 đồng thuận, 2 câu được sửa; agreement 97,89%.
- Unknown/ambiguous được giữ lại để review, không cưỡng ép nhãn.

### Primary-family counts

| Primary family | Train | Public |
|---|---:|---:|
| COGS/profit | 31 | 19 |
| average order value | 159 | 50 |
| cancel count/rate | 240 | 42 |
| customer ranking/loyalty | 115 | 54 |
| direct revenue | 884 | 257 |
| growth/comparison | 234 | 97 |
| industry-specific | 215 | 96 |
| inventory | 27 | 3 |
| max/min day | 93 | 9 |
| order count | 173 | 88 |
| payment/debt | 132 | 57 |
| product quantity | 132 | 36 |
| product ranking | 76 | 32 |
| purchase | 97 | 11 |
| revenue share | 81 | 17 |
| unsupported/unknown | 311 | 132 |

## 5. Nhóm 3 — archetype và capability map

- Đã quét README, rulebook, manifest và schema evidence cho đủ 44 businesses.
- Đã ghi 44 dòng business archetype; scan tổng cộng 502 table/sheet: 339 train và 163 public.
- Mỗi dòng giữ candidate roles cho date/status/amount/order/product/customer, fragment pattern, JOIN candidates, unit conversion, README evidence, train analogues và blocker.
- Tên cột giống nhau không được coi là bằng chứng semantics giống nhau.
- Không kích hoạt fact-to-fact hoặc many-to-many JOIN mới nếu chưa có cardinality proof.
- Capability views được thiết kế là read-only interface tối thiểu: `sales`, `orders/status`, `products/units`, `customers`, `payments/debt`, `inventory/purchases`.
- Raw data không bị sửa và không union cưỡng ép toàn bộ doanh nghiệp vào một physical schema chung.
- Public transfer ban đầu chỉ được chứng minh đủ cho archetype `monthly_excel_sales_lines`: `biz_102/103/104 -> dev_002`.

## 6. Priority map ban đầu

Ordinal score được dùng vì exactness, transfer evidence, effort và semantic risk chưa có thước đo số tuyệt đối. Question count là số đo thật; các yếu tố còn lại dùng ordinal scale có giải thích.

| Vai trò ban đầu | Bucket | Public questions | Ordinal score | Lý do/blocker |
|---|---|---:|---:|---|
| PRIMARY | `A_dev002_remaining_23` | 23 | 34,5 | cùng source adapter; cần exact family gates |
| SECONDARY | `B_dev_006_sales_core` | 44 | 19,556 | SQLite analogue `biz_123`; cần grain/cardinality/README proof |
| STRETCH | `C_product_customer_debt_inventory` | 308 | 12,32 | heterogeneous semantics, unit/customer/debt/inventory risks |
| STRETCH PILOT | `C_dev006_relational_extensions` | theo matrix | ordinal | pilot relational capabilities sau sales core |

Bucket A đã được triển khai một phần qua Prompt 2–3. Growth đã đi hết chu trình local -> public -> leaderboard. Product/customer còn blocker mới phát hiện.

## 7. Prompt 2 — capability expansion

### Thiết kế được thêm

- Capability contracts và registry.
- Read-only `SalesView` cho archetype monthly Excel sales lines.
- Explicit semantic roles từ config riêng từng business.
- Derived sales functions: AOV, revenue growth, max revenue day.
- Product functions: quantity, size quantity, ranking.
- Customer spend ranking.
- Full-train evaluator và public candidate generator có parent/diff/freeze gates.

### Train gates Prompt 2

| Family | Train exact | False positive | Gate |
|---|---:|---:|---|
| Average order value | 27/27 | 0 | PASS |
| Max revenue day | 13/13 | 0 | PASS |
| Customer spend ranking | 14/14 | 0 | PASS |
| Revenue growth | 27/30 | 0 | BLOCKED |
| Product quantity | 15/26 | 0 | BLOCKED |
| Product ranking | 12/13 | 0 | BLOCKED |

### Local candidates Prompt 2

| Candidate | Families | Added from B | Answered | Submission status |
|---|---|---:|---:|---|
| C | AOV + max revenue day | 5 | 23 | chưa submit |
| D | customer spend ranking | 1 | 19 | chưa submit |
| F | C + D | 6 | 24 | chưa submit; không có leaderboard score |

Sau public forensic ở Prompt 3, nhánh AOV và max-day của C được tính lại độc lập và khớp dữ liệu. Customer candidate D/F có lỗi `top_k` được mô tả ở §8, nên D/F không được dùng.

## 8. Prompt 3 — repair, Windows rerun và forensic public

### 8.1 Root cause của 15 train failures Prompt 2

- 3 revenue questions dạng “3 tháng liền nhau, mỗi tháng” bị classifier hiểu nhầm thành revenue-growth percent.
- 11 product quantity questions là tổng ly size M/L, không phải quantity của một named product.
- 1 câu customer ranking bị route nhầm sang product ranking.

### 8.2 Repair đã thực hiện

- Loại multi-month list khỏi growth-percent intent.
- Thêm typed intent `size_quantity` cho size M/L + đơn vị ly.
- Route customer-money ranking trước product ranking.
- Loại order-frequency wording khỏi customer-spend intent.
- Tạo forensic CSV/report cho từng failure group.

### 8.3 Prompt 3 train evaluation

Evaluator duyệt đủ 3.000 train questions. Trong 122 analogue targets hiện được classifier chọn: 122 correct, 0 wrong, 0 abstain. Điều này **không** có nghĩa hỗ trợ 3.000 câu.

| Sub-capability | Train exact | Ghi chú |
|---|---:|---|
| AOV | 27/27 | dev + holdout exact |
| Revenue growth percent | 27/27 | đã loại multi-month list |
| Max revenue day | 13/13 | dev + holdout exact |
| Exact product quantity | 15/15 | train exact nhưng public alias gap chưa được cover |
| Size M/L cup total | 12/12 | chỉ một business `biz_104`; temporal holdout, không có business holdout |
| Product ranking | 12/12 | train exact nhưng public alias gap chưa được cover |
| Customer spend ranking | 16/16 | train exact nhưng adversarial `Th9/... 3 khách` chưa được cover |

### 8.4 Windows run và verification

- Run ID: `chat08_prompt3_20261031_221000`.
- Rollback snapshot khi cài: `D:\ZALO\artifacts\rollback\chat08_prompt3_20261031_221001`.
- Manifest `passed=true`.
- Baseline và B hashes không đổi sau run.
- Code/config freeze không đổi trong run.
- `no_submission_performed=true`.
- Unit verification: 5 tests được discover; 4 pass, 1 skip với lý do measured artifact không nằm ở vị trí mặc định của test. Verifier đọc đúng Run ID và kết luận pass.

### 8.5 Candidate G/H/I tạo trên Windows

| Candidate | Added from B | Answered | Windows SHA-256 | Kết luận cuối |
|---|---:|---:|---|---|
| G growth percent | 6 | 24 | `3af7a104c16e41249419c9cc9260ac68ef80c68141e8df32b4af2880952b88dd` | đã submit, leaderboard 0.024 |
| H product | 7 | 25 | `c0e1324fceb61c8439b5ec111e7945e40e273e084cb4cedc370832bc610bf437` | không submit; public semantic errors |
| I composed | 19 | 37 | `a11e64ea5a200e2005c52126a1c3a6862175afebea2b9df09e9e405f56f14e51` | không submit; kế thừa H + top-k error |

### 8.6 Candidate G — evidence và leaderboard

Changed question IDs:

```text
q_2ac539902fe6
q_2ed4740ec705
q_45cb42f4dc7b
q_4ef479fd4803
q_a79c3c340077
q_d857fdab9c0a
```

Independent recomputation từ dev_002 raw workbooks:

| So sánh | Revenue target | Revenue reference | Growth |
|---|---:|---:|---:|
| 02/2026 vs 02/2025 | 159.156.000 | 198.885.000 | -19,98% |
| 03/2026 vs 03/2025 | 220.598.000 | 242.101.000 | -8,88% |
| 08/2025 vs 07/2025 | 238.238.500 | 228.031.000 | 4,48% |
| 10/2025 vs 09/2025 | 229.254.500 | 219.035.500 | 4,67% |
| 04/2026 vs 04/2025 | 207.491.000 | 229.699.000 | -9,67% |
| 04/2026 vs 03/2026 | 207.491.000 | 220.598.000 | -5,94% |

User submit G và báo leaderboard `0.024`, tăng đúng `+0.006` so với B.

### 8.7 Candidate H — lỗi public transfer đã xác minh

Rulebook public §8 nói các tên/cách viết cùng chỉ một thứ là cùng một thứ. Code H match một raw product string rồi group theo raw string, nên bỏ các biến thể hoa/thường, có/không dấu và khoảng trắng.

| Question | H trả | Rulebook-aware recomputation | Biến thể quan sát |
|---|---:|---:|---|
| `q_0ef28ee17f12`, Nước ép cam (M), 03/2025 | 15 | 151 | 127 + 15 + 9 |
| `q_b2bbe9c1e9fc`, Cà phê sữa (M), 02/2025 | 26 | 269 | 227 + 26 + 16 |
| `q_dec759a2f085`, Latte (M), 04/2026 | 6 | 118 | 105 + 7 + 6 |

Product ranking 06/2025 cũng sai sau canonical grouping:

1. Cà phê sữa (M): 303.
2. Cà phê đen (M): 301.
3. Trà đào cam sả (M): 301.

H trả thứ tự `Cà phê đen`, `Trà đào cam sả`, `Cà phê sữa`, nên sai tập/thứ tự top 3. Hai giá trị 301 bằng nhau phải tie-break theo tên vì source không có mã sản phẩm.

Kết luận: H có ít nhất bốn public outputs sai do product identity normalization; không được submit hoặc dùng làm parent.

### 8.8 Candidate I và D/F — lỗi `top_k`

Public question:

```text
q_ede70b7f6c13: Th9/2025 3 khach nao chi nhieu tien nhat?
```

Regex `(?:liet ke|cho toi|th)\s*([0-9]+)` bắt `Th9` và tạo `top_k=9`, thay vì bắt `3 khách`. Candidate I trả 9 tên; rulebook yêu cầu top 3 có đúng ba phần tử. Correct ranking theo raw data là:

1. Châu Quang Khánh — 1.415.500.
2. Đặng Trung Huy — 1.320.500.
3. Vũ Bích Phong — 1.289.000.

Candidate D/F dùng cùng nhánh customer ranking nên cũng không được dùng cho submission.

### 8.9 Các phần Prompt 2 có thể salvage

Independent recomputation cho năm public outputs AOV/max-day:

| Question group | Measured result |
|---|---|
| AOV 01/2025 | revenue 210.199.000 / 2.989 orders = 70.324 |
| AOV 06/2025 | revenue 221.770.500 / 3.185 orders = 69.630 |
| AOV 11/2025 | revenue 219.225.000 / 3.032 orders = 72.304 |
| Max revenue day 11/2025 | 2025-11-02; 11.898.000 |
| Max revenue day 07/2025 | 2025-07-27; 12.709.000 |

Các giá trị này khớp candidate C local. Candidate C chưa submit; muốn dùng phải tạo candidate mới từ parent G, không nộp lại C cũ từ parent B một cách mù quáng.

## 9. Vì sao train exact chưa đủ

Prompt 3 là ví dụ rõ nhất:

- Product quantity/ranking đạt train exact trên target classifier nhưng train target không cover biến thể tên sản phẩm giống dev_002.
- Customer ranking đạt train exact nhưng không cover câu có month shorthand đứng trước `K khách`.
- `inventory_label_disagreement` tồn tại ở một số family; inventory là audit evidence, không phải gold.
- Size quantity chỉ có temporal holdout trên một business.

Vì vậy gate mới cho chat sau phải có thêm:

1. Adversarial text tests.
2. Public transfer invariants từ README/rulebook.
3. Entity canonicalization audit.
4. Independent recomputation/sample review trước candidate creation.
5. Isolated candidate submission trước composed candidate.

## 10. File/artifact đã tạo trong Chat 08

### Inventory/audit

```text
D:\ZALO\artifacts\chat08\current_state_report.md
D:\ZALO\artifacts\chat08\current_state.json
D:\ZALO\artifacts\chat08\family_inventory_train.csv
D:\ZALO\artifacts\chat08\family_inventory_public.csv
D:\ZALO\artifacts\chat08\family_summary.csv
D:\ZALO\artifacts\chat08\business_archetype_matrix.csv
D:\ZALO\artifacts\chat08\capability_matrix.csv
D:\ZALO\artifacts\chat08\priority_buckets.csv
D:\ZALO\artifacts\chat08\manual_review_sample.csv
D:\ZALO\artifacts\chat08\chat08_plan.md
D:\ZALO\artifacts\chat08\missing_information.md
D:\ZALO\artifacts\chat08\inventory_validation.json
D:\ZALO\artifacts\chat08\run_all_checkpoint.json
```

### Prompt 2–3 reports/runs

```text
D:\ZALO\artifacts\chat08\chat08_prompt2_report.md
D:\ZALO\artifacts\chat08\chat08_prompt2_metrics.json
D:\ZALO\artifacts\chat08_prompt3\failure_forensics.md
D:\ZALO\artifacts\chat08_prompt3\final_report.md
D:\ZALO\artifacts\chat08_prompt3\growth_failures.csv
D:\ZALO\artifacts\chat08_prompt3\product_quantity_failures.csv
D:\ZALO\artifacts\chat08_prompt3\product_ranking_failures.csv
D:\ZALO\artifacts\chat08_prompt3\root_cause_summary.csv
D:\ZALO\artifacts\runs\chat08_prompt3_20261031_221000\capability_eval.json
D:\ZALO\artifacts\runs\chat08_prompt3_20261031_221000\expansion_manifest.json
D:\ZALO\artifacts\runs\chat08_prompt3_20261031_221000\freeze_manifest.json
```

### Main code added/changed

```text
src\datamate\chat08\inventory.py
src\datamate\chat08\archetypes.py
src\datamate\chat08\prioritize.py
src\datamate\chat08\reporting.py
src\datamate\chat08\run_all.py
src\datamate\chat08\run_expansion.py
src\datamate\chat08\prompt3_forensics.py
src\datamate\capabilities\contracts.py
src\datamate\capabilities\registry.py
src\datamate\capabilities\sales.py
src\datamate\business\derived_sales.py
src\datamate\business\product_analytics.py
src\datamate\business\customer_analytics.py
src\datamate\evaluation\capability_eval.py
tests\chat08\...
tests\chat08_expansion\test_capability_expansion.py
```

## 11. Lệnh kiểm tra/rerun

### Rebuild inventory read-only

```powershell
Set-Location D:\ZALO
$env:PYTHONPATH = 'D:\ZALO\src'

.\.venv\Scripts\python.exe -m datamate.chat08.run_all `
  --project-root D:\ZALO `
  --output-dir D:\ZALO\artifacts\chat08

.\.venv\Scripts\python.exe -m unittest discover -s tests\chat08 -v
```

### Verify frozen hashes

```powershell
Get-FileHash `
  'D:\ZALO\artifacts\submissions\submission_chat07_public_20261030_181131.jsonl' `
  -Algorithm SHA256

Get-FileHash `
  'D:\ZALO\artifacts\submissions\submission_wave1_public_revenue_20261030_220018.jsonl' `
  -Algorithm SHA256

Get-FileHash `
  'D:\ZALO\artifacts\submissions\submission_chat08_prompt3_20261031_221000_candidate_g_growth_percent.jsonl' `
  -Algorithm SHA256
```

### Verify Prompt 3 run without changing system execution policy

```powershell
Set-Location D:\ZALO\patches\prompt3_delivery

powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\verify_chat08_prompt3.ps1 `
  -ProjectRoot D:\ZALO `
  -RunId chat08_prompt3_20261031_221000
```

## 12. Recommended next plan

### Primary — low-risk composed candidate from G

Create a **new** candidate from parent G adding only the three AOV and two max-revenue-day outputs already train-exact and independently recomputed on public raw data. Required gates:

- Parent G hash exact.
- Exactly five expected new IDs; no overwrite of G's 24 non-abstain rows.
- Recompute values from raw source during build, not copy hard-coded answers.
- Structural validator, diff report, freeze manifest and no auto-submit.
- User reviews candidate before spending a submission slot.

Potential upside is five questions, but no leaderboard score should be predicted as fact.

### Secondary — repair product identity correctly

1. Introduce business-scoped `canonical_product_key` based on normalized case, accents and whitespace for clearly equivalent labels.
2. Audit collisions before merging; do not merge semantically different products merely because fuzzy text looks similar.
3. Normalize unit-conversion lookup with the same proven key.
4. Aggregate exact quantity and product ranking by canonical identity.
5. Return a deterministic raw label accepted by rulebook, preferably a label observed in source.
6. Add regression tests for the three dev_002 alias sets and June ranking.
7. Re-run full 3.000 train evaluator and explicit public transfer audit.
8. Create product-only candidate from G; do not compose until isolated review passes.

### Secondary — repair customer `top_k`

1. Parse `top K`, `K khách`, `liệt kê K khách` with anchored entity patterns.
2. Never use generic `th K` as top-k evidence because it collides with month shorthand.
3. Add adversarial regression: `Th9/2025 3 khách nào chi nhiều tiền nhất?` must produce `top_k=3`.
4. Apply rulebook tie-break instead of returning unanswerable at a ranking boundary when ties can be ordered by code/name.
5. Create isolated customer candidate only after train + adversarial tests pass.

### Secondary bucket — dev_006 sales core

Continue original capability-map choice only after the low-risk dev_002 items above:

- Verify SQLite README semantics, grain, date/status/amount roles.
- Prove join cardinality using train analogue `biz_123`.
- Build read-only sales/orders views.
- Exact-score the train analogue before any public enablement.

### Stretch

- Products/units and payments/debt on relational archetype.
- Inventory/purchases only after snapshot/flow and unit conversion proof.
- COGS/profit and industry-specific remain fail-closed.

## 13. Do not do

- Do not submit H, I, D or F.
- Do not infer Candidate F leaderboard accuracy; it was never submitted.
- Do not overwrite baseline, B or G.
- Do not call 122/122 “support for all 3.000 train questions”.
- Do not use one regex or inventory labels as answer ground truth.
- Do not hard-code public question IDs or public answer values into classifier/business logic.
- Do not JOIN fact-to-fact/many-to-many without cardinality proof.
- Do not auto-submit any future candidate.

## HANDOFF_CHAT08_C

```text
ĐÃ XÁC MINH: inventory đủ 3.000 train + 1.000 public, 30 + 14 businesses, không mất/trùng ID.
ĐÃ XÁC MINH: 502 table/sheet của đủ 44 businesses được scan, 0 business scan error.
ĐÃ XÁC MINH: baseline 10 answers, score 0.010, SHA c8c57a2c...5cf7ea6.
ĐÃ XÁC MINH: Candidate B 18 answers, score 0.018, SHA 0eb7eb9f...f8c66a.
ĐÃ XÁC MINH THEO LEADERBOARD USER: Candidate G 24 answers, score 0.024.
Candidate G SHA: 3af7a104c16e41249419c9cc9260ac68ef80c68141e8df32b4af2880952b88dd.
G chỉ thêm 6 revenue-growth questions từ B; independent recomputation khớp cả 6.
G hiện là best-known parent; B là rollback cấp 1; baseline là rollback gốc.
Prompt 2 train: AOV 27/27, max-day 13/13, customer spend 14/14.
Prompt 3 classified targets: 122 correct, 0 wrong, 0 abstain; không phải support 3.000 câu.
Candidate C/D/F là local-only, chưa submit; F không có leaderboard score.
Candidate H không submit: product aliases bị tách raw string, ít nhất 4 public outputs sai.
Candidate I không submit: kế thừa H và parse Th9 thành top_k=9 thay vì 3.
Candidate D/F customer branch cũng bị top_k bug, không được dùng.
Public product recomputation: Nước ép cam 151, Cà phê sữa 269, Latte 118.
Public June ranking đúng sau canonicalization: Cà phê sữa, Cà phê đen, Trà đào cam sả.
AOV/max-day 5 outputs đã được independent recompute và khớp Candidate C local.
PRIMARY NEXT: candidate mới từ G chỉ thêm AOV + max-day, expected-only diff, no auto-submit.
SECONDARY: canonical product identity + normalized unit lookup + product-only candidate.
SECONDARY: anchored customer top_k parser; regression Th9/2025 3 khách => top_k=3.
ORIGINAL SECONDARY: dev_006 sales core với biz_123 train analogue và cardinality proof.
Không overwrite baseline/B/G; không submit H/I/D/F; không hard-code public IDs/answers.
Rerun inventory: python -m datamate.chat08.run_all --project-root D:\ZALO --output-dir D:\ZALO\artifacts\chat08
Verify Prompt3: verify_chat08_prompt3.ps1 -ProjectRoot D:\ZALO -RunId chat08_prompt3_20261031_221000
```
