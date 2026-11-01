"""Small direct readers for configured CSV, Excel, and SQLite sources."""

from __future__ import annotations

import sqlite3
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
    readers = {"csv": _read_csv, "xlsx": _read_excel, "sqlite": _read_sqlite}
    reader = readers.get(source_format)
    if reader is None:
        raise SourceLoadError(
            f"Source '{source_name}' has unsupported format {source_format!r}; "
            f"supported formats: {sorted(readers)}"
        )
    return reader(Path(data_root), source_name, source)
