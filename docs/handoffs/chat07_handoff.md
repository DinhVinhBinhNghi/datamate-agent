# Chat 7 / Wave 1 handoff — direct revenue expansion

## ĐÃ XÁC MINH
- Baseline giữ nguyên: `chat07_public_20261030_181131`, 10/1.000 answered, SHA-256 `c8c57a2cca00047099c293c5ba642d864d9b706132891bb43858cfc605cf7ea6`, leaderboard `0.010`.
- Best local + best leaderboard: `wave1_public_revenue_20261030_220018`, leaderboard user-reported `0.018`.
- Candidate B: `artifacts/submissions/submission_wave1_public_revenue_20261030_220018.jsonl`.
- Candidate B SHA-256: `0eb7eb9f730bf8f0cbafb8dc3db5fe73b4f75bef99086dfcd5e21591ccf8c66a`.
- Reproduce: `$env:PYTHONPATH='D:\ZALO\src'; .\.venv\Scripts\python.exe -m datamate.wave1_group4_public --project-root D:\ZALO --run-id wave1_public_revenue_20261030_220018 --baseline "D:\ZALO\artifacts\submissions\submission_chat07_public_20261030_181131.jsonl"`.
- Group 0: freeze baseline/source/config/tests; snapshot phục hồi `wave1_prechange_20261030_183948`.
- Group 1: audit archetype monthly Excel trên `biz_102/103/104/dev_002`; xác minh sheet/cột/grain/coverage, không overlap fragment, `Tổng tiền` là line amount.
- Group 2: thêm business function doanh thu generic; dùng ngày đặt, Decimal/integer VND, loại cả đơn huỷ/trả, tính đơn đang giao, fail-closed và evidence đầy đủ.
- Group 3: kiểm kê 357 câu của ba business train; target 29 direct-revenue; exact 29 correct, 0 wrong, 0 abstain, 0 false-positive ngoài target.
- Group 4: bật public chỉ cho 8 pattern hôm nay/hôm qua/tháng; growth/average/max-day/product/customer/ranking vẫn abstain.
- Public Candidate B: 18/1.000 answered; 982 abstain; 15 number; 3 percent; accuracy không có.
- Diff với baseline: đúng 8 dòng `abstain -> number`; 0 unexpected, 0 missing, 0 evidence error; baseline SHA không đổi.
- Windows regression cuối: 90 passed + 40 subtests; train targeted 29/29; biz_129 giữ 7 correct/0 wrong.
- Runtime end-to-end Group 4: 102.448s; freeze/validation/diff/public report đã lưu dưới `artifacts/runs/wave1_public_revenue_20261030_220018`.

## SUBMISSION LOG
- Baseline: score `0.010`; Candidate B: score `0.018`; delta leaderboard `+0.008`.
- Timestamp submit và slot trong ngày chưa được cung cấp; không tự suy đoán. Score source: user-reported.

## SUY LUẬN THẬN TRỌNG
- Vì Candidate B chỉ khác baseline ở 8 câu, delta dương chứng minh Wave 1 có lợi ở cấp nhóm.
- Không dùng leaderboard để gán nhãn từng câu; không khẳng định 8/8 public đúng và không suy công thức normalize khi tài liệu chưa xác nhận.

## ACCEPTED / ROLLBACK
- Accepted: monthly-sales config/adapter, direct-revenue function, narrow classifier, evidence gate, exact train evaluator, guarded public diff/packager.
- Rolled back: none. Có rollback Group 0–4; baseline và mọi candidate cũ vẫn được giữ.

## RỦI RO / BACKLOG / REVIEW
- Chỉ validate targeted 29 câu trên `biz_102/103/104`, không phải toàn bộ 3.000 train; public vẫn abstain 98,2%.
- Public không có gold; source workbook/README raw hashes chưa nằm đầy đủ trong freeze manifest.
- Backlog: lập Pareto train theo family/archetype; map public business tương đồng bằng schema/rule evidence; chọn đúng một bucket tiếp theo; bổ sung raw-data hash.
- Cuộc họp cần chọn Wave 2 bằng `question count × train exactness × transfer evidence / effort`, không chọn theo cảm giác hay leaderboard từng câu.
- Chỉ mở Chat 8 khi có family inventory + train analogues + business rules đủ rõ; vẫn giữ Candidate B làm rollback/best-known.
