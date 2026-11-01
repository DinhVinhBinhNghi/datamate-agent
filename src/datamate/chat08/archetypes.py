from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from .inventory import write_csv


DATE_WORDS = ("ngày", "date", "thời gian", "time", "tháng", "năm")
STATUS_WORDS = ("trạng thái", "tình trạng", "status", "ghi chú")
AMOUNT_WORDS = ("tiền", "doanh thu", "thành tiền", "tổng", "giá", "amount", "phải thu", "thanh toán")
ORDER_WORDS = ("đơn", "hóa đơn", "hoá đơn", "phiếu", "order", "mahoadon", "số phiếu")
PRODUCT_WORDS = ("hàng", "sản phẩm", "món", "thuốc", "product", "mã hàng", "tên hàng")
CUSTOMER_WORDS = ("khách", "customer", "người mua")

CAPABILITY_CUES = {
    "sales": ("banhang", "bán hàng", "hoa don", "hóa đơn", "doanh thu", "thành tiền", "tổng tiền"),
    "orders/status": ("donhang", "đơn hàng", "hoa don", "hóa đơn", "trạng thái", "tình trạng", "số phiếu"),
    "products/units": ("sanpham", "sản phẩm", "hanghoa", "hàng hóa", "quydoi", "quy đổi", "đơn vị", "tên hàng"),
    "customers": ("khachhang", "khách hàng", "mã khách", "tên khách"),
    "payments/debt": ("thanhtoan", "thanh toán", "phieuthu", "phiếu thu", "công nợ", "dư nợ", "hạn nợ"),
    "inventory/purchases": ("tonkho", "tồn kho", "nhaphang", "nhập hàng", "phiếu nhập", "lô hàng"),
}


VERIFIED = {
    "biz_102": {"sales": "logic_verified+train_exact_29_pool", "orders/status": "logic_verified+train_exact_29_pool"},
    "biz_103": {"sales": "logic_verified+train_exact_29_pool", "orders/status": "logic_verified+train_exact_29_pool"},
    "biz_104": {"sales": "logic_verified+train_exact_29_pool", "orders/status": "logic_verified+train_exact_29_pool"},
    "dev_002": {"sales": "public_enabled_8_direct_revenue", "orders/status": "public_enabled_8_direct_revenue"},
    "biz_129": {"sales": "logic_verified_chat04", "orders/status": "logic_verified_chat04"},
    "biz_123": {"sales": "join_cardinality_verified_chat03", "orders/status": "join_cardinality_verified_chat03"},
    "biz_116": {"sales": "loader_verified_chat03"},
}

GRAIN_VERIFIED = {
    "biz_102": "line grain; Wave1 monthly-sales audit",
    "biz_103": "line grain; Wave1 monthly-sales audit",
    "biz_104": "line grain; Wave1 monthly-sales audit",
    "dev_002": "line grain; Wave1 monthly-sales audit",
    "biz_129": "order header + detail lines; Chat03/04",
    "biz_123": "order header one-to-many detail; Chat03 cardinality proof",
    "biz_116": "sales line grain; Chat03 loader/README",
}


def fold(value: object) -> str:
    text = unicodedata.normalize("NFD", str(value)).replace("đ", "d").replace("Đ", "D")
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn").lower().strip()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def best_header(rows: list[tuple]) -> tuple[int, list[str]]:
    best = (-1, -1, [])
    cues = DATE_WORDS + STATUS_WORDS + AMOUNT_WORDS + ORDER_WORDS + PRODUCT_WORDS + CUSTOMER_WORDS
    for idx, row in enumerate(rows):
        values = [str(v).strip() for v in row if v is not None and str(v).strip()]
        textual = sum(not re.fullmatch(r"[-+]?\d+(?:[.,]\d+)?", v) for v in values)
        cue_score = sum(any(fold(cue) in fold(v) for cue in cues) for v in values)
        score = cue_score * 10 + textual
        if score > best[0]:
            best = (score, idx + 1, values)
    return best[1], best[2]


