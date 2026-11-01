"""Small plan-only development benchmark; no train answers or public labels."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from datamate.plan_question import lookup_question, run_question


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    position = (len(values) - 1) * fraction
    lo = int(position)
    hi = min(lo + 1, len(values) - 1)
    return round(values[lo] + (values[hi] - values[lo]) * (position - lo), 6)


def benchmark(root: Path, ids_path: Path, questions_path: Path, output: Path, report: Path) -> dict:
    ids = json.loads(ids_path.read_text(encoding="utf-8"))
    if not isinstance(ids, list) or len(ids) != len(set(ids)) or not 5 <= len(ids) <= 10:
        raise ValueError("Provide 5–10 distinct development question IDs")
    results = [run_question(lookup_question(questions_path, qid), root, execute=False) for qid in ids]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in results), encoding="utf-8")
    planned = [r for r in results if r["status"] == "planned"]
    latencies = [r["planner_seconds"] for r in results]
    summary = {
        "total": len(results), "planned": len(planned), "planner_failure": len(results)-len(planned),
        "heuristic_plan_json_valid": len(planned), "heuristic_plan_schema_pass": len(planned),
        "planner_latency_p50_seconds": percentile(latencies, .5),
        "planner_latency_p95_seconds": percentile(latencies, .95),
        "model_json_valid_rate": None, "model_latency_p50_seconds": None,
        "model_runtime": "not installed", "execution_run": False,
    }
    lines = ["# Planner development checkpoint — Chat 5 Nhóm 2", "",
             "Plan-only heuristic; không phải model benchmark hay answer accuracy.", "",
             "```json", json.dumps(summary, ensure_ascii=False, indent=2), "```", "",
             "| Question ID | Planner status | Family | Period | Reason |", "|---|---|---|---|---|"]
    for r in results:
        intent = r.get("intent", {})
        lines.append(f'| {r["question_id"]} | {r["status"]} | {intent.get("family", "")} | {intent.get("period_expression", "")} | {r.get("reason", "")} |')
    lines += ["", "Model path chưa chạy vì Ollama/model chưa có. Heuristic là default; model integration và JSON-valid rate thật thuộc backlog có điều kiện.",
              "Accuracy theo oracle intent và unsupported detection sẽ đánh giá riêng ở Nhóm 4, chưa suy ra từ bảng này."]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.project_root.resolve()
    summary = benchmark(root, root / "tests/planner/fixtures/development_ids.json",
                        root / "train/questions.jsonl", root / "artifacts/planner/planner_benchmark_results.jsonl",
                        root / "artifacts/planner/planner_report.md")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
