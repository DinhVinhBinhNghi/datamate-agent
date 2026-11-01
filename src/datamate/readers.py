"""Small direct readers for configured CSV, Excel, and SQLite sources."""

from __future__ import annotations

import sqlite3
import re
from pathlib import Path
from typing import Any

import pandas as pd


class SourceLoadError(RuntimeError):
    """A configured source could not be validated or loaded."""


def _require_file(data_root: Path, source_name: str, source: dict[str, Any]) -> Path:
    relative_path = source.get("path")
    if not isinstance(relative_path, str) or not relative_path:
        raise SourceLoadError(f"Source '{source_name}' has no non-empty path")
    path = data_root / relative_path
    if not path.is_file():
        raise SourceLoadError(f"Source '{source_name}' file does not exist: {path}")
    return path


def _validate_columns(
    df: pd.DataFrame, source_name: str, path: Path, source: dict[str, Any]
) -> None:
    semantic_columns = source.get("semantic_columns", {})
    if not isinstance(semantic_columns, dict):
        raise SourceLoadError(f"Source '{source_name}' semantic_columns must be an object")
    declared = list(semantic_columns.values())
    order_key = source.get("order_key")
    if order_key:
        declared.append(order_key)
    missing = sorted({column for column in declared if column not in df.columns})
    if missing:
        raise SourceLoadError(
            f"Source '{source_name}' at {path} is missing configured columns: {missing}; "
            f"found headers: {list(df.columns)}"
        )


def _apply_declared_forward_fill(
    df: pd.DataFrame, source_name: str, source: dict[str, Any]
) -> pd.DataFrame:
    columns = source.get("forward_fill_columns", [])
    if not isinstance(columns, list):
        raise SourceLoadError(f"Source '{source_name}' forward_fill_columns must be a list")
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise SourceLoadError(
            f"Source '{source_name}' cannot forward-fill missing columns: {missing}"
        )
    if columns:
        df = df.copy()
        df[columns] = df[columns].ffill()
    return df


def _add_file_provenance(
    df: pd.DataFrame, path: Path, sheet_or_table: str, first_data_row: int
) -> pd.DataFrame:
    result = df.copy()
    result["_source_file"] = str(path)
    result["_source_sheet_or_table"] = sheet_or_table
    result["_source_row"] = range(first_data_row, first_data_row + len(result))
    return result


def _read_csv(data_root: Path, source_name: str, source: dict[str, Any]) -> pd.DataFrame:
    path = _require_file(data_root, source_name, source)
    header_row = source.get("header_row", 0)
    try:
        df = pd.read_csv(
            path,
            encoding=source.get("encoding", "utf-8-sig"),
            sep=source.get("delimiter", ","),
            header=header_row,
        )
    except Exception as exc:
        raise SourceLoadError(f"Cannot load CSV source '{source_name}' at {path}: {exc}") from exc
    _validate_columns(df, source_name, path, source)
    df = _apply_declared_forward_fill(df, source_name, source)
    return _add_file_provenance(df, path, "csv", int(header_row) + 2)


def _read_excel(data_root: Path, source_name: str, source: dict[str, Any]) -> pd.DataFrame:
    path = _require_file(data_root, source_name, source)
    sheet = source.get("sheet")
    if not isinstance(sheet, str) or not sheet:
        raise SourceLoadError(f"Excel source '{source_name}' must declare a sheet")
    header_row = source.get("header_row", 0)
    try:
        workbook = pd.ExcelFile(path, engine="openpyxl")
        if sheet not in workbook.sheet_names:
            raise SourceLoadError(
                f"Excel source '{source_name}' at {path} has no sheet {sheet!r}; "
                f"available sheets: {workbook.sheet_names}"
            )
        df = pd.read_excel(workbook, sheet_name=sheet, header=header_row)
    except SourceLoadError:
        raise
    except Exception as exc:
        raise SourceLoadError(
            f"Cannot load Excel source '{source_name}' sheet {sheet!r} at {path}: {exc}"
        ) from exc
    _validate_columns(df, source_name, path, source)
    df = _apply_declared_forward_fill(df, source_name, source)
    return _add_file_provenance(df, path, sheet, int(header_row) + 2)


def _read_excel_fragments(
    data_root: Path, source_name: str, source: dict[str, Any]
) -> pd.DataFrame:
    """Read a declared set of same-schema Excel fragments in stable path order."""
    pattern = source.get("path_glob")
    if not isinstance(pattern, str) or not pattern or Path(pattern).is_absolute():
        raise SourceLoadError(
            f"Excel fragment source '{source_name}' must declare a relative path_glob"
        )
    if ".." in Path(pattern).parts:
        raise SourceLoadError(f"Excel fragment source '{source_name}' path_glob escapes data root")
    paths = sorted(path for path in data_root.glob(pattern) if path.is_file())
    expected_files = source.get("expected_files")
    if type(expected_files) is not int or expected_files < 1:
        raise SourceLoadError(
            f"Excel fragment source '{source_name}' must declare positive expected_files"
        )
    if len(paths) != expected_files:
        raise SourceLoadError(
            f"Excel fragment source '{source_name}' expected {expected_files} files, found {len(paths)}"
        )
    sheet = source.get("sheet")
    if not isinstance(sheet, str) or not sheet:
        raise SourceLoadError(f"Excel fragment source '{source_name}' must declare a sheet")
    header_row = source.get("header_row", 0)
    frames = []
    for path in paths:
        try:
            workbook = pd.ExcelFile(path, engine="openpyxl")
            if sheet not in workbook.sheet_names:
                raise SourceLoadError(
                    f"Excel fragment '{path}' has no sheet {sheet!r}; available: {workbook.sheet_names}"
                )
            frame = pd.read_excel(workbook, sheet_name=sheet, header=header_row)
        except SourceLoadError:
            raise
        except Exception as exc:
            raise SourceLoadError(
                f"Cannot load Excel fragment source '{source_name}' at {path}: {exc}"
            ) from exc
        _validate_columns(frame, source_name, path, source)
        frame = _apply_declared_forward_fill(frame, source_name, source)
        frames.append(_add_file_provenance(frame, path, sheet, int(header_row) + 2))
    return pd.concat(frames, ignore_index=True)


