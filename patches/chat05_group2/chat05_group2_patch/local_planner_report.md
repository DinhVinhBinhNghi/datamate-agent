# Planner development checkpoint — Chat 5 Nhóm 2

Plan-only heuristic; không phải model benchmark hay answer accuracy.

```json
{
  "total": 10,
  "planned": 5,
  "planner_failure": 5,
  "heuristic_plan_json_valid": 5,
  "heuristic_plan_schema_pass": 5,
  "planner_latency_p50_seconds": 0.000178,
  "planner_latency_p95_seconds": 0.00062,
  "model_json_valid_rate": null,
  "model_latency_p50_seconds": null,
  "model_runtime": "not installed",
  "execution_run": false
}
```

| Question ID | Planner status | Family | Period | Reason |
|---|---|---|---|---|
| q_07f86ff2d62b | planned | revenue | tháng 3/2026 |  |
| q_0eebfe5b43c4 | planned | revenue | quý 1/2025 |  |
| q_113fb704f84d | planned | order_count | hôm qua |  |
| q_5fd698a99bce | planned | cancel | tháng này |  |
| q_92d3d19aeafa | planned | revenue | hôm qua |  |
| q_072e9d4f9c8e | planner_failure |  |  | invalid_period_or_config:Unsupported period expression: 'bị huỷ trong tháng 1 năm 2025' |
| q_12829de2ae90 | planner_failure |  |  | unsupported_or_ambiguous_question_template |
| q_237a88f0c7e3 | planner_failure |  |  | unsupported_or_ambiguous_question_template |
| q_383a90720a49 | planner_failure |  |  | unsupported_or_ambiguous_question_template |
| q_5cc913d371cd | planner_failure |  |  | invalid_period_or_config:Unsupported period expression: 'tháng 7/2026 so với cùng kỳ năm ngoái thay đổi bao nhiêu phần trăm' |

Model path chưa chạy vì Ollama/model chưa có. Heuristic là default; model integration và JSON-valid rate thật thuộc backlog có điều kiện.
Accuracy theo oracle intent và unsupported detection sẽ đánh giá riêng ở Nhóm 4, chưa suy ra từ bảng này.
