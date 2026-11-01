"""Benchmark the measured slow Excel source before and after derived SQLite cache."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import pandas as pd

from datamate.cache import CacheError, build_cache, cache_path_for, read_cache
from datamate.load_business import ConfigError, read_config
from datamate.readers import SourceLoadError, load_source


def _timed(callable_):
    started = time.perf_counter()
    value = callable_()
    return value, round(time.perf_counter() - started, 6)


def benchmark(data_root: Path, cache_root: Path, repeats: int = 3) -> dict:
    if repeats < 2:
        raise ValueError("repeats must be at least 2")
    config = read_config("train", "biz_116")
    source_name = "sales_lines"
    direct_times: list[float] = []
    direct_frame = None
    for _ in range(repeats):
        direct_frame, elapsed = _timed(
            lambda: load_source(config, source_name, data_root)
        )
        direct_times.append(elapsed)

    cache_path, identity = cache_path_for(config, source_name, data_root, cache_root)
    build_started = time.perf_counter()
    build_cache(config, source_name, data_root, cache_root, frame=direct_frame)
    build_seconds = round(time.perf_counter() - build_started, 6)

    cached_times: list[float] = []
    cached_frame = None
    for _ in range(repeats):
        cached_frame, elapsed = _timed(lambda: read_cache(cache_path, identity))
        cached_times.append(elapsed)
    pd.testing.assert_frame_equal(cached_frame, direct_frame, check_dtype=True)

    direct_warm = statistics.median(direct_times[1:])
    cached_warm = statistics.median(cached_times[1:])
    speedup = direct_warm / cached_warm if cached_warm else None
    return {
        "business_id": "biz_116",
        "source_name": source_name,
        "source_format": "xlsx",
        "cache_format": "sqlite",
        "cache_key_components": identity,
        "cache_path": str(cache_path),
        "cache_build_seconds_from_loaded_frame": build_seconds,
        "direct_load_seconds": direct_times,
        "cached_load_seconds": cached_times,
        "direct_warm_median_seconds": round(direct_warm, 6),
        "cached_warm_median_seconds": round(cached_warm, 6),
        "warm_speedup": round(speedup, 3) if speedup is not None else None,
        "row_count": int(len(direct_frame)),
        "raw_round_trip_equal": True,
        "atomic_build": True,
        "cache_scope": "train/biz_116/sales_lines only",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path.cwd() / "train")
    parser.add_argument("--cache-root", type=Path, default=Path.cwd() / "data" / "cache")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts") / "loader" / "cache_benchmark.json",
    )
    args = parser.parse_args(argv)
    try:
        result = benchmark(args.data_root, args.cache_root, args.repeats)
    except (
        CacheError,
        ConfigError,
        SourceLoadError,
        AssertionError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"CACHE BENCHMARK FAILED: {exc}", file=sys.stderr)
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