def _read_excel_sheets(
    data_root: Path, source_name: str, source: dict[str, Any]
) -> pd.DataFrame:
    """Read matching same-schema sheets from one workbook in workbook order."""
    path = _require_file(data_root, source_name, source)
    pattern_text = source.get("sheet_pattern")
    if not isinstance(pattern_text, str) or not pattern_text:
        raise SourceLoadError(
            f"Excel sheet source '{source_name}' must declare a sheet_pattern"
        )
    try:
        pattern = re.compile(pattern_text)
    except re.error as exc:
        raise SourceLoadError(
            f"Excel sheet source '{source_name}' has invalid sheet_pattern: {exc}"
        ) from exc
    expected_sheets = source.get("expected_sheets")
    if type(expected_sheets) is not int or expected_sheets < 1:
        raise SourceLoadError(
            f"Excel sheet source '{source_name}' must declare positive expected_sheets"
        )
    header_row = source.get("header_row", 0)
    try:
        workbook = pd.ExcelFile(path, engine="openpyxl")
        sheets = [name for name in workbook.sheet_names if pattern.fullmatch(name)]
        if len(sheets) != expected_sheets:
            raise SourceLoadError(
                f"Excel sheet source '{source_name}' expected {expected_sheets} matching "
                f"sheets, found {len(sheets)}; available: {workbook.sheet_names}"
            )
        frames = []
        for sheet in sheets:
            frame = pd.read_excel(workbook, sheet_name=sheet, header=header_row)
            _validate_columns(frame, source_name, path, source)
            # Forward fill within each sheet only; never leak an order across months.
            frame = _apply_declared_forward_fill(frame, source_name, source)
            frames.append(
                _add_file_provenance(frame, path, sheet, int(header_row) + 2)
            )
    except SourceLoadError:
        raise
    except Exception as exc:
        raise SourceLoadError(
            f"Cannot load Excel sheet source '{source_name}' at {path}: {exc}"
        ) from exc
    return pd.concat(frames, ignore_index=True)


def _quote_sqlite_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _read_sqlite(data_root: Path, source_name: str, source: dict[str, Any]) -> pd.DataFrame:
    path = _require_file(data_root, source_name, source)
    table = source.get("table")
    if not isinstance(table, str) or not table:
        raise SourceLoadError(f"SQLite source '{source_name}' must declare a table")
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True) as connection:
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
                (table,),
            ).fetchone()
            if not exists:
                available = [
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
                    )
                ]
                raise SourceLoadError(
                    f"SQLite source '{source_name}' at {path} has no table {table!r}; "
                    f"available tables: {available}"
                )
            quoted = _quote_sqlite_identifier(table)
            df = pd.read_sql_query(f"SELECT rowid AS _source_row, * FROM {quoted}", connection)
    except SourceLoadError:
        raise
    except Exception as exc:
        raise SourceLoadError(
            f"Cannot load SQLite source '{source_name}' table {table!r} at {path}: {exc}"
        ) from exc
    _validate_columns(df, source_name, path, source)
    df = _apply_declared_forward_fill(df, source_name, source)
    df["_source_file"] = str(path)
    df["_source_sheet_or_table"] = table
    return df


def load_source(
    config: dict[str, Any], source_name: str, data_root: str | Path
) -> pd.DataFrame:
    """Load one configured source without changing its raw columns or values."""
    sources = config.get("sources")
    if not isinstance(sources, dict) or source_name not in sources:
        available = sorted(sources) if isinstance(sources, dict) else []
        raise SourceLoadError(
            f"Source '{source_name}' is not configured; available sources: {available}"
        )
    source = sources[source_name]
    if not isinstance(source, dict):
        raise SourceLoadError(f"Source '{source_name}' config must be an object")
    source_format = source.get("format")
    readers = {
        "csv": _read_csv,
        "xlsx": _read_excel,
        "xlsx_fragments": _read_excel_fragments,
        "xlsx_sheets": _read_excel_sheets,
        "sqlite": _read_sqlite,
    }
    reader = readers.get(source_format)
    if reader is None:
        raise SourceLoadError(
            f"Source '{source_name}' has unsupported format {source_format!r}; "
            f"supported formats: {sorted(readers)}"
        )
    return reader(Path(data_root), source_name, source)
