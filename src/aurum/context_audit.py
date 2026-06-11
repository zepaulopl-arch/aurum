"""Aurum context audit, show, and explain.

This module is intentionally conservative:
- it reads local context/config files;
- it does not fetch web/news/API data;
- it never invents macro facts;
- every expected context area gets a source_status.

The goal is to make the current market context auditable before adding external
official data sources.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_CONTEXT_PATH = "storage/context/latest_market_context.json"
DEFAULT_AUTO_CONTEXT_PATH = "storage/context/latest_market_context_auto.json"
DEFAULT_CONFIG_PATH = "config/market_context.json"
DEFAULT_THRESHOLDS_PATH = "config/market_context_thresholds.json"


CORE_FIELDS = (
    "market_trend",
    "market_volatility",
    "headline_tags",
    "notes",
)

MACRO_FIELDS = (
    "inflation_target",
    "inflation_current",
    "inflation_expectation",
    "selic",
    "interest_rate_bias",
    "copom_next_meeting",
    "copom_bias",
)

COMMODITY_FIELDS = (
    "oil",
    "brent",
    "wti",
    "iron_ore",
    "soybean",
    "corn",
    "coffee",
    "sugar",
)

EARNINGS_FIELDS = (
    "earnings_calendar",
    "earnings_risk",
    "assets_with_results_soon",
)

GEOPOLITICAL_FIELDS = (
    "geopolitical_risk",
    "oil_war_risk",
    "war_risk",
    "sanctions_risk",
)

SECTOR_FIELDS = (
    "sector_context",
    "sector_bias",
    "sector_risk",
)


def _as_path(value: str | Path) -> Path:
    return Path(value).resolve()


def _read_json(path: str | Path) -> tuple[dict[str, Any], str]:
    p = Path(path)
    if not p.exists():
        return {}, "MISSING"
    try:
        return json.loads(p.read_text(encoding="utf-8-sig")), "OK"
    except json.JSONDecodeError:
        return {}, "INVALID_JSON"
    except OSError:
        return {}, "ERROR"


def _write_json(path: str | Path, payload: dict[str, Any]) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def _flatten_keys(payload: Any, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            full = f"{prefix}.{key_text}" if prefix else key_text
            keys.add(full)
            keys.add(key_text)
            keys.update(_flatten_keys(value, full))
    elif isinstance(payload, list):
        for item in payload:
            keys.update(_flatten_keys(item, prefix))
    return keys


def _has_any_key(payload: dict[str, Any], expected: tuple[str, ...]) -> bool:
    keys = _flatten_keys(payload)
    lowered = {key.lower() for key in keys}
    return any(item.lower() in lowered for item in expected)


def _get_any(payload: dict[str, Any], keys: tuple[str, ...], default: Any = None) -> Any:
    lowered_targets = {key.lower() for key in keys}

    def walk(value: Any) -> Any:
        if isinstance(value, dict):
            for key, inner in value.items():
                if str(key).lower() in lowered_targets:
                    return inner
            for inner in value.values():
                found = walk(inner)
                if found is not None:
                    return found
        elif isinstance(value, list):
            for inner in value:
                found = walk(inner)
                if found is not None:
                    return found
        return None

    found = walk(payload)
    return default if found is None else found


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    candidates = [
        text,
        text.replace("Z", "+00:00"),
    ]
    for candidate in candidates:
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            pass
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d")
    except ValueError:
        return None


def _age_days(payload: dict[str, Any], file_path: Path | None = None) -> int | None:
    for key in ("created_at", "updated_at", "date", "as_of", "timestamp"):
        value = _get_any(payload, (key,))
        parsed = _parse_datetime(value)
        if parsed is not None:
            if parsed.tzinfo is not None:
                now = datetime.now(timezone.utc)
                parsed = parsed.astimezone(timezone.utc)
            else:
                now = datetime.now()
            return max(0, (now.date() - parsed.date()).days)
    if file_path and file_path.exists():
        modified = datetime.fromtimestamp(file_path.stat().st_mtime)
        return max(0, (datetime.now().date() - modified.date()).days)
    return None


def _status_from_presence(
    payload: dict[str, Any],
    fields: tuple[str, ...],
    *,
    missing_status: str = "MISSING",
) -> str:
    return "OK" if _has_any_key(payload, fields) else missing_status


def _coverage_items(payload: dict[str, Any]) -> dict[str, str]:
    return {
        "core": _status_from_presence(payload, CORE_FIELDS),
        "macro_inflation_rates": _status_from_presence(payload, MACRO_FIELDS),
        "copom": _status_from_presence(payload, ("copom_next_meeting", "copom_bias", "copom")),
        "commodities": _status_from_presence(payload, COMMODITY_FIELDS),
        "earnings": _status_from_presence(payload, EARNINGS_FIELDS),
        "geopolitical": _status_from_presence(payload, GEOPOLITICAL_FIELDS),
        "sector": _status_from_presence(payload, SECTOR_FIELDS),
    }


def _overall_status(file_status: str, age: int | None, coverage: dict[str, str]) -> str:
    if file_status != "OK":
        return file_status
    missing = [name for name, status in coverage.items() if status != "OK"]
    if age is not None and age > 7:
        return "STALE"
    if len(missing) >= 4:
        return "WEAK"
    if missing:
        return "PARTIAL"
    return "OK"


def _context_score(payload: dict[str, Any]) -> Any:
    return _get_any(payload, ("context_score", "score", "market_context_score"), "-")


def _headline_tags(payload: dict[str, Any]) -> list[str]:
    value = _get_any(payload, ("headline_tags", "tags"), [])
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def audit_context(
    context_path: str | Path = DEFAULT_CONTEXT_PATH,
    auto_context_path: str | Path = DEFAULT_AUTO_CONTEXT_PATH,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    thresholds_path: str | Path = DEFAULT_THRESHOLDS_PATH,
) -> dict[str, Any]:
    """Audit local context files and coverage."""
    context_file = Path(context_path)
    auto_file = Path(auto_context_path)
    config_file = Path(config_path)
    thresholds_file = Path(thresholds_path)

    context, context_status = _read_json(context_file)
    auto_context, auto_status = _read_json(auto_file)
    config, config_status = _read_json(config_file)
    thresholds, thresholds_status = _read_json(thresholds_file)

    coverage = _coverage_items(context)
    age = _age_days(context, context_file)
    source_status = {
        "context_file": context_status,
        "auto_context_file": auto_status,
        "config_file": config_status,
        "thresholds_file": thresholds_status,
        "core": coverage["core"],
        "macro_inflation_rates": coverage["macro_inflation_rates"],
        "copom": coverage["copom"],
        "commodities": coverage["commodities"],
        "earnings": coverage["earnings"],
        "geopolitical": coverage["geopolitical"],
        "sector": coverage["sector"],
    }

    missing_context = [
        name
        for name in (
            "macro_inflation_rates",
            "copom",
            "commodities",
            "earnings",
            "geopolitical",
            "sector",
        )
        if coverage.get(name) != "OK"
    ]

    payload: dict[str, Any] = {
        "schema_version": "aurum_context_audit.v1",
        "date": date.today().isoformat(),
        "paths": {
            "context": str(context_file),
            "auto_context": str(auto_file),
            "config": str(config_file),
            "thresholds": str(thresholds_file),
        },
        "status": _overall_status(context_status, age, coverage),
        "age_days": age,
        "market": {
            "trend": _get_any(context, ("market_trend", "trend"), "-"),
            "volatility": _get_any(context, ("market_volatility", "volatility"), "-"),
            "context_score": _context_score(context),
            "headline_tags": _headline_tags(context),
            "notes": _get_any(context, ("notes", "summary", "comment"), ""),
        },
        "coverage": coverage,
        "source_status": source_status,
        "missing_context": missing_context,
        "loaded": {
            "context_keys": sorted(_flatten_keys(context))[:300],
            "auto_context_keys": sorted(_flatten_keys(auto_context))[:200],
            "config_keys": sorted(_flatten_keys(config))[:200],
            "threshold_keys": sorted(_flatten_keys(thresholds))[:200],
        },
        "recommendations": build_context_recommendations(missing_context, context_status, age),
    }
    return payload


def build_context_recommendations(
    missing_context: list[str],
    context_status: str,
    age_days: int | None,
) -> list[str]:
    """Return conservative recommendations. Do not invent facts."""
    recommendations: list[str] = []
    if context_status != "OK":
        recommendations.append("Create or repair storage/context/latest_market_context.json.")
        return recommendations

    if age_days is not None and age_days > 7:
        recommendations.append("Refresh context: latest context appears stale.")

    mapping = {
        "macro_inflation_rates": "Add inflation target/current/expectation and Selic bias fields.",
        "copom": "Add COPOM next meeting and policy bias fields.",
        "commodities": "Add oil, iron ore, and key commodity risk fields.",
        "earnings": "Add earnings calendar/risk fields for monitored assets.",
        "geopolitical": "Add geopolitical/oil-war/sanctions risk fields when relevant.",
        "sector": "Add sector_context or sector_bias fields.",
    }
    for item in missing_context:
        recommendations.append(mapping.get(item, f"Add context coverage for {item}."))
    if not recommendations:
        recommendations.append("Context coverage is complete for the current audit schema.")
    return recommendations


def render_context_audit(payload: dict[str, Any]) -> str:
    """Render context audit."""
    market = payload.get("market", {})
    lines = [
        "AURUM CONTEXT AUDIT",
        "-" * 80,
        f"{'status':<24} {payload.get('status', '-')}",
        f"{'age_days':<24} {payload.get('age_days', '-')}",
        f"{'context_path':<24} {payload.get('paths', {}).get('context', '-')}",
        "",
        "MARKET SNAPSHOT",
        "-" * 80,
        f"{'trend':<24} {market.get('trend', '-')}",
        f"{'volatility':<24} {market.get('volatility', '-')}",
        f"{'context_score':<24} {market.get('context_score', '-')}",
        f"{'headline_tags':<24} {','.join(market.get('headline_tags', [])) or '-'}",
        "",
        "SOURCE STATUS",
        "-" * 80,
    ]
    for key, value in payload.get("source_status", {}).items():
        lines.append(f"{key:<24} {value}")
    lines.extend(["", "MISSING CONTEXT", "-" * 80])
    missing = payload.get("missing_context", [])
    lines.append(", ".join(missing) if missing else "-")
    lines.extend(["", "RECOMMENDATIONS", "-" * 80])
    for item in payload.get("recommendations", []):
        lines.append(f"- {item}")
    return "\n".join(lines)


def render_context_show(payload: dict[str, Any]) -> str:
    """Render compact context show output."""
    market = payload.get("market", {})
    lines = [
        "AURUM CONTEXT",
        "-" * 80,
        f"{'status':<24} {payload.get('status', '-')}",
        f"{'trend':<24} {market.get('trend', '-')}",
        f"{'volatility':<24} {market.get('volatility', '-')}",
        f"{'context_score':<24} {market.get('context_score', '-')}",
        f"{'headline_tags':<24} {','.join(market.get('headline_tags', [])) or '-'}",
        f"{'notes':<24} {market.get('notes', '') or '-'}",
    ]
    return "\n".join(lines)


def render_context_explain(payload: dict[str, Any]) -> str:
    """Render plain-language explanation of context coverage."""
    market = payload.get("market", {})
    lines = [
        "AURUM CONTEXT EXPLAIN",
        "-" * 80,
        f"Context status: {payload.get('status', '-')}.",
        (
            f"Market snapshot: trend={market.get('trend', '-')}, "
            f"volatility={market.get('volatility', '-')}, "
            f"score={market.get('context_score', '-')}."
        ),
    ]

    missing = payload.get("missing_context", [])
    if missing:
        lines.append(
            "Missing coverage: " + ", ".join(missing) + "."
        )
        lines.append(
            "The system can use the current context file, but it should not claim "
            "complete macro awareness until these fields are provided."
        )
    else:
        lines.append("Context coverage is complete for the current audit schema.")

    lines.extend(["", "Recommendations:"])
    for item in payload.get("recommendations", []):
        lines.append(f"- {item}")
    return "\n".join(lines)


def write_context_audit(
    payload: dict[str, Any],
    output: str | Path = "storage/context/latest_context_audit.json",
) -> Path:
    """Write context audit JSON."""
    return _write_json(output, payload)
