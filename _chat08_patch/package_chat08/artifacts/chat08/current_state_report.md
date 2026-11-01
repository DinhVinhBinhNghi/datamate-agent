# Chat 08 — Current state report

## Kết luận điều hành

- **ĐÃ XÁC MINH:** 3.000 train questions, 3.000 train answers, 1.000 public questions, 30 train businesses, 14 public businesses; không mất/trùng ID.
- **ĐÃ XÁC MINH:** lightweight schema scan đọc 502 sheet/table (339 train + 163 public), khớp Chat02, không business nào lỗi scan.
- **ĐÃ XÁC MINH:** baseline có 1.000 dòng, 10 answer/990 abstain và SHA-256 c8c57a2...5cf7ea6.
- **ĐÃ XÁC MINH THEO CLOSEOUT, CHƯA BYTE-VERIFY:** Candidate B 18 answer/982 abstain, chỉ thêm 8 direct-revenue của dev_002; hash được báo 0eb7eb9f...f8c66a.
- **SUY LUẬN THẬN TRỌNG:** delta leaderboard người dùng báo +0.008 chứng minh Wave 1 có lợi ở cấp nhóm; không gán nhãn đúng/sai từng câu.
- **CÒN THIẾU:** Candidate B bytes và actual run manifest/metrics/diff/submission log.
- **ĐÃ XÁC MINH:** one-command rebuild passed; 5/5 Chat08 contract tests passed.

## Module và mức hỗ trợ thật

| Module | Business/family hỗ trợ thật | Validation | Hạn chế |
| --- | --- | --- | --- |
| Question/data audit | all 4,000 questions and 44 folders at structural-audit level | 3,000 train + 1,000 public; 30 + 14 businesses; 502 tables scanned | audit/candidate labels are not executable metric support |
| Loader | Chat03 biz_129/biz_116/biz_123; Wave1 biz_102/103/104/dev_002 | Chat03 11 tests; biz_123 one-to-many proof; Wave1 reported 90 tests + 40 subtests | not a universal contract for all 44 businesses |
| Business logic | biz_129 revenue/order/cancel; biz_102/103/104 + dev_002 direct revenue only | biz_129 7 exact; Wave1 direct revenue 29/29 target pool | growth/AOV/ranking/customer/debt/inventory unsupported |
| Planner | narrow heuristic allowlist + Wave1 direct-revenue classifier | 15 planner tests; fail-closed gates; no local model | running 3,000 questions does not mean supporting 3,000 |
| Runner/gates/formatter | train adapters; public dev_002 narrow families | Chat06 14 pipeline tests; baseline 1,000 valid rows; Wave1 guarded diff reported | full current D:\ZALO snapshot/run directory not attached |
| Public baseline/Candidate B | baseline 10 dev_002 answers; Candidate B adds 8 direct-revenue answers | baseline bytes/hash verified here; Candidate B aggregate/hash from closeout | public per-question correctness unknown; no auto-submit |

Phân biệt: raw audited ≠ loader verified ≠ business logic verified ≠ train exact ≠ public enabled. Chi tiết ở capability_matrix.csv.

## Inventory 4.000 câu

| Primary family | Train | Public |
| --- | --- | --- |
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

- Unknown: train 311/3.000; public 132/1.000.
- Ambiguous flags: train 684; public 299. Period unspecified là cờ review, không đồng nghĩa nhãn sai.
- Manual stratified review: 95 câu, 93 đồng thuận, 2 sửa; agreement 97.89%.
- classifier_confidence chỉ là mức evidence rule-based, không phải xác suất đúng.

## Archetype/capability

- Mỗi business có một dòng; cột semantic/JOIN ngoài case đã verify đều là candidate.
- Public transfer chỉ verified cho direct revenue biz_102/103/104 → dev_002. Analogue khác chỉ là similarity header/format.
- Không kích hoạt JOIN fact-to-fact/many-to-many mới. Capability view là read-only interface tối thiểu, không ép schema chung.

## Bucket đã chọn

| Vai trò | Bucket | Public questions | Ordinal score | Blocker |
| --- | --- | --- | --- | --- |
| PRIMARY | A_dev002_remaining_23 | 23 | 34.5 | must add per-family exact train oracles for AOV/growth/product/customer/ranking before public enablement |
| SECONDARY | B_dev_006_sales_core | 44 | 19.556 | README semantics, grain/cardinality, source coverage and train exact adapter validation required |
| STRETCH | C_product_customer_debt_inventory | 308 | 12.32 | unit conversion, customer identity, debt snapshots, purchase/inventory flow, COGS and industry rules need separate adapters |

Primary A được chọn sau khi so toàn inventory vì cùng dev_002 đã có adapter/public gate. Secondary B chọn dev_006 vì SQLite có analogue biz_123 similarity 0.9554 và join biz_123 đã verify; vẫn phải exact-validate train. Stretch C giữ riêng vì unit/customer/debt/inventory semantics rủi ro cao.

## Tính toàn vẹn

Chat08 chỉ đọc raw data và tạo audit artifacts. Không tạo public answer/candidate mới, không nộp leaderboard, không sửa baseline/Candidate B.
