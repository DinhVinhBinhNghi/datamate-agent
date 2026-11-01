"""Bounded parsing and safety gate for a future local model adapter.

The CLI's local path stays disabled until a real runtime/model is installed and
benchmarked. This module can be exercised with an in-process mock producer.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Callable

from datamate.execution.oracle_plan import execute_plan
from datamate.planner.validate import PlannerFailure, to_query_plan, validate_intent

PROMPT_VERSION = "v1"
MAX_RAW_CHARS = 32_768


def _unfence_once(raw: str) -> str | None:
    """Only remove a complete Markdown fence; never add/change JSON values."""
    stripped = raw.strip()
    if not stripped.startswith("```") or not stripped.endswith("```"):
        return None
    lines = stripped.splitlines()
    if len(lines) < 3 or lines[0].lower() not in ("```json", "```") or lines[-1] != "```":
        return None
    return "\n".join(lines[1:-1])


def parse_and_gate(raw: str, question: dict, root: Path, *, model: str,
                   runtime: str, latency_seconds: float) -> dict:
    """Return a planner record, not an oracle plan, on any failure."""
    record = {
        "question_id": question.get("id"), "planner": "local_candidate",
        "prompt_version": PROMPT_VERSION, "model": model, "runtime": runtime,
        "latency_seconds": round(latency_seconds, 6), "retry_count": 0,
        "raw_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest() if isinstance(raw, str) else None,
    }
    try:
        if not isinstance(raw, str) or not raw or len(raw) > MAX_RAW_CHARS:
            raise PlannerFailure("empty_or_oversize_raw_output")
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as first_error:
            repaired = _unfence_once(raw)
            if repaired is None:
                raise PlannerFailure(f"json_syntax:{first_error.msg}") from first_error
            record["retry_count"] = 1
            try:
                obj = json.loads(repaired)
            except json.JSONDecodeError as exc:
                raise PlannerFailure(f"json_syntax_after_one_repair:{exc.msg}") from exc
        intent = validate_intent(obj, question, root)
        plan = to_query_plan(intent, question, root)
        record.update(status="planned", parsed_intent=intent.to_dict(), plan=plan.to_dict())
    except (PlannerFailure, TypeError, ValueError, KeyError, OSError) as exc:
        record.update(status="planner_failure", error_layer="planner", failure_reason=str(exc))
    return record


def run_with_producer(question: dict, root: Path,
                      producer: Callable[[dict, float, int], str],
                      *, model: str = "mock", runtime: str = "mock",
                      timeout_seconds: float = 20.0, max_output_tokens: int = 512,
                      execute: bool = False) -> dict:
    """Producer contract: enforce its own wall timeout; no fallback answer.

    A real HTTP adapter must set a network timeout. This wrapper never invokes
    the oracle for failures and never estimates correctness from model confidence.
    """
    start = time.perf_counter()
    try:
        raw = producer(question, timeout_seconds, max_output_tokens)
    except (TimeoutError, OSError, ValueError) as exc:
        return {"question_id": question.get("id"), "planner": "local_candidate",
                "prompt_version": PROMPT_VERSION, "model": model, "runtime": runtime,
                "raw_sha256": None, "parsed_intent": None, "retry_count": 0,
                "latency_seconds": round(time.perf_counter() - start, 6),
                "status": "planner_failure", "error_layer": "planner",
                "failure_reason": f"model_error:{type(exc).__name__}:{exc}"}
    record = parse_and_gate(raw, question, root, model=model, runtime=runtime,
                            latency_seconds=time.perf_counter() - start)
    if execute and record["status"] == "planned":
        record["execution"] = execute_plan(record["plan"], root, root / "train")
        record["status"] = "ok" if record["execution"]["status"] == "ok" else "execution_failure"
        if record["status"] == "execution_failure":
            record["error_layer"] = record["execution"].get("error_layer", "execution")
    return record
