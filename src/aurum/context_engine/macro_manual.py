"""Manual macro fallback source for Aurum Context Engine.

File: data/context/macro_manual.csv

Schema:
name,value,source,updated_at
inflation_target,3.0,LOCAL_MANUAL,2026-06-06
inflation_expectation,,LOCAL_MANUAL,2026-06-06
selic_target,,LOCAL_MANUAL,2026-06-06

This is not a replacement for official sources. It is an explicit fallback with
source_status so the engine can remain auditable when official endpoints fail.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aurum.context_engine.sources import SourceResult, parse_float, read_csv_file


DEFAULT_MACRO_MANUAL_CSV = "data/context/macro_manual.csv"


def load_macro_manual(path: str | Path = DEFAULT_MACRO_MANUAL_CSV) -> SourceResult:
    """Load local/manual macro fallback values."""
    result = read_csv_file(path)
    result.name = "macro_manual"
    if result.status != "OK":
        return result

    data: dict[str, Any] = {}
    for row in result.data:
        name = str(row.get("name", "")).strip()
        if not name:
            continue
        data[name] = {
            "value": parse_float(row.get("value")),
            "raw_value": row.get("value", ""),
            "source": row.get("source", "LOCAL_MANUAL"),
            "updated_at": row.get("updated_at", ""),
        }

    result.data = data
    return result


def macro_value(data: dict[str, Any], name: str) -> float | None:
    """Extract a numeric macro value from loaded manual data."""
    item = data.get(name)
    if isinstance(item, dict):
        value = item.get("value")
        if isinstance(value, (int, float)):
            return float(value)
    return None
