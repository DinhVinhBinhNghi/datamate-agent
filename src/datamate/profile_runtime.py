"""Profile direct configured loads before deciding whether a cache is justified."""

from __future__ import annotations

import argparse
import gc
import json
import statistics
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any

from datamate.load_business import ConfigError, read_config
from datamate.readers import SourceLoadError, load_source


PILOTS = (
    ("train", "biz_129", "orders"),
    ("train", "biz_116", "sales_lines"),
    ("train", "biz_123", "orders"),
    ("train", "biz_123", "order_lines"),
)


def _measure_time_once(config: dict[str, Any], source_name: str, data_root: Path) -> dict[str, Any]:
    gc.collect()
    started = time.perf_counter()
    frame = load_source(config, source_name, data_root)
    elapsed = time.perf_counter() - started
    result = {
        "elapsed_seconds": round(elapsed, 6),
        "row_count": int(len(frame)),
        "column_count": int(len(frame.columns)),
    }
    del frame
    return result


def _measure_python_peak(
    config: dict[str, Any], source_name: str, data_root: Path
) -> float:
    """Measure memory separately so tracing overhead cannot distort load timing."""
    gc.collect()
    tracemalloc.start()
    frame = load_source(config, source_name, data_root)
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    del frame
    return round(peak_bytes / (1024 * 1024), 3)


def profile_direct_loads(data_root: Path, repeats: int = 3) -> dict[str, Any]:
    if repeats < 2:
        raise ValueError("repeats must be at least 2 to measure first and warm loads")
    profiles: list[dict[str, Any]] = []
    for split, business_id, source_name in PILOTS:
        config = read_config(split, business_id)
        iterations = [
            _measure_time_once(config, source_name, data_root)
            for _ in range(repeats)
        ]
        python_peak_mebibytes = _measure_python_peak(config, source_name, data_root)
        warm_seconds = [item["elapsed_seconds"] for item in iterations[1:]]
        profiles.append(
            {
                "split": split,
                "business_id": business_id,
                "source_name": source_name,
                "format": config["sources"][source_name]["format"],
                "iterations": iterations,
                "first_load_seconds": iterations[0]["elapsed_seconds"],
                "warm_median_seconds": round(statistics.median(warm_seconds), 6),
                "python_peak_mebibytes": python_peak_mebibytes,
            }
        )
    return {
        "profile_kind": "direct_loader",
        "repeats_per_source": repeats,
        "timing_note": (
            "first_load is the first load in this profiler process; OS disk-cache state "
            "is uncontrolled. warm_median uses later loads in the same process."
        ),
        "memory_note": (
            "python_peak_mebibytes is one separate tracemalloc run, not total process "
            "working set; tracing overhead is excluded from elapsed timings."
        ),
        "profiles": profiles,
        "summary": {
            "total_first_load_seconds": round(
                sum(item["first_load_seconds"] for item in profiles), 6
            ),
            "total_warm_median_seconds": round(
                sum(item["warm_median_seconds"] for item in profiles), 6
            ),
            "slowest_first_load": max(
                profiles, key=lambda item: item["first_load_seconds"]
            )["business_id"]
            + "/"
            + max(profiles, key=lambda item: item["first_load_seconds"])["source_name"],
            "slowest_warm_load": max(
                profiles, key=lambda item: item["warm_median_seconds"]
            )["business_id"]
            + "/"
            + max(profiles, key=lambda item: item["warm_median_seconds"])["source_name"],
        },
        "cache_decision": "pending_review_of_windows_profile",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path.cwd() / "train")
    parser.add_argument("--output", type=Path, default=Path("artifacts") / "loader" / "runtime_profile.json")
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args(argv)
    try:
        result = profile_direct_loads(args.data_root, args.repeats)
    except (ConfigError, SourceLoadError, KeyError, TypeError, ValueError) as exc:
        print(f"PROFILE FAILED: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
