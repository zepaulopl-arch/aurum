"""Shared source helpers for the Aurum context engine."""

from __future__ import annotations

import csv
import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SourceResult:
    """Result returned by context sources."""

    name: str
    status: str
    data: Any = None
    url: str = ""
    error: str = ""
    kind: str = "unknown"
    detail: dict[str, Any] = field(default_factory=dict)

    def as_status(self) -> str:
        return self.status


def http_get_json(url: str, timeout: float = 12.0) -> SourceResult:
    """Fetch JSON using stdlib only.

    Returns explicit JSON_DECODE_ERROR when the server responds with non-JSON or
    an empty body. This is important for official endpoints that sometimes
    return HTML, proxy messages, or maintenance pages.
    """
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "AurumContextEngine/1.0",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status_code = getattr(response, "status", None)
            content_type = response.headers.get("Content-Type", "")
            raw_bytes = response.read()
        raw = raw_bytes.decode("utf-8-sig", errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            snippet = raw[:240].replace("\n", " ").replace("\r", " ")
            return SourceResult(
                name="http",
                status="JSON_DECODE_ERROR",
                url=url,
                error=f"{exc}; content_type={content_type}; body_snippet={snippet!r}",
                detail={"status_code": status_code, "content_type": content_type},
            )
        return SourceResult(
            name="http",
            status="OK",
            data=payload,
            url=url,
            detail={"status_code": status_code, "content_type": content_type},
        )
    except urllib.error.HTTPError as exc:
        return SourceResult(name="http", status="ERROR", url=url, error=f"HTTP {exc.code}: {exc.reason}")
    except urllib.error.URLError as exc:
        return SourceResult(name="http", status="ERROR", url=url, error=str(exc.reason))
    except TimeoutError:
        return SourceResult(name="http", status="ERROR", url=url, error="timeout")
    except Exception as exc:  # pragma: no cover - network/platform dependent
        return SourceResult(name="http", status="ERROR", url=url, error=str(exc))


def read_json_file(path: str | Path) -> SourceResult:
    p = Path(path)
    if not p.exists():
        return SourceResult(name=str(p), status="MISSING", data={})
    try:
        return SourceResult(
            name=str(p),
            status="OK",
            data=json.loads(p.read_text(encoding="utf-8-sig")),
        )
    except json.JSONDecodeError as exc:
        return SourceResult(name=str(p), status="INVALID_JSON", data={}, error=str(exc))
    except OSError as exc:
        return SourceResult(name=str(p), status="ERROR", data={}, error=str(exc))


def read_csv_file(path: str | Path) -> SourceResult:
    p = Path(path)
    if not p.exists():
        return SourceResult(name=str(p), status="MISSING", data=[])
    try:
        with p.open("r", encoding="utf-8-sig", newline="") as file:
            rows = list(csv.DictReader(file))
        return SourceResult(name=str(p), status="OK", data=rows)
    except OSError as exc:
        return SourceResult(name=str(p), status="ERROR", data=[], error=str(exc))


def write_json(path: str | Path, payload: dict[str, Any]) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def first_non_empty(*values: Any, default: Any = None) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return default


def parse_float(value: Any, default: float | None = None) -> float | None:
    if value in (None, ""):
        return default
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default

# ---------------------------------------------------------------------------
# Compatibility helpers for Context Engine source repair
# ---------------------------------------------------------------------------

def source_status(results):
    """Return source status mapping from SourceResult dictionary."""
    return {
        name: getattr(result, "status", "UNKNOWN")
        for name, result in results.items()
    }


def source_errors(results):
    """Return source errors mapping from SourceResult dictionary.

    Includes direct result.error and nested result.detail["errors"] when present.
    """
    errors = {}

    for name, result in results.items():
        direct_error = getattr(result, "error", "")
        if direct_error:
            errors[name] = direct_error

        detail = getattr(result, "detail", {})
        if isinstance(detail, dict):
            detail_errors = detail.get("errors")
            if detail_errors:
                errors[name] = detail_errors

    return errors
