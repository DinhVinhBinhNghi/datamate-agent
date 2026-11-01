"""Small command-line oracle operation for resolving a requested time period."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from datamate.time.resolve import PeriodResolutionError, resolve_period


def resolve_with_evidence(expression: str, as_of_date: str, calendar_path: Path, ruleset: str) -> dict:
    calendar = pd.read_csv(calendar_path)
    period = resolve_period(expression, as_of_date, calendar, ruleset)
    return {
        "operation": "resolve_period",
        "type": "date_range",
        "value": {"start": period.start.isoformat(), "end": period.end.isoformat()},
        "evidence": {
            "expression": expression,
            "as_of_date": as_of_date,
            "mode": period.mode,
            "ruleset": ruleset,
            "calendar_source": str(calendar_path),
            "calendar_rows": int(len(calendar)),
            "inclusive_endpoints": True,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expression", required=True)
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--calendar", type=Path, required=True)
    parser.add_argument("--ruleset", required=True, choices=("train", "public_test"))
    args = parser.parse_args(argv)
    try:
        result = resolve_with_evidence(args.expression, args.as_of_date, args.calendar, args.ruleset)
    except (PeriodResolutionError, OSError, ValueError) as exc:
        print(f"TIME OPERATION FAILED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
