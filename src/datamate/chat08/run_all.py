from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from . import archetypes, inventory, prioritize


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild the complete Chat08 audit inventory")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    inv = inventory.run(args.project_root, args.output_dir)
    arch = archetypes.run(args.project_root, args.output_dir)
    pri = prioritize.run(args.output_dir)
    result = {
        "passed": bool(inv["validation"]["passed"] and arch["business_count"] == 44 and pri["dev002_remaining"] == 23),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "project_root": str(args.project_root),
        "output_dir": str(args.output_dir),
        "inventory_validation": inv["validation"],
        "archetype_validation": arch,
        "priority_validation": pri,
        "note": "Read-only scan; no public answers or candidate submission are generated.",
    }
    (args.output_dir / "run_all_checkpoint.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