def scan_xlsx(path: Path) -> list[dict]:
    import openpyxl

    out = []
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        for sheet in book.worksheets:
            rows = []
            for i, row in enumerate(sheet.iter_rows(values_only=True)):
                rows.append(tuple(row))
                if i >= 29:
                    break
            header_row, columns = best_header(rows)
            out.append({
                "source": path.name,
                "table": sheet.title,
                "format": "xlsx",
                "header_row_candidate": header_row,
                "columns": columns,
                "max_row_reported": sheet.max_row,
                "max_column_reported": sheet.max_column,
            })
    finally:
        book.close()
    return out


def scan_csv(path: Path) -> list[dict]:
    raw = path.read_bytes()[:65536]
    text = None
    for encoding in ("utf-8-sig", "utf-8", "cp1258", "latin1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    text = text or raw.decode("latin1", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","
    rows = list(csv.reader(text.splitlines()[:30], delimiter=delimiter))
    header_row, columns = best_header([tuple(r) for r in rows])
    return [{
        "source": path.name,
        "table": path.stem,
        "format": "csv",
        "header_row_candidate": header_row,
        "columns": columns,
        "max_row_reported": "not_scanned",
        "max_column_reported": len(columns),
    }]


def scan_sqlite(path: Path) -> list[dict]:
    uri = f"file:{path.as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        names = [r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        out = []
        for name in names:
            escaped = name.replace("'", "''")
            cols = [r[1] for r in connection.execute(f"PRAGMA table_info('{escaped}')")]
            out.append({
                "source": path.name,
                "table": name,
                "format": "sqlite",
                "header_row_candidate": 0,
                "columns": cols,
                "max_row_reported": "not_scanned",
                "max_column_reported": len(cols),
            })
        return out
    finally:
        connection.close()


def candidate_columns(tables: list[dict], words: tuple[str, ...]) -> list[str]:
    found = []
    for table in tables:
        for col in table["columns"]:
            if any(fold(word) in fold(col) for word in words):
                label = f"{table['source']}::{table['table']}::{col}"
                if label not in found:
                    found.append(label)
    return found


def fragment_pattern(files: list[Path]) -> str:
    groups = defaultdict(list)
    for path in files:
        stem = fold(path.stem)
        normalized = re.sub(r"(?:19|20)\d{2}|(?:thang|t|month)?[_ -]?\d{1,2}|[_ -]?\d+$", "#", stem)
        normalized = re.sub(r"#+", "#", normalized).strip("_ -#")
        groups[normalized].append(path.name)
    repeated = {k: v for k, v in groups.items() if len(v) > 1 and k}
    return json.dumps(repeated, ensure_ascii=False, separators=(",", ":")) if repeated else "none_detected"


def join_candidates(tables: list[dict], business_id: str) -> str:
    by_col = defaultdict(list)
    for table in tables:
        for col in table["columns"]:
            key = fold(col)
            if re.search(r"(^|\s)(ma|so|id)|ma.*(don|hoa|hang|khach)|.*id$", key):
                by_col[key].append(f"{table['source']}::{table['table']}::{col}")
    shared = {k: v for k, v in by_col.items() if len(v) > 1}
    if business_id == "biz_123":
        shared["VERIFIED_CHAT03"] = ["don_hang.MaHoaDon -> chi_tiet_don.MaHoaDon one_to_many; unmatched=0"]
    return json.dumps(shared, ensure_ascii=False, separators=(",", ":")) if shared else "none_detected"


def classify_archetype(formats: set[str], files: list[Path], tables: list[dict]) -> str:
    fragments = fragment_pattern(files) != "none_detected"
    if "sqlite" in formats:
        return "relational_sqlite"
    if formats == {"csv"}:
        return "flat_or_multi_csv"
    if "xlsx" in formats and fragments:
        return "monthly_or_part_fragmented_excel"
    if "xlsx" in formats and len(tables) > len(files):
        return "multi_sheet_excel"
    if "xlsx" in formats:
        return "excel_workbook"
    return "mixed_or_unknown"


def analogue_similarity(public: dict, train: dict) -> float:
    a = set(public["column_tokens"])
    b = set(train["column_tokens"])
    col = len(a & b) / len(a | b) if a | b else 0.0
    fmt = 1.0 if public["format_set"] == train["format_set"] else 0.0
    arch = 1.0 if public["archetype"] == train["archetype"] else 0.0
    return round(0.65 * col + 0.2 * fmt + 0.15 * arch, 4)


def scan_business(split_root: Path, split: str, business_dir: Path, rulebook_hash: str) -> tuple[dict, list[dict], list[dict]]:
    business_id = business_dir.name
    readme = business_dir / "README.md"
    readme_text = readme.read_text(encoding="utf-8-sig", errors="replace") if readme.exists() else ""
    readme_hash = sha256(readme) if readme.exists() else "missing"
    source_files = [p for p in sorted(business_dir.iterdir()) if p.is_file() and p.name != "README.md" and not p.name.startswith(".")]
    tables = []
    errors = []
    for path in source_files:
        try:
            suffix = path.suffix.lower()
            if suffix == ".xlsx":
                tables.extend(scan_xlsx(path))
            elif suffix in {".csv", ".tsv"}:
                tables.extend(scan_csv(path))
            elif suffix in {".sqlite", ".db"}:
                tables.extend(scan_sqlite(path))
            else:
                errors.append(f"unsupported:{path.name}")
        except Exception as exc:  # continue per business/file as requested
            errors.append(f"{path.name}:{type(exc).__name__}:{exc}")

    formats = {t["format"] for t in tables}
    all_columns = [fold(c) for t in tables for c in t["columns"]]
    combined_evidence = fold(" ".join([p.name for p in source_files]) + " " + readme_text + " " + " ".join(all_columns))
    markers = [cue for cue in ("grain", "mỗi dòng", "đơn hàng", "dòng hàng", "quy đổi", "trạng thái", "công nợ", "tồn kho") if fold(cue) in fold(readme_text)]
    grain = GRAIN_VERIFIED.get(business_id, "candidate_from_README/header_only")
    if business_id not in GRAIN_VERIFIED:
        if "moi dong" in fold(readme_text):
            grain += "; README mentions mỗi dòng"
        elif "don hang" in fold(readme_text):
            grain += "; README mentions đơn hàng"

    matrix = {
        "split": split,
        "business_id": business_id,
        "format_archetype": classify_archetype(formats, source_files, tables),
        "formats": "|".join(sorted(formats)) or "unknown",
        "file_sheet_table": json.dumps([f"{t['source']}::{t['table']}" for t in tables], ensure_ascii=False),
        "source_file_count": len(source_files),
        "table_count": len(tables),
        "grain_candidate_or_verified": grain,
        "date_candidates": json.dumps(candidate_columns(tables, DATE_WORDS), ensure_ascii=False),
        "status_candidates": json.dumps(candidate_columns(tables, STATUS_WORDS), ensure_ascii=False),
        "amount_candidates": json.dumps(candidate_columns(tables, AMOUNT_WORDS), ensure_ascii=False),
        "order_candidates": json.dumps(candidate_columns(tables, ORDER_WORDS), ensure_ascii=False),
        "product_candidates": json.dumps(candidate_columns(tables, PRODUCT_WORDS), ensure_ascii=False),
        "customer_candidates": json.dumps(candidate_columns(tables, CUSTOMER_WORDS), ensure_ascii=False),
        "fragment_pattern": fragment_pattern(source_files),
        "join_candidates": join_candidates(tables, business_id),
        "unit_conversion": "candidate" if any(cue in combined_evidence for cue in ("quydoi", "quy doi", "donvitinh", "don vi tinh")) else "not_observed",
        "rulebook_readme_evidence": f"{split}/rulebook.md sha256={rulebook_hash}; {split}/data/{business_id}/README.md sha256={readme_hash}; markers={','.join(markers) or 'none'}",
        "train_analogues": "self" if split == "train" else "pending_similarity_pass",
        "public_transfer_evidence": "not_applicable_train" if split == "train" else ("verified_Wave1_biz_102_103_104_to_dev_002_direct_revenue_only" if business_id == "dev_002" else "schema_candidate_only_no_metric_validation"),
        "blocker": "none_for_Wave1_direct_revenue_scope" if business_id == "dev_002" else "semantic/grain/cardinality proof required before metric enablement",
        "scan_errors": "|".join(errors),
    }

    table_rows = []
    for t in tables:
        table_rows.append({"split": split, "business_id": business_id, **t})

    capabilities = []
    for capability, cues in CAPABILITY_CUES.items():
        verified = VERIFIED.get(business_id, {}).get(capability)
        candidate = any(fold(cue) in combined_evidence for cue in cues)
        if verified:
            state = "verified" if not verified.startswith("loader_verified") else "loader_verified"
            evidence = verified
        elif candidate:
            state = "candidate"
            evidence = "filename/README/header cue only; semantics not proven"
        else:
            state = "unknown"
            evidence = "no cue observed in lightweight scan"
        capabilities.append({
            "split": split,
            "business_id": business_id,
            "capability_view": capability,
            "state": state,
            "evidence": evidence,
            "raw_audit_status": "scanned_with_errors" if errors else "scanned",
            "loader_status": "verified" if business_id in {"biz_102", "biz_103", "biz_104", "dev_002", "biz_116", "biz_123", "biz_129"} else "not_verified",
            "business_logic_status": "verified_narrow_scope" if business_id in {"biz_102", "biz_103", "biz_104", "dev_002", "biz_123", "biz_129"} and capability in VERIFIED.get(business_id, {}) else "not_verified",
            "train_exact_status": "29_target_pool" if business_id in {"biz_102", "biz_103", "biz_104"} and capability in {"sales", "orders/status"} else ("7_biz129_pool" if business_id == "biz_129" and capability in {"sales", "orders/status"} else "not_verified"),
            "public_enabled_status": "8_direct_revenue_only" if business_id == "dev_002" and capability in {"sales", "orders/status"} else "not_enabled",
            "interface_note": "minimal read-only view; raw data is not overwritten or coerced into a universal schema",
        })
    internal = {"matrix": matrix, "tables": table_rows, "capabilities": capabilities, "column_tokens": set(all_columns), "format_set": formats, "archetype": matrix["format_archetype"]}
    return matrix, table_rows, capabilities, internal


def run(project_root: Path, output_dir: Path) -> dict:
    all_matrix = []
    all_tables = []
    all_capabilities = []
    internals = []
    for split in ("train", "public_test"):
        split_root = project_root / split
        rulebook_hash = sha256(split_root / "rulebook.md")
        for business_dir in sorted((split_root / "data").iterdir()):
            if not business_dir.is_dir():
                continue
            matrix, tables, capabilities, internal = scan_business(split_root, split, business_dir, rulebook_hash)
            all_matrix.append(matrix)
            all_tables.extend(tables)
            all_capabilities.extend(capabilities)
            internals.append({"split": split, "business_id": business_dir.name, **internal})

    train = [x for x in internals if x["split"] == "train"]
    for item in [x for x in internals if x["split"] == "public_test"]:
        scored = sorted(((analogue_similarity(item, t), t["business_id"]) for t in train), reverse=True)[:3]
        evidence = "|".join(f"{bid}:{score:.4f}" for score, bid in scored)
        for row in all_matrix:
            if row["split"] == "public_test" and row["business_id"] == item["business_id"]:
                if item["business_id"] == "dev_002":
                    row["train_analogues"] = "biz_102|biz_103|biz_104 (Wave1 verified direct-revenue transfer); mechanical_top=" + evidence
                else:
                    row["train_analogues"] = evidence + " (mechanical header/format similarity only)"

    write_csv(output_dir / "business_archetype_matrix.csv", all_matrix)
    write_csv(output_dir / "capability_matrix.csv", all_capabilities)
    write_csv(output_dir / "schema_table_scan.csv", all_tables)
    result = {
        "business_count": len(all_matrix),
        "train_business_count": sum(r["split"] == "train" for r in all_matrix),
        "public_business_count": sum(r["split"] == "public_test" for r in all_matrix),
        "table_count": len(all_tables),
        "scan_error_business_count": sum(bool(r["scan_errors"]) for r in all_matrix),
        "scan_errors": {r["business_id"]: r["scan_errors"] for r in all_matrix if r["scan_errors"]},
    }
    (output_dir / "archetype_validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan DataMate business archetypes and capability candidates")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.project_root, args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
