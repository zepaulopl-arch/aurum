"""Borrow rates data management for short execution evaluation."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


BORROW_SCHEMA = [
    "date",
    "ticker",
    "borrow_available",
    "available_qty",
    "borrow_rate_annual",
    "b3_fee_annual",
    "broker_fee_annual",
    "min_days",
    "expiry_date",
    "reversible",
    "source",
]


def normalize_ticker(ticker: Any) -> str:
    """Normalize Brazilian tickers by removing .SA and uppercasing."""
    return str(ticker or "").strip().upper().replace(".SA", "")


def _as_float(value: Any, default: float = 0.0) -> float:
    """Convert value to float with a safe default."""
    if value is None or value == "":
        return default
    try:
        return float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    """Convert value to int with a safe default."""
    try:
        return int(_as_float(value, float(default)))
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any) -> bool:
    """Convert common CSV boolean values to bool."""
    text = str(value or "").strip().lower()
    return text in {"true", "1", "yes", "sim", "s", "y", "available", "ok"}


def _as_text(value: Any, default: str = "") -> str:
    """Convert value to stripped text."""
    text = str(value or "").strip()
    return text or default


def parse_borrow_row(row: dict[str, Any]) -> dict[str, Any] | None:
    """Parse a raw CSV row into a normalized borrow record."""
    ticker = normalize_ticker(row.get("ticker"))
    if not ticker:
        return None

    return {
        "date": _as_text(row.get("date"), ""),
        "ticker": ticker,
        "borrow_available": _as_bool(row.get("borrow_available")),
        "available_qty": _as_float(row.get("available_qty"), 0.0),
        "borrow_rate_annual": _as_float(row.get("borrow_rate_annual"), 0.0),
        "b3_fee_annual": _as_float(row.get("b3_fee_annual"), 0.0),
        "broker_fee_annual": _as_float(row.get("broker_fee_annual"), 0.0),
        "min_days": _as_int(row.get("min_days"), 1),
        "expiry_date": _as_text(row.get("expiry_date"), ""),
        "reversible": _as_bool(row.get("reversible", "true")),
        "source": _as_text(row.get("source"), "CSV"),
    }


def read_borrow_rates_csv(
    csv_path: Path | str,
    signal_date: str | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Read borrow rates from CSV and return records indexed by normalized ticker.

    Selection rule:
    - for each ticker, use the most recent row with date <= signal_date;
    - if signal_date is None, use the most recent row regardless of date;
    - if the file is missing or empty, return an empty dict.
    """
    path = Path(csv_path)
    result: dict[str, dict[str, Any]] = {}

    if not path.exists():
        return result

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            if not reader.fieldnames:
                return result

            for raw_row in reader:
                parsed = parse_borrow_row(raw_row)
                if not parsed:
                    continue

                record_date = parsed.get("date", "")
                if signal_date and record_date and record_date > signal_date:
                    continue

                ticker = parsed["ticker"]
                existing = result.get(ticker)
                existing_date = existing.get("date", "") if existing else ""

                if existing is None or record_date >= existing_date:
                    result[ticker] = parsed
    except OSError:
        return {}

    return result


def get_borrow_record(
    ticker: str,
    csv_path: Path | str,
    signal_date: str | None = None,
) -> dict[str, Any] | None:
    """Return the selected borrow record for a ticker, or None."""
    rates = read_borrow_rates_csv(csv_path, signal_date=signal_date)
    return rates.get(normalize_ticker(ticker))


def estimate_borrow_cost(
    notional: float,
    borrow_rate_annual: float,
    b3_fee_annual: float,
    broker_fee_annual: float,
    holding_days: int = 1,
) -> dict[str, float]:
    """
    Estimate borrow cost for a short position.

    Rates are annual percentages and use a 252 business-day convention:
    cost = notional * annual_rate_pct / 100 * holding_days / 252
    """
    clean_notional = max(0.0, _as_float(notional))
    clean_days = max(0, int(holding_days or 0))
    total_annual_cost = (
        _as_float(borrow_rate_annual)
        + _as_float(b3_fee_annual)
        + _as_float(broker_fee_annual)
    )
    borrow_cost_brl = clean_notional * (total_annual_cost / 100.0) * (clean_days / 252.0)
    borrow_cost_pct = (total_annual_cost * clean_days) / 252.0

    return {
        "borrow_cost_brl": round(borrow_cost_brl, 2),
        "borrow_cost_pct": round(borrow_cost_pct, 4),
        "total_annual_cost": round(total_annual_cost, 4),
    }


def validate_borrow_record(
    record: dict[str, Any] | None,
    qty_needed: float = 0.0,
) -> tuple[str, str]:
    """
    Validate borrow availability and basic cost data.

    Returns:
    - BORROW_OK
    - BORROW_DATA_MISSING
    - BORROW_UNAVAILABLE
    - BORROW_INSUFFICIENT
    - BORROW_COST_MISSING
    """
    if not record:
        return "BORROW_DATA_MISSING", "borrow data missing"

    if not bool(record.get("borrow_available", False)):
        return "BORROW_UNAVAILABLE", "borrow unavailable"

    available_qty = _as_float(record.get("available_qty"), 0.0)
    needed = _as_float(qty_needed, 0.0)
    if needed > 0 and available_qty < needed:
        return "BORROW_INSUFFICIENT", f"insufficient qty: {available_qty} < {needed}"

    borrow_rate = _as_float(record.get("borrow_rate_annual"), 0.0)
    if borrow_rate <= 0:
        return "BORROW_COST_MISSING", "borrow rate missing"

    return "BORROW_OK", "borrow ok"
