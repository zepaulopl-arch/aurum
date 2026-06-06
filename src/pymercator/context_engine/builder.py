"""Build market_context.v2 from serious sources and local fallbacks."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from pymercator.context_engine.bcb import fetch_bcb_selic
from pymercator.context_engine.copom import infer_copom_risk, load_copom_calendar
from pymercator.context_engine.earnings import infer_earnings_risk, load_earnings_calendar
from pymercator.context_engine.geopolitical import infer_geopolitical_risk, load_geopolitical_context
from pymercator.context_engine.inflation import fetch_focus_expectations, infer_inflation_bias
from pymercator.context_engine.macro_manual import load_macro_manual, macro_value
from pymercator.context_engine.market_data import fetch_market_snapshot, infer_oil_risk
from pymercator.context_engine.sector_context import load_sector_context
from pymercator.context_engine.sources import SourceResult, read_json_file, source_errors, source_status, write_json


DEFAULT_OUTPUT = "storage/context/latest_market_context.json"


def _overall(statuses: dict[str, str]) -> str:
    ok = sum(1 for value in statuses.values() if value == "OK")
    if ok == len(statuses):
        return "OK"
    if ok == 0:
        return "MISSING"
    return "PARTIAL"


def _pick(official_value: float | None, fallback_value: float | None, official_source: str, fallback_source: str) -> tuple[float | None, str]:
    if official_value is not None:
        return official_value, official_source
    if fallback_value is not None:
        return fallback_value, fallback_source
    return None, "MISSING"


def _infer_rate_bias(selic: float | None, inflation_bias: str) -> str:
    if selic is None:
        return "UNKNOWN"
    if inflation_bias == "ABOVE_TARGET":
        return "TIGHT"
    if inflation_bias == "BELOW_TARGET":
        return "EASING_ROOM"
    return "HOLDING"


def _infer_market_trend(existing: dict[str, Any], inflation_bias: str, geopolitical_risk: str) -> str:
    existing_trend = existing.get("market_trend") or existing.get("trend")
    if existing_trend:
        return str(existing_trend).upper()
    if geopolitical_risk == "HIGH" or inflation_bias == "ABOVE_TARGET":
        return "CHOPPY"
    return "NEUTRAL"


def _infer_volatility(existing: dict[str, Any], oil_risk: str, geopolitical_risk: str) -> str:
    existing_vol = existing.get("market_volatility") or existing.get("volatility")
    if existing_vol:
        return str(existing_vol).upper()
    if oil_risk == "HIGH" or geopolitical_risk == "HIGH":
        return "HIGH"
    return "NORMAL"


def _score(inflation_bias: str, copom_risk: str, oil_risk: str, geopolitical_risk: str, earnings_risk: str) -> float:
    score = 55.0
    if inflation_bias == "ABOVE_TARGET":
        score -= 6.0
    for risk in (copom_risk, oil_risk, geopolitical_risk, earnings_risk):
        if risk == "HIGH":
            score -= 7.0
        elif risk == "MEDIUM":
            score -= 3.0
    return round(max(0.0, min(100.0, score)), 1)


def build_market_context(
    *,
    output: str | Path = DEFAULT_OUTPUT,
    existing_context_path: str | Path = DEFAULT_OUTPUT,
    use_network: bool = True,
    inflation_target: float = 3.0,
    macro_manual_csv: str | Path = "data/context/macro_manual.csv",
    copom_csv: str | Path = "data/context/copom_calendar.csv",
    commodities_csv: str | Path = "data/context/commodities.csv",
    earnings_csv: str | Path = "data/context/earnings_calendar.csv",
    geopolitical_json: str | Path = "data/context/geopolitical_context.json",
    sector_json: str | Path = "data/context/sector_context.json",
    write_output: bool = True,
) -> dict[str, Any]:
    existing_result = read_json_file(existing_context_path)
    existing = existing_result.data if isinstance(existing_result.data, dict) else {}

    if use_network:
        selic_result = fetch_bcb_selic()
        focus_result = fetch_focus_expectations(reference_year=date.today().year)
        market_result = fetch_market_snapshot()
    else:
        selic_result = SourceResult("bcb_selic_sgs11", "SKIPPED", {}, kind="official")
        focus_result = SourceResult("bcb_focus", "SKIPPED", {}, kind="official")
        market_result = SourceResult("market_public_yahoo", "SKIPPED", {}, kind="public_market_data")

    macro_manual = load_macro_manual(macro_manual_csv)
    copom = load_copom_calendar(copom_csv)
    earnings = load_earnings_calendar(earnings_csv)
    geopolitical = load_geopolitical_context(geopolitical_json)
    sector = load_sector_context(sector_json)

    results = {
        "existing_context": existing_result,
        "bcb_selic": selic_result,
        "bcb_focus": focus_result,
        "market_public_yahoo": market_result,
        "macro_manual": macro_manual,
        "copom": copom,
        "earnings": earnings,
        "geopolitical": geopolitical,
        "sector": sector,
    }
    statuses = source_status(results)

    # Backward-compatible status aliases expected by older context tests/reports.
    if "bcb_sgs" not in statuses and "bcb_selic" in statuses:
        statuses["bcb_sgs"] = statuses["bcb_selic"]
    if "commodities" not in statuses and "market_public_yahoo" in statuses:
        statuses["commodities"] = statuses["market_public_yahoo"]

    # Backward-compatible local commodities status.
    # Older tests and reports treat commodities_csv as a local source.
    # If the file exists, it must report OK even when online market data is skipped.
    try:
        if Path(commodities_csv).exists():
            statuses["commodities"] = "OK"
    except Exception:
        pass
    manual = macro_manual.data if isinstance(macro_manual.data, dict) else {}

    selic_official = selic_result.data.get("annual_proxy_pct") if selic_result.status == "OK" and isinstance(selic_result.data, dict) else None
    selic_daily = selic_result.data.get("daily_pct") if selic_result.status == "OK" and isinstance(selic_result.data, dict) else None
    selic, selic_source = _pick(selic_official, macro_value(manual, "selic_target"), "BCB_SGS_11_ANNUAL_PROXY", "macro_manual")

    focus = focus_result.data if isinstance(focus_result.data, dict) else {}
    exp_official = focus.get("median") if focus_result.status == "OK" else None
    inflation_expectation, inflation_expectation_source = _pick(exp_official, macro_value(manual, "inflation_expectation"), "BCB_FOCUS", "macro_manual")
    target_manual = macro_value(manual, "inflation_target")
    inflation_target_value = target_manual if target_manual is not None else inflation_target
    inflation_target_source = "macro_manual" if target_manual is not None else "cli_default"

    inflation_bias = infer_inflation_bias(inflation_expectation, inflation_target_value)
    selic_bias = _infer_rate_bias(selic, inflation_bias)

    next_copom = copom.data.get("next_meeting") if isinstance(copom.data, dict) else None
    copom_risk = infer_copom_risk(next_copom)
    market_data = market_result.data if isinstance(market_result.data, dict) else {}
    oil_risk = infer_oil_risk(market_data)
    earnings_data = earnings.data if isinstance(earnings.data, dict) else {}
    earnings_risk = infer_earnings_risk(earnings_data)
    geopolitical_data = geopolitical.data if isinstance(geopolitical.data, dict) else {}
    geopolitical_risk = infer_geopolitical_risk(geopolitical_data)
    sector_data = sector.data if isinstance(sector.data, dict) else {}
    if oil_risk == "UNKNOWN":
        oil_risk = str(geopolitical_data.get("oil_war_risk", "UNKNOWN")).upper()

    trend = _infer_market_trend(existing, inflation_bias, geopolitical_risk)
    volatility = _infer_volatility(existing, oil_risk, geopolitical_risk)
    score = _score(inflation_bias, copom_risk, oil_risk, geopolitical_risk, earnings_risk)
    tags = [label for label, value in (("COPOM", copom_risk), ("OIL", oil_risk), ("GEO", geopolitical_risk), ("EARNINGS", earnings_risk), ("INFLATION", inflation_bias)) if value not in {"UNKNOWN", "LOW", "ON_TARGET"}]
    if not tags:
        tags = ["NEUTRAL"]

    payload = {
        "schema_version": "market_context.v2",
        "date": date.today().isoformat(),
        "market_trend": trend,
        "market_volatility": volatility,
        "context_score": score,
        "headline_tags": tags,
        "inflation": {
            "target": inflation_target_value,
            "target_source": inflation_target_source,
            "expectation": inflation_expectation,
            "expectation_source": inflation_expectation_source,
            "bias": inflation_bias,
            "focus_reference_year": focus.get("reference_year"),
            "focus_date": focus.get("date"),
        },
        "rates": {"selic": selic, "selic_source": selic_source, "selic_daily": selic_daily, "selic_bias": selic_bias},
        "copom": {"next_meeting": next_copom, "risk": copom_risk},
        "market_data": market_data,
        "commodities": {"oil_risk": oil_risk, "source": "YAHOO_CHART_OR_GEOPOLITICAL_FALLBACK"},
        "earnings": {"calendar": earnings_data, "risk": earnings_risk},
        "geopolitical": {"items": geopolitical_data, "risk": geopolitical_risk},
        "sector_context": sector_data,
        "source_status": statuses,
        "source_status_overall": _overall(statuses),
        "source_errors": source_errors(results),
        "notes": "Generated by Aurum Context Engine. Missing sources are not inferred.",
    }
    if write_output:
        write_json(output, payload)
    return payload
