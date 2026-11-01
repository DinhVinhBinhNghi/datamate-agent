# Planner evaluation — Chat 5 Nhóm 4

Development questions only; 10 intent labels were written by hand from the question text and Chat 4 allowlist. This is a deliberately selected set, not a representative or held-out estimate of 3,000 questions.

```json
{
  "development_total": 10,
  "hand_labeled_supported": 5,
  "hand_labeled_unsupported": 5,
  "heuristic_planned": 5,
  "heuristic_json_valid": "5/5",
  "heuristic_schema_pass": "5/5",
  "supported_family_correct": "5/5",
  "supported_period_correct": "5/5",
  "supported_type_correct": "5/5",
  "unsupported_detected": "5/5",
  "planner_latency_p50_seconds": 0.000193,
  "planner_latency_p95_seconds": 0.000437,
  "heuristic_retries": 0,
  "heuristic_timeouts": 0,
  "model_json_valid": null,
  "model_accuracy": null,
  "model_latency": null,
  "default_planner": "heuristic",
  "execution_run": false
}
```

| Question ID | Oracle supported | Planner | Family | Period | Category |
|---|---|---|---|---|---|
| q_07f86ff2d62b | True | planned | revenue | tháng 3/2026 |  |
| q_0eebfe5b43c4 | True | planned | revenue | quý 1/2025 |  |
| q_113fb704f84d | True | planned | order_count | hôm qua |  |
| q_5fd698a99bce | True | planned | cancel | tháng này |  |
| q_92d3d19aeafa | True | planned | revenue | hôm qua |  |
| q_072e9d4f9c8e | False | planner_failure |  |  | unsupported |
| q_12829de2ae90 | False | planner_failure |  |  | unsupported |
| q_237a88f0c7e3 | False | planner_failure |  |  | unsupported |
| q_383a90720a49 | False | planner_failure |  |  | unsupported |
| q_5cc913d371cd | False | planner_failure |  |  | unsupported |

Rejection categories (correct unsupported detection included): {"unsupported": 5}

Error taxonomy: intent, period, entity/filter, unsupported, schema, latency. Categories not observed in this selected set have count 0; no model latency was measured.

Comparison: heuristic measured; local model unavailable. Keep heuristic as default. Model path remains optional backlog until an installed model shows better coverage/accuracy at acceptable latency and schema pass rate.

No train answers were put in a runtime prompt; no public test labels were used. Executor outcomes are intentionally excluded from planner metrics.
