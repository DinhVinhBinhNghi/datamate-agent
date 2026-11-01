from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from openpyxl import load_workbook

from datamate.audit_dataset import (
    detect_csv,
    is_null,
    normalize_header,
    parse_date,
    quote_identifier,
)


VALUE_SAMPLE_LIMIT = 20_000


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fold_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char)).casefold()


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


@dataclass
class ColumnProfile:
    total_rows: int = 0
    null_count: int = 0
    non_null_count: int = 0
    sampled_value_count: int = 0
    values: Counter[str] = field(default_factory=Counter)
    date_parse_count: int = 0
    date_min: datetime | None = None
    date_max: datetime | None = None

    def add(self, value: Any, date_requested: bool) -> None:
        self.total_rows += 1
        if is_null(value):
            self.null_count += 1
            return
        self.non_null_count += 1
        if self.sampled_value_count < VALUE_SAMPLE_LIMIT:
            rendered = str(value).strip()
            self.values[rendered] += 1
            self.sampled_value_count += 1
        if date_requested:
            parsed = parse_date(value)
            if parsed is not None:
                self.date_parse_count += 1
                self.date_min = parsed if self.date_min is None else min(self.date_min, parsed)
                self.date_max = parsed if self.date_max is None else max(self.date_max, parsed)

    def summary(self) -> dict[str, Any]:
        unique = len(self.values)
        return {
            "row_count_scanned": self.total_rows,
            "null_count": self.null_count,
            "non_null_count": self.non_null_count,
            "null_rate": round(self.null_count / self.total_rows, 6) if self.total_rows else None,
            "sampled_value_count": self.sampled_value_count,
            "distinct_sample": unique,
            "uniqueness_sample": round(unique / self.sampled_value_count, 6)
            if self.sampled_value_count
            else None,
            "values_truncated": self.non_null_count > self.sampled_value_count,
            "date_parse_count": self.date_parse_count,
            "date_parse_rate": round(self.date_parse_count / self.non_null_count, 6)
            if self.non_null_count
            else 0.0,
            "date_min": self.date_min.isoformat() if self.date_min else None,
            "date_max": self.date_max.isoformat() if self.date_max else None,
        }


