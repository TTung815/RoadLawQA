"""Canonical artifact serialization used by current-law receipts (no V1 runner)."""

from datetime import datetime
from enum import Enum
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

def _json_default(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, Path)):
        return value.isoformat() if isinstance(value, datetime) else str(value)
    raise TypeError(f"Unsupported snapshot value: {type(value).__name__}")

def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False, default=_json_default).encode("utf-8")

def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()

def file_digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()

def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False,
                               allow_nan=False, default=_json_default) + "\n", encoding="utf-8")

def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def read_gzip_json(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)

def redact_schema(value: Any):
    """Preserve schema settings but never export embedded credentials."""
    if isinstance(value, dict):
        return {key: "<redacted>" if key.replace("_", "").lower() in (
            "apikey", "authorization", "password", "secret", "accesstoken", "token")
                else redact_schema(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_schema(item) for item in value]
    return value
