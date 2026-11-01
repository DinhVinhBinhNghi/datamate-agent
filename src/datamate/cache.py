"""Derived SQLite cache for measured slow direct sources."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any

import pandas as pd

from datamate.readers import SourceLoadError, load_source


LOADER_VERSION = "chat03-sqlite-cache-v1"


class CacheError(RuntimeError):
    """A derived cache could not be built, validated, or read."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cache_identity(
    config: dict[str, Any], source_name: str, data_root: str | Path
) -> dict[str, str]:
    source = config["sources"][source_name]
    source_path = Path(data_root) / source["path"]
    if not source_path.is_file():
        raise CacheError(f"Cannot hash missing source '{source_name}': {source_path}")
    source_hash = _sha256_file(source_path)
    config_bytes = json.dumps(
        config, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    config_hash = hashlib.sha256(config_bytes).hexdigest()
    key_material = f"{source_hash}:{config_hash}:{LOADER_VERSION}".encode("utf-8")
    return {
        "source_hash": source_hash,
        "config_hash": config_hash,
        "loader_version": LOADER_VERSION,
        "cache_key": hashlib.sha256(key_material).hexdigest(),
    }


def cache_path_for(
    config: dict[str, Any], source_name: str, data_root: str | Path, cache_root: str | Path
) -> tuple[Path, dict[str, str]]:
    identity = cache_identity(config, source_name, data_root)
    path = (
        Path(cache_root)
        / config["split"]
        / config["business_id"]
        / source_name
        / f"{identity['cache_key']}.sqlite"
    )
    return path, identity


def _encode_mixed_object_columns(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    encoded = frame.copy()
    mixed: list[str] = []
    for column in encoded.columns:
        if encoded[column].dtype != object:
            continue
        types = {type(value).__name__ for value in encoded[column] if pd.notna(value)}
        if len(types) <= 1:
            continue
        mixed.append(str(column))
        encoded[column] = encoded[column].map(
            lambda value: None
            if pd.isna(value)
            else json.dumps(
                {"type": type(value).__name__, "value": value},
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
    return encoded, mixed


def _decode_mixed_value(value: Any) -> Any:
    if value is None:
        return None
    payload = json.loads(value)
    kind = payload["type"]
    raw = payload["value"]
    converters = {"int": int, "float": float, "str": str, "bool": bool}
    if kind not in converters:
        raise CacheError(f"Unsupported cached mixed scalar type: {kind}")
    return converters[kind](raw)


def build_cache(
    config: dict[str, Any],
    source_name: str,
    data_root: str | Path,
    cache_root: str | Path,
    frame: pd.DataFrame | None = None,
) -> tuple[Path, dict[str, str]]:
    """Build one cache in the destination directory and publish it atomically."""
    path, identity = cache_path_for(config, source_name, data_root, cache_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if frame is None:
        frame = load_source(config, source_name, data_root)
    encoded, mixed_columns = _encode_mixed_object_columns(frame)
    manifest = {
        **identity,
        "business_id": config["business_id"],
        "split": config["split"],
        "source_name": source_name,
        "row_count": int(len(frame)),
        "columns": [str(column) for column in frame.columns],
        "dtypes": {str(column): str(dtype) for column, dtype in frame.dtypes.items()},
        "mixed_object_columns": mixed_columns,
    }
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        connection = sqlite3.connect(temporary)
        try:
            encoded.to_sql("source_data", connection, index=False, if_exists="fail")
            connection.execute(
                "CREATE TABLE cache_manifest (manifest_json TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT INTO cache_manifest(manifest_json) VALUES (?)",
                (json.dumps(manifest, ensure_ascii=False, sort_keys=True),),
            )
            connection.commit()
        finally:
            connection.close()
        os.replace(temporary, path)
    except Exception as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise CacheError(
            f"Cannot build cache for source '{source_name}' at {path}: {exc}"
        ) from exc
    return path, identity


def read_cache(path: str | Path, expected_identity: dict[str, str]) -> pd.DataFrame:
    path = Path(path)
    if not path.is_file():
        raise CacheError(f"Cache file does not exist: {path}")
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True) as connection:
            row = connection.execute(
                "SELECT manifest_json FROM cache_manifest"
            ).fetchone()
            if row is None:
                raise CacheError(f"Cache manifest is missing: {path}")
            manifest = json.loads(row[0])
            for field in ("source_hash", "config_hash", "loader_version", "cache_key"):
                if manifest.get(field) != expected_identity[field]:
                    raise CacheError(
                        f"Cache identity mismatch for {field} at {path}: "
                        f"expected {expected_identity[field]}, got {manifest.get(field)}"
                    )
            frame = pd.read_sql_query("SELECT * FROM source_data", connection)
    except CacheError:
        raise
    except Exception as exc:
        raise CacheError(f"Cannot read cache {path}: {exc}") from exc
    for column in manifest["mixed_object_columns"]:
        frame[column] = frame[column].map(_decode_mixed_value).astype(object)
    if len(frame) != manifest["row_count"] or list(frame.columns) != manifest["columns"]:
        raise CacheError(f"Cache shape/schema mismatch: {path}")
    return frame


def load_source_cached(
    config: dict[str, Any],
    source_name: str,
    data_root: str | Path,
    cache_root: str | Path,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Read a valid cache, or build it from the direct reader and then read it."""
    if (config.get("split"), config.get("business_id"), source_name) != (
        "train",
        "biz_116",
        "sales_lines",
    ):
        raise CacheError(
            "Baseline cache is intentionally limited to train/biz_116/sales_lines"
        )
    path, identity = cache_path_for(config, source_name, data_root, cache_root)
    built = False
    if not path.is_file():
        build_cache(config, source_name, data_root, cache_root)
        built = True
    frame = read_cache(path, identity)
    return frame, {"cache_path": str(path), "cache_key": identity["cache_key"], "built": built}