def candidate_key_columns(table: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for candidate in table.get("candidate_keys") or []:
        for column in candidate.get("columns") or []:
            result.add(normalize_header(column))
    for column in table.get("declared_keys") or []:
        result.add(normalize_header(column))
    for raw, normalized in zip(table["headers_raw"], table["headers_normalized"]):
        folded = fold_text(normalized)
        if (
            folded in {"id", "sku", "imei", "ma", "ma_hd", "so_hd"}
            or folded.endswith("_id")
            or folded.startswith("ma_")
            or any(token in folded for token in ("ma_don", "ma_hoa_don", "ma_hang", "ma_khach", "ma_sp"))
        ):
            result.add(normalized)
    return result


def requested_columns(table: dict[str, Any]) -> tuple[set[str], set[str]]:
    dates = {item["normalized_column"] for item in table.get("date_candidates") or []}
    keys = candidate_key_columns(table)
    return dates | keys, dates


def new_profiles(table: dict[str, Any]) -> dict[str, ColumnProfile]:
    requested, _dates = requested_columns(table)
    return {column: ColumnProfile() for column in requested}


def update_profiles(
    table: dict[str, Any],
    profiles: dict[str, ColumnProfile],
    headers: list[Any],
    rows: Iterable[list[Any]],
) -> None:
    normalized = [normalize_header(value) for value in headers]
    indexes = {name: index for index, name in enumerate(normalized) if name in profiles}
    date_columns = requested_columns(table)[1]
    for row in rows:
        for name, profile in profiles.items():
            index = indexes.get(name)
            value = row[index] if index is not None and index < len(row) else None
            profile.add(value, name in date_columns)


def scan_csv(table: dict[str, Any], profiles: dict[str, ColumnProfile]) -> None:
    path = Path(table["raw_path"])
    encoding, delimiter, _bom = detect_csv(path)
    with path.open("r", encoding=encoding, errors="strict", newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        headers = next(reader, [])
        update_profiles(table, profiles, headers, reader)


def excel_header_and_rows(worksheet: Any) -> tuple[list[Any], Iterable[list[Any]]]:
    iterator = enumerate(worksheet.iter_rows(values_only=True), 1)
    preview: list[tuple[int, list[Any]]] = []
    for _ in range(20):
        try:
            row_number, values = next(iterator)
        except StopIteration:
            break
        preview.append((row_number, list(values)))
    candidates = [
        (sum(not is_null(value) for value in values), -row_number, row_number, values)
        for row_number, values in preview
        if any(not is_null(value) for value in values)
    ]
    if not candidates:
        return [], iter(())
    _width, _negative, header_row, headers = max(candidates)
    while headers and is_null(headers[-1]):
        headers.pop()

    def rows() -> Iterable[list[Any]]:
        for row_number, values in preview:
            if row_number > header_row and any(not is_null(value) for value in values):
                yield values
        for row_number, values in iterator:
            values_list = list(values)
            if row_number > header_row and any(not is_null(value) for value in values_list):
                yield values_list

    return headers, rows()


def scan_xlsx(source_tables: list[dict[str, Any]], profile_map: dict[str, dict[str, ColumnProfile]]) -> None:
    path = Path(source_tables[0]["raw_path"])
    workbook = load_workbook(path, read_only=True, data_only=False)
    try:
        by_sheet = {table["table"]: table for table in source_tables}
        for worksheet in workbook.worksheets:
            table = by_sheet.get(worksheet.title)
            if table is None or not profile_map[table_key(table)]:
                continue
            headers, rows = excel_header_and_rows(worksheet)
            update_profiles(table, profile_map[table_key(table)], headers, rows)
    finally:
        workbook.close()


def scan_sqlite(source_tables: list[dict[str, Any]], profile_map: dict[str, dict[str, ColumnProfile]]) -> None:
    path = Path(source_tables[0]["raw_path"])
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        for table in source_tables:
            profiles = profile_map[table_key(table)]
            if not profiles:
                continue
            header_lookup = {
                normalized: raw
                for raw, normalized in zip(table["headers_raw"], table["headers_normalized"])
            }
            selected = [name for name in profiles if name in header_lookup]
            if not selected:
                continue
            raw_columns = [header_lookup[name] for name in selected]
            query = "SELECT " + ", ".join(quote_identifier(name) for name in raw_columns)
            query += " FROM " + quote_identifier(table["table"])
            rows = (list(row) for row in connection.execute(query))
            update_profiles(table, profiles, raw_columns, rows)
    finally:
        connection.close()


def table_key(table: dict[str, Any]) -> str:
    return f"{table['source_id']}::{table['table']}"


def scan_business_tables(tables: list[dict[str, Any]]) -> dict[str, dict[str, ColumnProfile]]:
    profile_map = {table_key(table): new_profiles(table) for table in tables}
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for table in tables:
        by_source[table["source_id"]].append(table)
    for source_tables in by_source.values():
        fmt = source_tables[0]["format"]
        if fmt == "csv":
            scan_csv(source_tables[0], profile_map[table_key(source_tables[0])])
        elif fmt == "xlsx":
            scan_xlsx(source_tables, profile_map)
        elif fmt == "sqlite":
            scan_sqlite(source_tables, profile_map)
    return profile_map


def date_role(column: str) -> str:
    folded = fold_text(column)
    if any(token in folded for token in ("ngay_ban", "ngay_giao_dich", "thoi_gian", "order_date")):
        return "sales_date_candidate"
    if any(token in folded for token in ("ngay_nhap", "purchase")):
        return "purchase_date_candidate"
    if any(token in folded for token in ("han", "expiry", "het_han")):
        return "expiry_date_candidate"
    return "date_candidate"


def build_date_rows(
    split: str,
    tables: list[dict[str, Any]],
    profiles: dict[str, dict[str, ColumnProfile]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for table in tables:
        date_columns = requested_columns(table)[1]
        header_raw = dict(zip(table["headers_normalized"], table["headers_raw"]))
        for column in sorted(date_columns):
            profile = profiles[table_key(table)].get(column)
            if profile is None:
                continue
            summary = profile.summary()
            severity = "info" if summary["date_parse_rate"] >= 0.8 else "warning"
            rows.append(
                {
                    "split": split,
                    "business_id": table["business_id"],
                    "source_id": table["source_id"],
                    "relative_path": table["relative_path"],
                    "table": table["table"],
                    "column": header_raw.get(column, column),
                    "normalized_column": column,
                    "role": date_role(column),
                    "row_count_scanned": summary["row_count_scanned"],
                    "non_null_count": summary["non_null_count"],
                    "parse_count": summary["date_parse_count"],
                    "parse_rate": summary["date_parse_rate"],
                    "min_date": summary["date_min"],
                    "max_date": summary["date_max"],
                    "coverage_scope": "full_scan",
                    "severity": severity,
                    "evidence": "sample candidate confirmed by full column scan",
                }
            )
    return rows


def fragment_family(table: dict[str, Any]) -> str:
    stem = Path(table["relative_path"].replace("\\", "/")).stem
    folded = fold_text(stem)
    folded = re.sub(r"(?:_|-)?(?:t|thang)?\d{1,2}(?:_|-)?20\d{2}$", "", folded)
    folded = re.sub(r"(?:_|-)?20\d{2}$", "", folded)
    folded = re.sub(r"(?:_|-)?\d+$", "", folded)
    sheet = fold_text(table["table"])
    if re.fullmatch(r"(?:t|thang)?\d{1,2}[-_/]20\d{2}", sheet):
        return f"{folded.strip('_-')}::monthly_fragments"
    if table["format"] == "sqlite":
        return f"{table['source_id']}::{sheet}"
    if table["format"] == "xlsx" and table["table"].casefold() not in {"sheet1", stem.casefold()}:
        return f"{table['source_id']}::{sheet}"
    return folded.strip("_-")


def build_fragment_rows(
    split: str,
    tables: list[dict[str, Any]],
    date_rows: list[dict[str, Any]],
    profiles: dict[str, dict[str, ColumnProfile]],
) -> list[dict[str, Any]]:
    date_lookup: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in date_rows:
        date_lookup[f"{row['source_id']}::{row['table']}"].append(row)
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for table in tables:
        groups[fragment_family(table)].append(table)
    output: list[dict[str, Any]] = []
    for family, members in groups.items():
        if len(members) < 2:
            continue
        dated: list[tuple[datetime, datetime, dict[str, Any], dict[str, Any]]] = []
        for member in members:
            candidates = [
                row
                for row in date_lookup.get(table_key(member), [])
                if row["min_date"] and row["max_date"] and row["parse_rate"] >= 0.8
            ]
            if candidates:
                best = max(candidates, key=lambda row: row["parse_count"])
                dated.append(
                    (
                        datetime.fromisoformat(best["min_date"]),
                        datetime.fromisoformat(best["max_date"]),
                        member,
                        best,
                    )
                )
        dated.sort(key=lambda item: (item[0], item[1]))
        if len(dated) < 2:
            output.append(
                {
                    "split": split,
                    "business_id": members[0]["business_id"],
                    "fragment_family": family,
                    "left_fragment": "",
                    "right_fragment": "",
                    "date_column": "",
                    "left_min": "",
                    "left_max": "",
                    "right_min": "",
                    "right_max": "",
                    "gap_days": "",
                    "overlap_days": "",
                    "key_column": "",
                    "key_overlap_count_sample": "",
                    "scope": "insufficient_date_evidence",
                    "severity": "info",
                    "evidence": "filename/sheet pattern only; no fragmentation conclusion",
                }
            )
            continue
        for left, right in zip(dated, dated[1:]):
            left_min, left_max, left_table, left_date = left
            right_min, right_max, right_table, right_date = right
            gap = max(0, (right_min.date() - left_max.date()).days - 1)
            overlap = max(0, (min(left_max, right_max).date() - max(left_min, right_min).date()).days + 1)
            common_keys = sorted(
                set(profiles[table_key(left_table)]) & set(profiles[table_key(right_table)])
            )
            key_column = common_keys[0] if common_keys else ""
            key_overlap: int | str = ""
            scope = "full_date_scan"
            if key_column:
                left_values = set(profiles[table_key(left_table)][key_column].values)
                right_values = set(profiles[table_key(right_table)][key_column].values)
                key_overlap = len(left_values & right_values)
                if (
                    profiles[table_key(left_table)][key_column].non_null_count > VALUE_SAMPLE_LIMIT
                    or profiles[table_key(right_table)][key_column].non_null_count > VALUE_SAMPLE_LIMIT
                ):
                    scope += "+first_20000_key_values"
                else:
                    scope += "+full_key_values"
            severity = "warning" if overlap > 0 else "info"
            output.append(
                {
                    "split": split,
                    "business_id": left_table["business_id"],
                    "fragment_family": family,
                    "left_fragment": f"{left_table['relative_path']}::{left_table['table']}",
                    "right_fragment": f"{right_table['relative_path']}::{right_table['table']}",
                    "date_column": left_date["normalized_column"],
                    "left_min": left_date["min_date"],
                    "left_max": left_date["max_date"],
                    "right_min": right_date["min_date"],
                    "right_max": right_date["max_date"],
                    "gap_days": gap,
                    "overlap_days": overlap,
                    "key_column": key_column,
                    "key_overlap_count_sample": key_overlap,
                    "scope": scope,
                    "severity": severity,
                    "evidence": "measured date ranges; key overlap is measured only when a common profiled column exists",
                }
            )
    return output


def build_join_rows(
    split: str,
    tables: list[dict[str, Any]],
    profiles: dict[str, dict[str, ColumnProfile]],
) -> list[dict[str, Any]]:
    def canonical_join_key(table: dict[str, Any], column: str) -> str:
        folded = fold_text(column)
        aliases = {
            "ma_don": "order_id",
            "ma_don_hang": "order_id",
            "ma_hoa_don": "order_id",
            "ma_hd": "order_id",
            "so_hd": "order_id",
            "ma_hang": "product_id",
            "ma_sp": "product_id",
            "sku": "product_id",
            "ma_kh": "customer_id",
            "ma_khach": "customer_id",
            "ma_khach_hang": "customer_id",
            "ma_ncc": "supplier_id",
        }
        if folded in aliases:
            return aliases[folded]
        if folded == "id":
            table_name = fold_text(normalize_header(table["table"]))
            if table_name.endswith("s"):
                table_name = table_name[:-1]
            return f"{table_name}_id"
        return folded

    by_column: dict[str, list[tuple[dict[str, Any], str]]] = defaultdict(list)
    for table in tables:
        for column, profile in profiles[table_key(table)].items():
            if column in candidate_key_columns(table) and profile.sampled_value_count >= 10:
                by_column[canonical_join_key(table, column)].append((table, column))
    rows: list[dict[str, Any]] = []
    for canonical_column, members in by_column.items():
        for left_index, (left, left_column) in enumerate(members):
            for right, right_column in members[left_index + 1 :]:
                if table_key(left) == table_key(right):
                    continue
                if fragment_family(left) == fragment_family(right):
                    continue
                left_profile = profiles[table_key(left)][left_column]
                right_profile = profiles[table_key(right)][right_column]
                left_values = left_profile.values
                right_values = right_profile.values
                common = set(left_values) & set(right_values)
                if not common:
                    continue
                left_matched = sum(left_values[value] for value in common)
                right_matched = sum(right_values[value] for value in common)
                join_rows = sum(left_values[value] * right_values[value] for value in common)
                left_match_rate = left_matched / left_profile.sampled_value_count
                right_match_rate = right_matched / right_profile.sampled_value_count
                if max(left_match_rate, right_match_rate) < 0.05:
                    continue
                left_unique = len(left_values) / left_profile.sampled_value_count
                right_unique = len(right_values) / right_profile.sampled_value_count
                if left_unique >= 0.98 and right_unique >= 0.98:
                    relationship = "one_to_one_candidate"
                elif left_unique >= 0.98:
                    relationship = "one_to_many_candidate"
                elif right_unique >= 0.98:
                    relationship = "many_to_one_candidate"
                else:
                    relationship = "many_to_many_risk"
                inflation = join_rows / left_profile.sampled_value_count
                scope = (
                    "full_values"
                    if left_profile.non_null_count == left_profile.sampled_value_count
                    and right_profile.non_null_count == right_profile.sampled_value_count
                    else "first_20000_non_null_values"
                )
                severity = "warning" if relationship == "many_to_many_risk" or inflation > 5 else "info"
                rows.append(
                    {
                        "split": split,
                        "business_id": left["business_id"],
                        "left_source": left["relative_path"],
                        "left_table": left["table"],
                        "right_source": right["relative_path"],
                        "right_table": right["table"],
                        "column": canonical_column,
                        "left_column": left_column,
                        "right_column": right_column,
                        "left_null_rate": left_profile.summary()["null_rate"],
                        "right_null_rate": right_profile.summary()["null_rate"],
                        "left_uniqueness": round(left_unique, 6),
                        "right_uniqueness": round(right_unique, 6),
                        "left_match_rate": round(left_match_rate, 6),
                        "right_match_rate": round(right_match_rate, 6),
                        "join_rows_measured": join_rows,
                        "row_inflation_vs_left": round(inflation, 6),
                        "relationship": relationship,
                        "scope": scope,
                        "severity": severity,
                        "evidence": "measured frequencies; no full N:M join executed",
                    }
                )
    return sorted(rows, key=lambda row: (row["business_id"], row["column"], row["left_table"], row["right_table"]))


CAPABILITY_PATTERNS = {
    "sales_lines": ("chi_tiet_don", "chi_tiet_hoa_don", "so_ban_hang", "so_chi_tiet_ban_hang", "thanh_tien"),
    "orders": ("don_hang", "hoa_don", "ma_don", "ma_hoa_don", "tong_bill"),
    "payments": ("thanh_toan", "phieu_thu", "so_quy", "khach_tra", "da_tra"),
    "products": ("san_pham", "hang_hoa", "danh_muc", "ten_hang", "sku"),
    "units": ("don_vi", "quy_doi", "sl_quy_doi"),
    "purchases": ("nhap_hang", "phieu_nhap", "chi_tiet_nhap"),
    "inventory": ("ton_kho", "the_kho", "ton_cuoi", "ton_thuc"),
    "lots": ("lo_hang", "ban_theo_lo", "chi_tiet_don_lo", "han_dung"),
    "delivery": ("giao_hang", "phieu_giao", "luot_giao", "lan_giao"),
    # Keep this list deliberately specific.  Generic words such as "ban"
    # (sales/table) and "tho" (which also prefixes unrelated Vietnamese
    # words after normalization) make almost every retailer look
    # industry-specific.
    "industry_specific": (
        "thuoc",
        "ban_theo_don",
        "imei",
        "sua_xe",
        "ma_tho",
        "ten_tho",
        "topping",
    ),
}


def build_capability_rows(split: str, tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    businesses = sorted({table["business_id"] for table in tables})
    rows: list[dict[str, Any]] = []
    for business in businesses:
        business_tables = [table for table in tables if table["business_id"] == business]
        evidence_pool: list[str] = []
        for table in business_tables:
            evidence_pool.extend(
                [table["relative_path"], table["table"], *table["headers_raw"]]
            )
        normalized_evidence = [(item, fold_text(normalize_header(item))) for item in evidence_pool]
        for capability, patterns in CAPABILITY_PATTERNS.items():
            evidence = sorted(
                {
                    raw
                    for raw, normalized in normalized_evidence
                    if any(pattern in normalized for pattern in patterns)
                }
            )[:20]
            rows.append(
                {
                    "split": split,
                    "business_id": business,
                    "capability": capability,
                    "status": "candidate" if evidence else "unknown",
                    "evidence_count": len(evidence),
                    "evidence": json.dumps(evidence, ensure_ascii=False),
                    "severity": "info",
                    "note": "Preliminary structural evidence only; semantic correctness deferred to adapters",
                }
            )
    return rows


def analyze_split(split: str, audit_dir: Path, resume: bool = False) -> dict[str, Any]:
    tables = load_jsonl(audit_dir / "tables.jsonl")
    tables_stat = (audit_dir / "tables.jsonl").stat()
    input_fingerprint = {
        "size_bytes": tables_stat.st_size,
        "mtime_ns": tables_stat.st_mtime_ns,
    }
    checkpoint_dir = audit_dir / "analysis_checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    by_business: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for table in tables:
        by_business[table["business_id"]].append(table)
    date_rows: list[dict[str, Any]] = []
    join_rows: list[dict[str, Any]] = []
    fragment_rows: list[dict[str, Any]] = []
    for business, business_tables in sorted(by_business.items()):
        checkpoint_path = checkpoint_dir / f"{business}.json"
        checkpoint: dict[str, Any] | None = None
        if resume and checkpoint_path.exists():
            try:
                candidate = json.loads(checkpoint_path.read_text(encoding="utf-8"))
                if (
                    candidate.get("analysis_version") == 2
                    and candidate.get("input_fingerprint") == input_fingerprint
                ):
                    checkpoint = candidate
            except (OSError, json.JSONDecodeError):
                checkpoint = None
        if checkpoint is None:
            print(f"scan {split}/{business}: {len(business_tables)} tables", flush=True)
            profiles = scan_business_tables(business_tables)
            business_dates = build_date_rows(split, business_tables, profiles)
            business_joins = build_join_rows(split, business_tables, profiles)
            business_fragments = build_fragment_rows(
                split, business_tables, business_dates, profiles
            )
            checkpoint = {
                "analysis_version": 2,
                "input_fingerprint": input_fingerprint,
                "business_id": business,
                "date_rows": business_dates,
                "join_rows": business_joins,
                "fragment_rows": business_fragments,
            }
            temporary = checkpoint_path.with_name(checkpoint_path.name + ".tmp")
            temporary.write_text(
                json.dumps(checkpoint, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            temporary.replace(checkpoint_path)
        else:
            print(f"cached {split}/{business}", flush=True)
        date_rows.extend(checkpoint["date_rows"])
        join_rows.extend(checkpoint["join_rows"])
        fragment_rows.extend(checkpoint["fragment_rows"])
    capability_rows = build_capability_rows(split, tables)
    write_csv(
        audit_dir / "date_coverage.csv",
        date_rows,
        [
            "split", "business_id", "source_id", "relative_path", "table", "column",
            "normalized_column", "role", "row_count_scanned", "non_null_count",
            "parse_count", "parse_rate", "min_date", "max_date", "coverage_scope",
            "severity", "evidence",
        ],
    )
    write_csv(
        audit_dir / "join_candidates.csv",
        join_rows,
        [
            "split", "business_id", "left_source", "left_table", "right_source",
            "right_table", "column", "left_column", "right_column", "left_null_rate", "right_null_rate",
            "left_uniqueness", "right_uniqueness", "left_match_rate", "right_match_rate",
            "join_rows_measured", "row_inflation_vs_left", "relationship", "scope",
            "severity", "evidence",
        ],
    )
    write_csv(
        audit_dir / "fragmentation.csv",
        fragment_rows,
        [
            "split", "business_id", "fragment_family", "left_fragment", "right_fragment",
            "date_column", "left_min", "left_max", "right_min", "right_max", "gap_days",
            "overlap_days", "key_column", "key_overlap_count_sample", "scope", "severity",
            "evidence",
        ],
    )
    write_csv(
        audit_dir / "capability_matrix.csv",
        capability_rows,
        ["split", "business_id", "capability", "status", "evidence_count", "evidence", "severity", "note"],
    )
    summary = {
        "split": split,
        "business_count": len(by_business),
        "table_count": len(tables),
        "date_coverage_count": len(date_rows),
        "date_warning_count": sum(row["severity"] == "warning" for row in date_rows),
        "join_candidate_count": len(join_rows),
        "join_warning_count": sum(row["severity"] == "warning" for row in join_rows),
        "fragment_pair_count": len(fragment_rows),
        "fragment_warning_count": sum(row["severity"] == "warning" for row in fragment_rows),
        "capability_candidate_count": sum(row["status"] == "candidate" for row in capability_rows),
        "capability_unknown_count": sum(row["status"] == "unknown" for row in capability_rows),
    }
    (audit_dir / "coverage_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Coverage, fragmentation and JOIN candidate profiler")
    parser.add_argument("--split", choices=("train", "public_test"), required=True)
    parser.add_argument("--audit-dir", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    summary = analyze_split(args.split, args.audit_dir, resume=args.resume)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
