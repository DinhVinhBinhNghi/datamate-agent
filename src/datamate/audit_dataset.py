from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import platform
import re
import sqlite3
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from zipfile import ZipFile

from openpyxl import load_workbook


STRUCTURED_SUFFIXES = {".csv", ".xlsx", ".sqlite", ".sqlite3", ".db"}
README_SUFFIXES = {".md"}
SAMPLE_LIMIT = 500
DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%Y/%m/%d",
    "%d-%m-%Y",
    "%Y-%m-%d %H:%M:%S",
    "%d/%m/%Y %H:%M:%S",
)


def normalize_header(value: Any) -> str:
    text = unicodedata.normalize("NFKC", "" if value is None else str(value)).strip().lower()
    text = re.sub(r"[^\w]+", "_", text, flags=re.UNICODE).strip("_")
    return text


def source_id(split: str, business_id: str, relative_path: str) -> str:
    raw = f"{split}\0{business_id}\0{relative_path.replace(os.sep, '/')}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def json_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def is_null(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def parse_date(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if not isinstance(value, str):
        return None
    text = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    return None


def observed_type(value: Any) -> str:
    if is_null(value):
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, (datetime, date)):
        return "datetime"
    text = str(value).strip()
    if re.fullmatch(r"[+-]?\d+", text):
        return "integer_text"
    if re.fullmatch(r"[+-]?(?:\d+(?:[.,]\d+)?|[.,]\d+)", text):
        return "number_text"
    if parse_date(text) is not None:
        return "date_text"
    return "string"


def analyze_sample(headers: list[Any], rows: list[list[Any]]) -> dict[str, Any]:
    raw_headers = ["" if item is None else str(item) for item in headers]
    normalized = [normalize_header(item) for item in raw_headers]
    width = len(raw_headers)
    padded = [(row + [None] * width)[:width] for row in rows]
    columns = list(zip(*padded)) if padded and width else [tuple() for _ in raw_headers]

    dtypes: dict[str, list[str]] = {}
    null_rates: dict[str, float | None] = {}
    distinct_counts: dict[str, int] = {}
    date_candidates: list[dict[str, Any]] = []
    key_candidates: list[dict[str, Any]] = []
    enums: list[dict[str, Any]] = []

    for index, values_tuple in enumerate(columns):
        values = list(values_tuple)
        key = normalized[index] or f"column_{index + 1}"
        non_null = [value for value in values if not is_null(value)]
        dtypes[key] = sorted({observed_type(value) for value in values})
        null_rate = (len(values) - len(non_null)) / len(values) if values else None
        null_rates[key] = round(null_rate, 6) if null_rate is not None else None
        rendered = [json.dumps(value, ensure_ascii=False, default=str) for value in non_null]
        distinct = len(set(rendered))
        distinct_counts[key] = distinct

        parsed = [parsed_value for value in non_null if (parsed_value := parse_date(value))]
        parse_rate = len(parsed) / len(non_null) if non_null else 0.0
        if len(parsed) >= 3 and parse_rate >= 0.8:
            date_candidates.append(
                {
                    "column": raw_headers[index],
                    "normalized_column": key,
                    "evidence": "sample_parse_rate",
                    "parse_rate": round(parse_rate, 6),
                    "sample_min": min(parsed).isoformat(),
                    "sample_max": max(parsed).isoformat(),
                    "coverage_scope": "sample_only",
                }
            )

        unique_rate = distinct / len(non_null) if non_null else 0.0
        if len(non_null) >= 20 and null_rate == 0 and unique_rate == 1.0:
            key_candidates.append(
                {
                    "columns": [raw_headers[index]],
                    "status": "candidate",
                    "evidence": "sample_non_null_unique",
                    "sample_rows": len(non_null),
                    "sample_unique_rate": 1.0,
                }
            )

        if non_null and distinct <= 20 and distinct / len(non_null) <= 0.2:
            counter = Counter(str(value) for value in non_null)
            role = "low_cardinality"
            if any(token in key for token in ("status", "trang_thai", "tinh_trang")):
                role = "status_candidate"
            elif any(token in key for token in ("unit", "don_vi", "dvt")):
                role = "unit_candidate"
            enums.append(
                {
                    "column": raw_headers[index],
                    "role": role,
                    "evidence": "sample_low_cardinality",
                    "values": dict(counter.most_common(20)),
                }
            )

    return {
        "headers_raw": raw_headers,
        "headers_normalized": normalized,
        "observed_dtypes": dtypes,
        "null_rate_sample": null_rates,
        "distinct_count_sample": distinct_counts,
        "sample_row_count": len(rows),
        "sample_hash": json_hash({"headers": raw_headers, "rows": padded}),
        "date_candidates": date_candidates,
        "candidate_keys": key_candidates,
        "enum_status_unit_candidates": enums,
    }


