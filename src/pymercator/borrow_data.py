from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def _ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_bool(value: Any, default: bool = False) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return default
    if text in {"1", "true", "t", "yes", "y", "sim", "s", "available"}:
        return True
    if text in {"0", "false", "f", "no", "n", "nao", "não", "unavailable"}:
        return False
    return default


def load_borrow_data(
    path: str | Path | None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    if not path:
        return {"status": "DISABLED", "path": "", "records": 0}, {}

    source = Path(path)
    if not source.exists():
        return {"status": "MISSING", "path": str(source), "records": 0}, {}

    records: dict[str, dict[str, Any]] = {}
    try:
        with source.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                ticker = _ticker(row.get("ticker"))
                if not ticker:
                    continue
                available_qty = _to_float(row.get("available_qty"), 0.0)
                available = _to_bool(row.get("available"), available_qty > 0)
                records[ticker] = {
                    "ticker": ticker,
                    "available": available,
                    "borrow_cost_pct": _to_float(row.get("borrow_cost_pct"), 0.0),
                    "available_qty": available_qty,
                    "liquidity_ok": _to_bool(row.get("liquidity_ok"), False),
                    "squeeze_risk": _to_float(row.get("squeeze_risk"), 100.0),
                }
    except Exception as exc:
        return {
            "status": "INVALID",
            "path": str(source),
            "records": 0,
            "warning": f"unable to load borrow data: {exc}",
        }, {}

    return {"status": "OK", "path": str(source), "records": len(records)}, records


def evaluate_borrow_record(
    record: dict[str, Any] | None,
    config: dict[str, Any],
) -> tuple[bool, str]:
    if not record:
        return False, "borrow/cost data unavailable"
    if not bool(record.get("available", False)):
        return False, "borrow unavailable"
    if not bool(record.get("liquidity_ok", False)):
        return False, "borrow liquidity not confirmed"

    max_cost = _to_float(config.get("max_borrow_cost_pct"), 5.0)
    min_qty = _to_float(config.get("min_available_qty"), 1.0)
    max_squeeze = _to_float(config.get("max_squeeze_risk"), 70.0)
    cost = _to_float(record.get("borrow_cost_pct"), 0.0)
    qty = _to_float(record.get("available_qty"), 0.0)
    squeeze = _to_float(record.get("squeeze_risk"), 100.0)

    if cost > max_cost:
        return False, "borrow cost above limit"
    if qty < min_qty:
        return False, "borrow availability below minimum"
    if squeeze > max_squeeze:
        return False, "squeeze risk above limit"
    return True, "borrow available; short remains observational"
