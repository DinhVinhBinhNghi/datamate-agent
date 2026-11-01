from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from pathlib import Path

from openpyxl import Workbook

from datamate.audit_dataset import run_audit
from datamate.analyze_audit import analyze_split


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_sources(tmp_path: Path) -> tuple[Path, list[Path]]:
    root = tmp_path / "train"
    csv_dir = root / "data" / "biz_csv"
    xlsx_dir = root / "data" / "biz_xlsx"
    sqlite_dir = root / "data" / "biz_sqlite"
    for directory in (csv_dir, xlsx_dir, sqlite_dir):
        directory.mkdir(parents=True)

    csv_path = csv_dir / "orders.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(["Mã đơn", "Ngày bán", "Trạng thái"])
        for index in range(30):
            writer.writerow([f"O{index:03}", f"2026-01-{index % 28 + 1:02}", "xong"])

    xlsx_path = xlsx_dir / "multi.xlsx"
    workbook = Workbook()
    visible = workbook.active
    visible.title = "Sales"
    visible.append(["SALES DETAIL"])
    visible.append(["Period: all", "Channel: all"])
    visible.append([])
    visible.append(["ID", "Ngày", "Tổng"])
    for index in range(30):
        visible.append([index + 1, date_text(index), f"=A{index + 2}*2"])
    visible.merge_cells("E1:F1")
    hidden = workbook.create_sheet("HiddenLookup")
    hidden.sheet_state = "hidden"
    hidden.append(["Code", "Name"])
    hidden.append(["A", "Alpha"])
    workbook.save(xlsx_path)

    sqlite_path = sqlite_dir / "pos.sqlite"
    connection = sqlite3.connect(sqlite_path)
    connection.executescript(
        "CREATE TABLE orders(id TEXT PRIMARY KEY, order_date TEXT, amount REAL);"
        "CREATE TABLE lines(id INTEGER PRIMARY KEY, order_id TEXT, "
        "FOREIGN KEY(order_id) REFERENCES orders(id));"
    )
    connection.executemany(
        "INSERT INTO orders VALUES (?, ?, ?)",
        [(f"O{i:03}", date_text(i), float(i)) for i in range(30)],
    )
    connection.executemany(
        "INSERT INTO lines(id, order_id) VALUES (?, ?)",
        [(i + 1, f"O{i % 30:03}") for i in range(60)],
    )
    connection.commit()
    connection.close()
    return root, [csv_path, xlsx_path, sqlite_path]


def date_text(index: int) -> str:
    return f"2026-01-{index % 28 + 1:02}"


def test_pilot_audits_three_formats_without_modifying_sources(tmp_path: Path) -> None:
    root, source_paths = build_sources(tmp_path)
    before = {path: sha256(path) for path in source_paths}
    output = tmp_path / "audit"

    runtime = run_audit(root, "train", output, pilot=True)

    assert runtime["selected_source_count"] == 3
    assert runtime["error_source_count"] == 0
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert {item["format"] for item in manifest} == {"csv", "xlsx", "sqlite"}
    tables = [json.loads(line) for line in (output / "tables.jsonl").read_text(encoding="utf-8").splitlines()]
    assert any(item["format"] == "xlsx" and item["formula_present"] for item in tables)
    assert any(item["format"] == "xlsx" and item["hidden"] for item in tables)
    sales = next(item for item in tables if item["format"] == "xlsx" and item["table"] == "Sales")
    assert sales["header_row"] == 4
    assert sales["column_count"] == 3
    assert any(item["format"] == "sqlite" and item["declared_keys"] for item in tables)
    assert all(sha256(path) == before[path] for path in source_paths)


def test_outputs_are_stably_ordered(tmp_path: Path) -> None:
    root, _ = build_sources(tmp_path)
    output = tmp_path / "audit"
    run_audit(root, "train", output, pilot=True)
    tables = [json.loads(line) for line in (output / "tables.jsonl").read_text(encoding="utf-8").splitlines()]
    ordering = [(item["business_id"], item["relative_path"], item["table"]) for item in tables]
    assert ordering == sorted(ordering)


def test_full_audit_resumes_from_per_source_checkpoints(tmp_path: Path) -> None:
    root, source_paths = build_sources(tmp_path)
    for path in source_paths:
        readme = path.parent / "README.md"
        readme.write_text(f"# Source\n\n## File\n- `{path.name}`\n", encoding="utf-8")
    output = tmp_path / "full_audit"

    first = run_audit(root, "train", output, pilot=False, resume=True, batch_size=2)
    assert first["processed_this_run"] == 2
    assert first["pending_source_count"] == 4

    second = run_audit(root, "train", output, pilot=False, resume=True, batch_size=10)
    assert second["processed_this_run"] == 4
    assert second["pending_source_count"] == 0
    assert second["error_source_count"] == 0
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest) == 6
    assert {item["status"] for item in manifest} == {"success"}
    assert (output / "readme_mismatches.csv").exists()
    assert (output / "audit_summary.md").exists()


def test_coverage_and_join_analysis_uses_measured_values(tmp_path: Path) -> None:
    root, source_paths = build_sources(tmp_path)
    for path in source_paths:
        (path.parent / "README.md").write_text(
            f"# Source\n\n## File\n- `{path.name}`\n", encoding="utf-8"
        )
    output = tmp_path / "full_audit"
    runtime = run_audit(root, "train", output, pilot=False, resume=True, batch_size=20)
    assert runtime["pending_source_count"] == 0

    summary = analyze_split("train", output)

    assert summary["date_coverage_count"] >= 1
    joins = list(csv.DictReader((output / "join_candidates.csv").open(encoding="utf-8")))
    measured = [row for row in joins if row["column"] == "order_id"]
    assert measured
    assert measured[0]["relationship"] in {
        "one_to_many_candidate",
        "many_to_one_candidate",
    }
    assert measured[0]["evidence"] == "measured frequencies; no full N:M join executed"

    capabilities = list(
        csv.DictReader((output / "capability_matrix.csv").open(encoding="utf-8"))
    )
    generic_sales = next(
        row
        for row in capabilities
        if row["business_id"] == "biz_csv"
        and row["capability"] == "industry_specific"
    )
    assert generic_sales["status"] == "unknown"
