"""Chat 6 single-question and small-batch runner, official submission shapes."""
from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path

from datamate.contracts import Question, SubmissionRecord
from datamate.plan_question import run_question
from datamate.validate_submission import validate_row


def process_question(
    question: dict,
    root: Path,
    split: str,
    planner: str = "heuristic",
) -> tuple[dict, dict]:
    start = time.perf_counter()
    packet = {
        "id": question.get("id"),
        "business_id": question.get("business_id"),
        "ruleset": split,
        "planner": planner,
        "plan": None,
        "sources": [],
        "period": None,
        "checks": {},
        "typed_result": None,
    }
    record = {"id": question["id"], "type": "abstain"}

    try:
        Question.model_validate(question)
        if split != "train":
            raise ValueError(
                "unsupported_ruleset:public business rules/configs not verified"
            )

        result = run_question(question, root, planner, execute=True)
        packet["planner_seconds"] = result.get("planner_seconds")
        packet["plan"] = result.get("plan")
        if result["status"] != "ok":
            packet["error_layer"] = result.get("error_layer", "planner")
            raise ValueError(
                result.get("reason")
                or result.get("execution", {}).get("reason")
                or result["status"]
            )

        answer = result["execution"]["answer"]
        packet["typed_result"] = {
            "type": answer.get("type"),
            "value": answer.get("value"),
        }
        packet["execution_seconds"] = result["execution"].get("runtime_seconds")
        evidence = answer.get("evidence", {})
        packet["function_evidence"] = evidence
        packet["sources"] = evidence.get(
            "provenance_sources",
            [evidence["source"]] if "source" in evidence else [],
        )
        packet["period"] = evidence.get("period")
        packet["function"] = packet["plan"]["operation"]

        if answer.get("type") not in {"number", "percent"}:
            packet["error_layer"] = "formatter"
            raise ValueError("unsupported_executor_result_type")

        candidate = {
            "id": question["id"],
            "type": answer["type"],
            "answer": answer["value"],
        }
        SubmissionRecord.model_validate(candidate)
        errors = validate_row(candidate, 1)
        if errors:
            packet["error_layer"] = "formatter"
            raise ValueError("invalid_result:" + json.dumps(errors))

        record = candidate
        packet["checks"] = {
            "plan_gate": True,
            "execution_ok": True,
            "submission_shape": True,
        }
    except Exception as exc:
        packet.setdefault("error_layer", "pipeline")
        packet["reason"] = f"{type(exc).__name__}:{exc}"

    SubmissionRecord.model_validate(record)
    if validate_row(record, 1):
        raise ValueError("internal_invalid_submission_record")
    packet["formatted_answer"] = record
    packet["decision"] = "abstain" if record["type"] == "abstain" else "answer"
    packet["elapsed_seconds"] = round(time.perf_counter() - start, 6)
    return record, packet


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", required=True, choices=["train", "public_test"])
    parser.add_argument("--question-id", action="append")
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--planner", choices=["heuristic", "local"], default="heuristic"
    )
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()

    root = args.project_root.resolve()
    question_path = root / args.split / "questions.jsonl"
    questions = [
        json.loads(line)
        for line in question_path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    if args.question_id:
        selected = set(args.question_id)
        questions = [q for q in questions if q["id"] in selected]
        if selected - {q["id"] for q in questions}:
            parser.error("question ID not found")
    if args.limit is not None:
        if args.limit < 1:
            parser.error("limit must be positive")
        questions = questions[: args.limit]
    if not args.question_id and args.limit is None:
        parser.error("Group 1 requires --question-id or --limit")

    run_id = "chat06_" + uuid.uuid4().hex[:12]
    folder = root / "artifacts" / "runs" / run_id
    folder.mkdir(parents=True)
    decisions = {"answer": 0, "abstain": 0}
    with (
        (folder / "predictions.jsonl").open("w", encoding="utf-8") as predictions,
        (folder / "evidence.jsonl").open("w", encoding="utf-8") as evidence,
    ):
        for question in questions:
            record, packet = process_question(question, root, args.split, args.planner)
            predictions.write(
                json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n"
            )
            evidence.write(
                json.dumps(packet, ensure_ascii=False, allow_nan=False) + "\n"
            )
            predictions.flush()
            evidence.flush()
            decisions[packet["decision"]] += 1

    manifest = {
        "run_id": run_id,
        "version": "chat06-group1",
        "split": args.split,
        "planner": args.planner,
        "question_ids": [q["id"] for q in questions],
        "count": len(questions),
        "decisions": decisions,
        "predictions": str(folder / "predictions.jsonl"),
        "evidence": str(folder / "evidence.jsonl"),
    }
    (folder / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
