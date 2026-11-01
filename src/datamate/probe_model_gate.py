"""Exercise model-output gates using fixed mock strings, with no model dependency."""

from __future__ import annotations

import json
from pathlib import Path

from datamate.plan_question import lookup_question
from datamate.planner.model_gate import run_with_producer


def main() -> int:
    root = Path.cwd()
    question = lookup_question(root / "train/questions.jsonl", "q_07f86ff2d62b")
    valid = json.loads((root / "tests/planner/fixtures/valid_intent.json").read_text(encoding="utf-8"))
    cases = [
        ("valid", json.dumps(valid, ensure_ascii=False)),
        ("fenced_json", "```json\n" + json.dumps(valid, ensure_ascii=False) + "\n```"),
        ("hallucinated_column", json.dumps({**valid, "entity_filter": {"column": "Invented"}}, ensure_ascii=False)),
        ("unsupported_family", json.dumps({**valid, "family": "debt"}, ensure_ascii=False)),
        ("wrong_business", json.dumps({**valid, "business_id": "biz_128"}, ensure_ascii=False)),
        ("invalid_period", json.dumps({**valid, "period_expression": "tháng 13/2026"}, ensure_ascii=False)),
        ("arbitrary_sql", json.dumps({**valid, "sql": "SELECT * FROM orders"}, ensure_ascii=False)),
        ("arbitrary_code", json.dumps({**valid, "python": "print(1)"}, ensure_ascii=False)),
        ("bad_syntax", "{bad json"),
    ]
    results = []
    for name, raw in cases:
        result = run_with_producer(question, root, lambda q, t, n, value=raw: value)
        results.append({"case": name, **result})
    def timeout(q: dict, seconds: float, tokens: int) -> str:
        raise TimeoutError("mock deadline")
    results.append({"case": "timeout", **run_with_producer(question, root, timeout)})
    output = root / "artifacts/planner/model_gate_results.jsonl"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in results), encoding="utf-8")
    planned = sum(row["status"] == "planned" for row in results)
    rejected = sum(row["status"] == "planner_failure" for row in results)
    summary = {"cases": len(results), "planned": planned, "rejected": rejected,
               "max_retry_count": max(row["retry_count"] for row in results),
               "oracle_executions": 0, "model_runtime": "mock"}
    report = root / "artifacts/planner/model_gate_report.md"
    report.write_text("# Model gate mock checkpoint — Chat 5 Nhóm 3\n\n"
                      + "```json\n" + json.dumps(summary, ensure_ascii=False, indent=2) + "\n```\n\n"
                      + "No real model was called. `model_gate_results.jsonl` records version, model/runtime, raw SHA-256, parsed intent/plan on success, retries, latency and failure reason.\n",
                      encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if (planned, rejected, summary["max_retry_count"]) == (2, 8, 1) else 2


if __name__ == "__main__":
    raise SystemExit(main())
