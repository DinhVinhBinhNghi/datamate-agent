# Chat 08 plan — backlog evidence-first

## Primary — A: 23 câu còn lại của dev_002

1. Chia theo family; xử lý AOV/growth/max-day/share trước, rồi product/ranking/customer.
2. Mỗi family cần exact oracle biz_102/103/104, false-positive audit, evidence gate và baseline regression.
3. Chỉ bật pattern có train exact; public diff phải đúng expected IDs; Candidate B là rollback.

## Secondary — B: sales core dev_006 / analogue biz_123

1. Xác minh README/schema semantics, date/status/amount grain và join cardinality.
2. Tạo read-only views orders/status và sales; exact-score toàn target biz_123.
3. Mở public từng metric sau train exact + transfer checklist.

## Stretch — C: product/customer/debt/inventory

1. Pilot dev_006/biz_123: products/units và payments/debt trước, inventory/purchases sau.
2. Tách unit conversion, customer identity, debt snapshot/flow và inventory snapshot.
3. Industry-specific fail-closed tới khi rulebook + README + exact oracle đủ.

## Stop/go gates

- Go: exact train target, zero false positives, provenance, cardinality proof, expected-only public diff.
- Stop: semantic chưa chứng minh, kỳ ngoài coverage, ambiguous classifier, unexplained join inflation, hoặc regression đổi Candidate B.