def detect_csv(path: Path) -> tuple[str, str, bool]:
    raw = path.read_bytes()[:131072]
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    last_error: UnicodeDecodeError | None = None
    encoding = ""
    text = ""
    for candidate in ("utf-8-sig", "utf-8", "cp1258", "cp1252"):
        try:
            text = raw.decode(candidate, errors="strict")
            encoding = candidate
            break
        except UnicodeDecodeError as exc:
            last_error = exc
    if not encoding:
        raise UnicodeError(f"No strict encoding candidate succeeded: {last_error}")
    try:
        dialect = csv.Sniffer().sniff(text, delimiters=",;\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","
    return encoding, delimiter, has_bom


def base_table_record(context: dict[str, Any], table: str) -> dict[str, Any]:
    return {
        **context,
        "table": table,
        "status": "success",
        "severity": "info",
        "error": None,
        "header_row": None,
        "row_count": None,
        "column_count": None,
        "headers_raw": [],
        "headers_normalized": [],
        "observed_dtypes": {},
        "null_rate_sample": {},
        "distinct_count_sample": {},
        "sample_row_count": 0,
        "sample_hash": None,
        "date_candidates": [],
        "candidate_keys": [],
        "declared_keys": [],
        "enum_status_unit_candidates": [],
        "formula_present": False,
        "formula_count": 0,
        "cached_formula_value_count": 0,
        "merged_present": False,
        "merged_range_count": 0,
        "hidden": False,
        "row_width_mismatch_count": 0,
        "elapsed_seconds": None,
        "notes": [],
    }


def audit_csv(path: Path, context: dict[str, Any]) -> list[dict[str, Any]]:
    started = time.perf_counter()
    encoding, delimiter, has_bom = detect_csv(path)
    headers: list[Any] = []
    sample: list[list[Any]] = []
    row_count = 0
    width_mismatches = 0
    with path.open("r", encoding=encoding, errors="strict", newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        try:
            headers = next(reader)
        except StopIteration:
            headers = []
        for row in reader:
            row_count += 1
            if len(row) != len(headers):
                width_mismatches += 1
            if len(sample) < SAMPLE_LIMIT:
                sample.append(row)
    record = base_table_record(context, path.stem)
    record.update(analyze_sample(headers, sample))
    record.update(
        {
            "header_row": 1 if headers else None,
            "row_count": row_count,
            "column_count": len(headers),
            "encoding": encoding,
            "bom_present": has_bom,
            "delimiter": delimiter,
            "row_width_mismatch_count": width_mismatches,
            "elapsed_seconds": round(time.perf_counter() - started, 6),
        }
    )
    if width_mismatches:
        record["severity"] = "warning"
        record["notes"].append("CSV rows with width different from header")
    return [record]


def xlsx_xml_flags(path: Path, worksheet_path: str | None) -> dict[str, int]:
    result = {"formula_count": 0, "cached_formula_value_count": 0, "merged_range_count": 0}
    if not worksheet_path:
        return result
    member = worksheet_path.lstrip("/")
    if not member.startswith("xl/"):
        member = f"xl/{member}"
    with ZipFile(path) as archive:
        with archive.open(member) as stream:
            for _event, element in ET.iterparse(stream, events=("end",)):
                tag = element.tag.rsplit("}", 1)[-1]
                if tag == "c":
                    children = {child.tag.rsplit("}", 1)[-1]: child for child in element}
                    if "f" in children:
                        result["formula_count"] += 1
                        value_node = children.get("v")
                        if value_node is not None and value_node.text not in (None, ""):
                            result["cached_formula_value_count"] += 1
                elif tag == "mergeCell":
                    result["merged_range_count"] += 1
                element.clear()
    return result


def audit_xlsx(path: Path, context: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    workbook = load_workbook(path, read_only=True, data_only=False)
    try:
        for worksheet in workbook.worksheets:
            started = time.perf_counter()
            record = base_table_record(context, worksheet.title)
            header_values: list[Any] = []
            header_row: int | None = None
            sample: list[list[Any]] = []
            data_rows = 0
            width_mismatches = 0

            row_iterator = enumerate(worksheet.iter_rows(), 1)
            preview: list[tuple[int, list[Any]]] = []
            for _ in range(20):
                try:
                    row_number, cells = next(row_iterator)
                except StopIteration:
                    break
                preview.append((row_number, [cell.value for cell in cells]))

            header_candidates = [
                (sum(not is_null(value) for value in values), -row_number, row_number, values)
                for row_number, values in preview
                if any(not is_null(value) for value in values)
            ]
            if header_candidates:
                _width, _negative_row, header_row, header_values = max(header_candidates)
                while header_values and is_null(header_values[-1]):
                    header_values.pop()

            def consume(row_number: int, values: list[Any]) -> None:
                nonlocal data_rows, width_mismatches
                if header_row is None or row_number <= header_row:
                    return
                if not any(not is_null(value) for value in values):
                    return
                data_rows += 1
                if len(values) != len(header_values):
                    width_mismatches += 1
                if len(sample) < SAMPLE_LIMIT:
                    sample.append(values)

            for row_number, values in preview:
                consume(row_number, values)
            for row_number, cells in row_iterator:
                consume(row_number, [cell.value for cell in cells])

            xml_flags = xlsx_xml_flags(path, getattr(worksheet, "_worksheet_path", None))
            record.update(analyze_sample(header_values, sample))
            record.update(
                {
                    "header_row": header_row,
                    "row_count": data_rows,
                    "column_count": len(header_values),
                    "hidden": worksheet.sheet_state != "visible",
                    "row_width_mismatch_count": width_mismatches,
                    "formula_present": xml_flags["formula_count"] > 0,
                    "merged_present": xml_flags["merged_range_count"] > 0,
                    **xml_flags,
                    "elapsed_seconds": round(time.perf_counter() - started, 6),
                }
            )
            record["notes"].append("header candidate = widest non-empty row among first 20 rows")
            if header_row is None:
                record["severity"] = "warning"
                record["notes"].append("No non-empty header found in first 20 rows")
            records.append(record)
    finally:
        workbook.close()
    return records


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def audit_sqlite(path: Path, context: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        for table in tables:
            started = time.perf_counter()
            quoted = quote_identifier(table)
            columns = list(connection.execute(f"PRAGMA table_info({quoted})"))
            headers = [column[1] for column in columns]
            declared_types = {column[1]: column[2] for column in columns}
            declared_keys = [column[1] for column in columns if column[5]]
            indexes = [dict(zip(("seq", "name", "unique", "origin", "partial"), row)) for row in connection.execute(f"PRAGMA index_list({quoted})")]
            foreign_keys = [list(row) for row in connection.execute(f"PRAGMA foreign_key_list({quoted})")]
            row_count = connection.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0]
            sample_rows = [list(row) for row in connection.execute(f"SELECT * FROM {quoted} LIMIT {SAMPLE_LIMIT}")]
            record = base_table_record(context, table)
            record.update(analyze_sample(headers, sample_rows))
            record.update(
                {
                    "header_row": 0,
                    "row_count": row_count,
                    "column_count": len(headers),
                    "declared_types": declared_types,
                    "declared_keys": declared_keys,
                    "indexes": indexes,
                    "foreign_keys": foreign_keys,
                    "elapsed_seconds": round(time.perf_counter() - started, 6),
                }
            )
            records.append(record)
    finally:
        connection.close()
    return records


def read_text_strict(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    last_error: UnicodeDecodeError | None = None
    for encoding in ("utf-8-sig", "utf-8", "cp1258", "cp1252"):
        try:
            return raw.decode(encoding, errors="strict"), encoding
        except UnicodeDecodeError as exc:
            last_error = exc
    raise UnicodeError(f"No strict encoding candidate succeeded: {last_error}")


def parse_readme(path: Path, context: dict[str, Any]) -> dict[str, Any]:
    text, encoding = read_text_strict(path)
    file_claims: list[dict[str, Any]] = []
    column_claims: list[dict[str, Any]] = []
    semantic_claims: list[dict[str, Any]] = []
    current_file: str | None = None
    current_sheet: str | None = None
    file_pattern = re.compile(r"`([^`]+\.(?:csv|xlsx|sqlite|sqlite3|db))`", re.IGNORECASE)
    heading_pattern = re.compile(
        r"^##\s+Cột\s+trong\s+`([^`]+)`(?:\s*,\s*sheet\s+`([^`]+)`)?",
        re.IGNORECASE,
    )
    bold_column_pattern = re.compile(r"^\s*-\s*\*\*([^*]+)\*\*")
    seen_files: set[str] = set()

    for line_number, line in enumerate(text.splitlines(), 1):
        heading = heading_pattern.search(line)
        if heading:
            current_file = heading.group(1).strip()
            current_sheet = heading.group(2).strip() if heading.group(2) else None
        elif re.match(r"^##\s+", line):
            current_file = None
            current_sheet = None
        for match in file_pattern.finditer(line):
            claimed = match.group(1).strip()
            key = unicodedata.normalize("NFKC", claimed).casefold()
            if key not in seen_files:
                file_claims.append(
                    {"name": claimed, "line": line_number, "evidence": line.strip()}
                )
                seen_files.add(key)
        column = bold_column_pattern.search(line)
        if column and current_file:
            column_claims.append(
                {
                    "file": current_file,
                    "sheet": current_sheet,
                    "column": column.group(1).strip(),
                    "line": line_number,
                    "evidence": line.strip(),
                }
            )
        normalized_line = unicodedata.normalize("NFKC", line).casefold()
        if any(token in normalized_line for token in ("mỗi dòng", "nối ", "khóa", "khoá", "không trùng")):
            semantic_claims.append(
                {"line": line_number, "evidence": line.strip(), "status": "requires_validation"}
            )

    return {
        **context,
        "parser_version": 2,
        "encoding": encoding,
        "file_claims": file_claims,
        "column_claims": column_claims,
        "semantic_claims": semantic_claims,
        "sample_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


def discover_all_files(root: Path) -> list[tuple[str, Path]]:
    data_root = root / "data"
    discovered: list[tuple[str, Path]] = []
    for business_dir in sorted(path for path in data_root.iterdir() if path.is_dir()):
        for path in sorted(business_dir.rglob("*")):
            if path.is_file():
                discovered.append((business_dir.name, path))
    return discovered


def discover_sources(root: Path) -> list[tuple[str, Path]]:
    return [item for item in discover_all_files(root) if item[1].suffix.lower() in STRUCTURED_SUFFIXES]


def workbook_sheet_count(path: Path) -> int:
    try:
        with ZipFile(path) as archive:
            with archive.open("xl/workbook.xml") as stream:
                return sum(
                    1
                    for _event, element in ET.iterparse(stream, events=("end",))
                    if element.tag.rsplit("}", 1)[-1] == "sheet"
                )
    except Exception:
        return -1


def select_pilot(sources: list[tuple[str, Path]]) -> list[tuple[str, Path]]:
    csv_sources = [item for item in sources if item[1].suffix.lower() == ".csv"]
    xlsx_sources = [item for item in sources if item[1].suffix.lower() == ".xlsx"]
    sqlite_sources = [item for item in sources if item[1].suffix.lower() in {".sqlite", ".sqlite3", ".db"}]
    selected: list[tuple[str, Path]] = []
    if csv_sources:
        representative = [
            item
            for item in csv_sources
            if item[0] == "biz_110" and item[1].name.casefold() == "danh_sach_hoa_don.csv"
        ]
        selected.append(
            representative[0]
            if representative
            else min(csv_sources, key=lambda item: (item[1].stat().st_size, str(item[1])))
        )
    if xlsx_sources:
        selected.append(max(xlsx_sources, key=lambda item: (workbook_sheet_count(item[1]), -item[1].stat().st_size, str(item[1]))))
    if sqlite_sources:
        selected.append(min(sqlite_sources, key=lambda item: str(item[1])))
    return selected


def file_format(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return "csv"
    if suffix == ".xlsx":
        return "xlsx"
    if suffix in {".sqlite", ".sqlite3", ".db"}:
        return "sqlite"
    if suffix == ".md":
        return "markdown"
    return suffix.lstrip(".") or "unknown"


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    text = "".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True, default=str) + "\n"
        for record in records
    )
    atomic_write_text(path, text)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(path)


def source_context(root: Path, split: str, business_id: str, path: Path) -> dict[str, Any]:
    relative = str(path.relative_to(root))
    return {
        "split": split,
        "business_id": business_id,
        "raw_path": str(path),
        "relative_path": relative,
        "source_id": source_id(split, business_id, relative),
        "format": file_format(path),
    }


def source_fingerprint(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {"size_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def audit_one_file(root: Path, split: str, business_id: str, path: Path) -> dict[str, Any]:
    context = source_context(root, split, business_id, path)
    fingerprint = source_fingerprint(path)
    started = time.perf_counter()
    file_record = {
        **context,
        **fingerprint,
        "status": "success",
        "severity": "info",
        "error": None,
        "table_count": 0,
        "elapsed_seconds": None,
    }
    tables: list[dict[str, Any]] = []
    readme_claims: dict[str, Any] | None = None
    try:
        if context["format"] == "csv":
            tables = audit_csv(path, context)
        elif context["format"] == "xlsx":
            tables = audit_xlsx(path, context)
        elif context["format"] == "sqlite":
            tables = audit_sqlite(path, context)
        elif context["format"] == "markdown":
            readme_claims = parse_readme(path, context)
        else:
            file_record["status"] = "unsupported"
            file_record["severity"] = "info"
            file_record["error"] = {
                "type": "UnsupportedFormat",
                "message": f"No auditor registered for suffix {path.suffix}",
            }
        file_record["table_count"] = len(tables)
        if any(record["severity"] == "warning" for record in tables):
            file_record["severity"] = "warning"
    except Exception as exc:
        file_record.update(
            {
                "status": "error",
                "severity": "fatal",
                "error": {"type": type(exc).__name__, "message": str(exc)},
            }
        )
    file_record["elapsed_seconds"] = round(time.perf_counter() - started, 6)
    return {
        "checkpoint_version": 1,
        "fingerprint": fingerprint,
        "file": file_record,
        "tables": tables,
        "readme_claims": readme_claims,
    }


def checkpoint_path(output_dir: Path, context: dict[str, Any]) -> Path:
    return output_dir / "checkpoints" / f"{context['source_id']}.json"


def load_valid_checkpoint(path: Path, fingerprint: dict[str, Any]) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if payload.get("checkpoint_version") != 1 or payload.get("fingerprint") != fingerprint:
        return None
    if (
        payload.get("file", {}).get("format") == "markdown"
        and payload.get("readme_claims", {}).get("parser_version") != 2
    ):
        return None
    return payload


def write_checkpoint(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str))


def peak_rss_mb() -> tuple[float | None, str]:
    """Return process peak RSS without instrumenting every Python allocation."""
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            class ProcessMemoryCounters(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            counters = ProcessMemoryCounters()
            counters.cb = ctypes.sizeof(counters)
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            psapi = ctypes.WinDLL("psapi", use_last_error=True)
            get_current_process = kernel32.GetCurrentProcess
            get_current_process.restype = wintypes.HANDLE
            get_memory_info = psapi.GetProcessMemoryInfo
            get_memory_info.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(ProcessMemoryCounters),
                wintypes.DWORD,
            ]
            get_memory_info.restype = wintypes.BOOL
            ok = get_memory_info(
                get_current_process(), ctypes.byref(counters), counters.cb
            )
            if ok:
                return round(counters.PeakWorkingSetSize / (1024 * 1024), 3), "Windows PeakWorkingSetSize"
        except Exception:
            pass
        return None, "unavailable_on_windows"
    try:
        import resource

        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        divisor = 1024 if sys.platform != "darwin" else 1024 * 1024
        return round(value / divisor, 3), "resource.ru_maxrss"
    except Exception:
        return None, "unavailable"


def normalized_name(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold().strip()


def readme_filename_matches(claimed: str, actual: str) -> bool:
    claim = normalized_name(basename_any(claimed))
    candidate = normalized_name(basename_any(actual))
    if "<" not in claim or ">" not in claim:
        return claim == candidate
    pieces = re.split(r"(<[^>]+>)", claim)
    pattern = "".join(r".+" if piece.startswith("<") else re.escape(piece) for piece in pieces)
    return re.fullmatch(pattern, candidate) is not None


def basename_any(value: str) -> str:
    return value.replace("\\", "/").rsplit("/", 1)[-1]


def generate_readme_mismatches(
    manifest: list[dict[str, Any]],
    tables: list[dict[str, Any]],
    readme_claims: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    actual_by_business: dict[str, dict[str, dict[str, Any]]] = {}
    tables_by_source: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in manifest:
        if item["format"] in {"csv", "xlsx", "sqlite"}:
            key = normalized_name(basename_any(item["relative_path"]))
            actual_by_business.setdefault(item["business_id"], {})[key] = item
    for table in tables:
        key = (table["business_id"], normalized_name(basename_any(table["relative_path"])))
        tables_by_source.setdefault(key, []).append(table)

    claims_by_business = {item["business_id"]: item for item in readme_claims}
    for business_id, actual_files in sorted(actual_by_business.items()):
        readme = claims_by_business.get(business_id)
        if not readme:
            mismatches.append(
                {
                    "split": next(iter(actual_files.values()))["split"],
                    "business_id": business_id,
                    "severity": "warning",
                    "mismatch_type": "readme_missing",
                    "claimed": "",
                    "actual": "; ".join(sorted(item["relative_path"] for item in actual_files.values())),
                    "evidence": "No README checkpoint found for business",
                    "readme_path": "",
                }
            )
            continue

        claimed_files = list(readme["file_claims"])
        for claim in sorted(claimed_files, key=lambda item: normalized_name(item["name"])):
            if not any(readme_filename_matches(claim["name"], item["relative_path"]) for item in actual_files.values()):
                mismatches.append(
                    {
                        "split": readme["split"],
                        "business_id": business_id,
                        "severity": "warning",
                        "mismatch_type": "readme_file_missing_from_data",
                        "claimed": claim["name"],
                        "actual": "",
                        "evidence": f"README line {claim['line']}: {claim['evidence']}",
                        "readme_path": readme["relative_path"],
                    }
                )
        for key, actual in sorted(actual_files.items()):
            if not any(readme_filename_matches(claim["name"], actual["relative_path"]) for claim in claimed_files):
                mismatches.append(
                    {
                        "split": readme["split"],
                        "business_id": business_id,
                        "severity": "info",
                        "mismatch_type": "data_file_not_documented",
                        "claimed": "",
                        "actual": actual["relative_path"],
                        "evidence": "Structured source exists but filename was not found in README backticks",
                        "readme_path": readme["relative_path"],
                    }
                )

        column_claims_by_file: dict[str, list[dict[str, Any]]] = {}
        for claim in readme["column_claims"]:
            key = normalized_name(basename_any(claim["file"]))
            column_claims_by_file.setdefault(key, []).append(claim)
        for file_key, claims in column_claims_by_file.items():
            matching_keys = [
                key
                for key, actual in actual_files.items()
                if readme_filename_matches(claims[0]["file"], actual["relative_path"])
            ]
            source_tables = [
                table
                for key in matching_keys
                for table in tables_by_source.get((business_id, key), [])
            ]
            if not source_tables:
                continue
            for claim in claims:
                target_tables = source_tables
                if claim["sheet"]:
                    target_tables = [
                        table
                        for table in source_tables
                        if normalized_name(table["table"]) == normalized_name(claim["sheet"])
                    ]
                    if not target_tables:
                        mismatches.append(
                            {
                                "split": readme["split"],
                                "business_id": business_id,
                                "severity": "warning",
                                "mismatch_type": "readme_sheet_missing_from_workbook",
                                "claimed": claim["sheet"],
                                "actual": "; ".join(table["table"] for table in source_tables),
                                "evidence": f"README line {claim['line']}: {claim['evidence']}",
                                "readme_path": readme["relative_path"],
                            }
                        )
                        continue
                present_in = [
                    table["table"]
                    for table in target_tables
                    if normalize_header(claim["column"]) in table["headers_normalized"]
                ]
                if not present_in:
                    mismatches.append(
                        {
                            "split": readme["split"],
                            "business_id": business_id,
                            "severity": "warning",
                            "mismatch_type": "readme_column_missing_from_data",
                            "claimed": claim["column"],
                            "actual": "; ".join(table["table"] for table in target_tables),
                            "evidence": f"README line {claim['line']}: {claim['evidence']}",
                            "readme_path": readme["relative_path"],
                        }
                    )
        for claim in readme["semantic_claims"]:
            mismatches.append(
                {
                    "split": readme["split"],
                    "business_id": business_id,
                    "severity": "info",
                    "mismatch_type": "semantic_claim_requires_group3_validation",
                    "claimed": claim["evidence"],
                    "actual": "candidate",
                    "evidence": f"README line {claim['line']}; no JOIN/key/grain conclusion made in file audit",
                    "readme_path": readme["relative_path"],
                }
            )
    return sorted(
        mismatches,
        key=lambda item: (item["business_id"], item["mismatch_type"], item["claimed"], item["actual"]),
    )


def write_mismatch_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "split",
        "business_id",
        "severity",
        "mismatch_type",
        "claimed",
        "actual",
        "evidence",
        "readme_path",
    ]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    atomic_write_text(path, buffer.getvalue())


def write_audit_summary(
    path: Path,
    split: str,
    manifest: list[dict[str, Any]],
    tables: list[dict[str, Any]],
    mismatches: list[dict[str, Any]],
) -> None:
    status_counts = Counter(item["status"] for item in manifest)
    format_counts = Counter(item["format"] for item in manifest)
    severity_counts = Counter(item["severity"] for item in manifest)
    businesses = sorted({item["business_id"] for item in manifest})
    lines = [
        f"# Audit summary — {split}",
        "",
        f"- Businesses discovered: {len(businesses)}",
        f"- Source records: {len(manifest)}",
        f"- Table records: {len(tables)}",
        f"- Status counts: {dict(sorted(status_counts.items()))}",
        f"- Format counts: {dict(sorted(format_counts.items()))}",
        f"- Severity counts: {dict(sorted(severity_counts.items()))}",
        f"- README mismatch records: {len(mismatches)}",
        "",
        "Candidate labels are sample evidence only. Date coverage, key uniqueness, grain and JOIN validity are deferred to Group 3.",
    ]
    atomic_write_text(path, "\n".join(lines) + "\n")


def update_global_runtime(path: Path | None, run: dict[str, Any]) -> None:
    if path is None:
        return
    payload: dict[str, Any] = {"runs": []}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(existing, dict) and isinstance(existing.get("runs"), list):
                payload = existing
        except (OSError, json.JSONDecodeError):
            pass
    payload["runs"].append(run)
    payload["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def aggregate_full_outputs(
    root: Path,
    split: str,
    output_dir: Path,
    all_files: list[tuple[str, Path]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], int]:
    manifest: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    pending = 0
    for business_id, path in all_files:
        context = source_context(root, split, business_id, path)
        checkpoint = load_valid_checkpoint(
            checkpoint_path(output_dir, context), source_fingerprint(path)
        )
        if checkpoint is None:
            pending += 1
            manifest.append(
                {
                    **context,
                    **source_fingerprint(path),
                    "status": "pending",
                    "severity": "info",
                    "error": None,
                    "table_count": 0,
                    "elapsed_seconds": None,
                }
            )
            continue
        manifest.append(checkpoint["file"])
        tables.extend(checkpoint.get("tables") or [])
        if checkpoint.get("readme_claims"):
            claims.append(checkpoint["readme_claims"])
    manifest.sort(key=lambda item: (item["business_id"], item["relative_path"]))
    tables.sort(key=lambda item: (item["business_id"], item["relative_path"], item["table"]))
    claims.sort(key=lambda item: (item["business_id"], item["relative_path"]))
    mismatches = generate_readme_mismatches(manifest, tables, claims)
    atomic_write_text(
        output_dir / "manifest.json",
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True, default=str),
    )
    write_jsonl(output_dir / "tables.jsonl", tables)
    write_jsonl(output_dir / "readme_claims.jsonl", claims)
    write_mismatch_csv(output_dir / "readme_mismatches.csv", mismatches)
    write_audit_summary(output_dir / "audit_summary.md", split, manifest, tables, mismatches)
    return manifest, tables, mismatches, pending


def run_audit(
    root: Path,
    split: str,
    output_dir: Path,
    pilot: bool,
    resume: bool = False,
    batch_size: int | None = None,
    global_runtime_path: Path | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)
    all_structured = discover_sources(root)
    chosen = select_pilot(all_structured) if pilot else discover_all_files(root)
    manifest_records: list[dict[str, Any]] = []
    table_records: list[dict[str, Any]] = []

    processed_this_run = 0
    cached_before_run = 0
    if pilot:
        for business_id, path in chosen:
            checkpoint = audit_one_file(root, split, business_id, path)
            manifest_records.append(checkpoint["file"])
            table_records.extend(checkpoint["tables"])
            processed_this_run += 1
        pending_count = 0
        mismatches: list[dict[str, Any]] = []
    else:
        checkpoints_dir = output_dir / "checkpoints"
        checkpoints_dir.mkdir(parents=True, exist_ok=True)
        existing_valid: set[str] = set()
        queue: list[tuple[str, Path]] = []
        for business_id, path in chosen:
            context = source_context(root, split, business_id, path)
            cached = load_valid_checkpoint(
                checkpoint_path(output_dir, context), source_fingerprint(path)
            )
            if resume and cached is not None:
                existing_valid.add(context["source_id"])
                continue
            queue.append((business_id, path))
        cached_before_run = len(existing_valid)
        if batch_size is not None:
            queue = queue[:batch_size]
        for index, (business_id, path) in enumerate(queue, 1):
            checkpoint = audit_one_file(root, split, business_id, path)
            context = source_context(root, split, business_id, path)
            write_checkpoint(checkpoint_path(output_dir, context), checkpoint)
            processed_this_run += 1
            print(
                f"[{index}/{len(queue)}] {checkpoint['file']['status']} "
                f"{checkpoint['file']['relative_path']} "
                f"{checkpoint['file']['elapsed_seconds']}s",
                file=sys.stderr,
                flush=True,
            )
        manifest_records, table_records, mismatches, pending_count = aggregate_full_outputs(
            root, split, output_dir, chosen
        )

    peak_memory, memory_method = peak_rss_mb()
    manifest_records.sort(key=lambda item: (item["business_id"], item["relative_path"]))
    table_records.sort(key=lambda item: (item["business_id"], item["relative_path"], item["table"]))
    runtime = {
        "split": split,
        "mode": "pilot" if pilot else "full",
        "discovered_structured_source_count": len(all_structured),
        "discovered_source_count": len(all_structured) if pilot else len(chosen),
        "selected_source_count": len(chosen),
        "success_source_count": sum(item["status"] == "success" for item in manifest_records),
        "error_source_count": sum(item["status"] == "error" for item in manifest_records),
        "unsupported_source_count": sum(item["status"] == "unsupported" for item in manifest_records),
        "pending_source_count": pending_count,
        "processed_this_run": processed_this_run,
        "cached_before_run": cached_before_run,
        "table_record_count": len(table_records),
        "readme_mismatch_count": len(mismatches),
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "peak_process_memory_mb": peak_memory,
        "memory_measurement": memory_method,
        "python": sys.version,
        "platform": platform.platform(),
    }
    if pilot:
        atomic_write_text(
            output_dir / "manifest.json",
            json.dumps(manifest_records, ensure_ascii=False, indent=2, sort_keys=True),
        )
        write_jsonl(output_dir / "tables.jsonl", table_records)
    atomic_write_text(
        output_dir / "runtime_profile.json",
        json.dumps(runtime, ensure_ascii=False, indent=2, sort_keys=True),
    )
    update_global_runtime(global_runtime_path, runtime)
    return runtime


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only structural audit for DataMate sources")
    parser.add_argument("--root", type=Path, required=True, help="Split root containing data/")
    parser.add_argument("--split", choices=("train", "public_test"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--global-runtime", type=Path)
    args = parser.parse_args()
    if args.batch_size is not None and args.batch_size < 1:
        parser.error("--batch-size must be >= 1")
    runtime = run_audit(
        args.root,
        args.split,
        args.output_dir,
        args.pilot,
        resume=args.resume,
        batch_size=args.batch_size,
        global_runtime_path=args.global_runtime,
    )
    print(json.dumps(runtime, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if runtime["error_source_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
