"""Run a constrained planner, validate its oracle-compatible plan, then execute."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from datamate.execution.oracle_plan import execute_plan
from datamate.planner.heuristic import plan_heuristic
from datamate.planner.validate import PlannerFailure, to_query_plan


def lookup_question(path: Path, question_id: str) -> dict:
    with path.open(encoding="utf-8-sig") as source:
        for line in source:
            if line.strip():
                item = json.loads(line)
                if item["id"] == question_id:
                    return item
    raise PlannerFailure(f"question_id_not_found:{question_id}")


def run_question(question: dict, root: Path, planner: str = "heuristic", execute: bool = True) -> dict:
    started = time.perf_counter()
    result = {"question_id": question["id"], "planner": planner}
    try:
        if planner == "local":
            raise PlannerFailure("local_model_not_configured")
        if planner != "heuristic":
            raise PlannerFailure("planner_not_allowed")
        intent = plan_heuristic(question)
        plan = to_query_plan(intent, question, root)
        result.update(status="planned", intent=intent.to_dict(), plan=plan.to_dict())
    except (PlannerFailure, KeyError, TypeError, ValueError, OSError) as exc:
        result.update(status="planner_failure", error_layer="planner", reason=str(exc))
        result["planner_seconds"] = round(time.perf_counter() - started, 6)
        return result
    result["planner_seconds"] = round(time.perf_counter() - started, 6)
    if execute:
        result["execution"] = execute_plan(plan.to_dict(), root, root / plan.ruleset)
        result["status"] = "ok" if result["execution"]["status"] == "ok" else "execution_failure"
        if result["status"] != "ok":
            result["error_layer"] = result["execution"].get("error_layer", "execution")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question-id", required=True)
    parser.add_argument("--planner", choices=("heuristic", "local"), default="heuristic")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--questions", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    questions = args.questions or root / "train/questions.jsonl"
    output = args.output or root / "artifacts/planner/planner_results.jsonl"
    try:
        question = lookup_question(questions, args.question_id)
        result = run_question(question, root, args.planner, not args.plan_only)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("a", encoding="utf-8") as sink:
            sink.write(json.dumps(result, ensure_ascii=False, allow_nan=False) + "\n")
    except (PlannerFailure, OSError, json.JSONDecodeError) as exc:
        print(f"PLANNER FAILED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"ok", "planned"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
