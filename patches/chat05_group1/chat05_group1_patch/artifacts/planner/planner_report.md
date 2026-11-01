# Planner checkpoint — Chat 5, Nhóm 1

## Đã xác minh trong workspace local (Linux, 30/10/2026)

- Nguồn code: các patch Chat 3/4 trong dự án; oracle schema giữ nguyên sáu field runtime.
- Supported: `train/biz_129`, operation `resolve_period`, `revenue`, `order_count`, `cancel_rate`.
- Heuristic template khớp chặt; `QuestionIntent` chặn filter/grouping/comparison/top_k; `QueryPlan` không nhận SQL, code, path, column hay `expected_value`.
- `python -m unittest discover -s tests/planner -v`: 7 tests pass (cần xác nhận lại sau khi chạy Windows).
- End-to-end: q_07f86ff2d62b → revenue tháng 3/2026 → executor ok; q_113fb704f84d → order_count hôm qua → ok; q_5fd698a99bce → cancel_rate tháng này → ok.
- Các kết quả chạy thực tế local nằm ở `planner_results.jsonl` trong workspace; thời gian/đường dẫn là của Linux, chưa phải benchmark máy Windows.
- Planner failure tách khỏi loader/execution/formatter failure; `local` hiện trả `local_model_not_configured`.

## Còn thiếu / chưa đo

- Chưa chạy checkpoint trên `D:\ZALO`, chưa có CPU/RAM/runtime/model output; chưa chọn/tải model.
- Chưa đánh giá accuracy với nhãn oracle trên development set; ba câu chỉ xác nhận pipeline chạy được, không phải benchmark.
- Chưa thực hiện Nhóm 2–4; heuristic chỉ hỗ trợ cấu trúc câu giới hạn, chưa bảo đảm xử lý các biến thể.
- `family_inventory.csv` và `rule_traceability.csv` chưa được đính kèm, không dùng làm bằng chứng coverage.
- Data coverage guard và gates đầy đủ đối với raw output của model thuộc Nhóm 3; hiện model path chưa bật.
