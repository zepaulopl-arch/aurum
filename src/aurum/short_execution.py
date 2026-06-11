"""Short execution evaluation layer for Aurum trading system."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aurum.borrow_rates import estimate_borrow_cost, normalize_ticker, validate_borrow_record


def _as_float(value: Any, default: float = 0.0) -> float:
    """Convert value to float with default fallback."""
    if value is None or value == "":
        return default
    try:
        return float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return default


def _as_text(value: Any, default: str = "") -> str:
    """Convert value to text."""
    text = str(value or "").strip()
    return text or default


@dataclass
class ShortExecutionConfig:
    """Configuration for short execution evaluation."""

    enabled: bool = True
    max_borrow_cost_pct_annual: float = 20.0
    default_holding_days: int = 1
    min_short_net_rr: dict[str, float] = field(
        default_factory=lambda: {"CON": 1.20, "BAL": 0.90, "AGR": 0.60, "RLX": 0.40}
    )
    max_short_exposure_pct: dict[str, float] = field(
        default_factory=lambda: {"CON": 10.0, "BAL": 15.0, "AGR": 20.0, "RLX": 25.0}
    )
    require_borrow_data: bool = True
    require_margin_check: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ShortExecutionConfig":
        """Create config from dictionary."""
        data = data or {}
        return cls(
            enabled=bool(data.get("enabled", True)),
            max_borrow_cost_pct_annual=_as_float(
                data.get("max_borrow_cost_pct_annual"), 20.0
            ),
            default_holding_days=int(_as_float(data.get("default_holding_days"), 1.0)),
            min_short_net_rr=data.get("min_short_net_rr")
            or {"CON": 1.20, "BAL": 0.90, "AGR": 0.60, "RLX": 0.40},
            max_short_exposure_pct=data.get("max_short_exposure_pct")
            or {"CON": 10.0, "BAL": 15.0, "AGR": 20.0, "RLX": 25.0},
            require_borrow_data=bool(data.get("require_borrow_data", True)),
            require_margin_check=bool(data.get("require_margin_check", True)),
        )


def _default_short_setup_result(short_setup: dict[str, Any]) -> dict[str, Any]:
    """Build the base output payload for short execution evaluation."""
    return {
        "ticker": normalize_ticker(short_setup.get("ticker")),
        "short_signal": _as_text(short_setup.get("short_signal"), "SELL_SETUP"),
        "setup_score": _as_float(short_setup.get("setup_score") or short_setup.get("score"), 0.0),
        "entry": _as_float(short_setup.get("entry"), 0.0),
        "stop": _as_float(short_setup.get("stop"), 0.0),
        "target": _as_float(short_setup.get("target"), 0.0),
        "qty": _as_float(short_setup.get("qty"), 0.0),
        "notional": _as_float(short_setup.get("notional"), 0.0),
        "expected_gross_pnl": _as_float(short_setup.get("expected_gross_pnl"), 0.0),
        "holding_days": int(_as_float(short_setup.get("holding_days"), 1.0)),
        "liquidity_status": _as_text(short_setup.get("liquidity_status"), "UNKNOWN").upper(),
        "borrow_available": False,
        "available_qty": 0.0,
        "borrow_rate_annual": 0.0,
        "b3_fee_annual": 0.0,
        "broker_fee_annual": 0.0,
        "borrow_cost_brl": 0.0,
        "borrow_cost_pct": 0.0,
        "total_annual_cost": 0.0,
        "borrow_status": "BORROW_DATA_MISSING",
        "margin_status": "UNKNOWN",
        "net_expected_pnl": 0.0,
        "net_expected_return_pct": 0.0,
        "net_rr": 0.0,
        "execution": "DATA_BLOCKED",
        "main_reason": "short execution not evaluated",
    }


def _short_risk(entry: float, stop: float, qty: float) -> float:
    """Return risk in BRL for a short setup. For short, stop must be above entry."""
    if entry <= 0 or stop <= entry or qty <= 0:
        return 0.0
    return (stop - entry) * qty


def _apply_borrow_record(result: dict[str, Any], borrow_record: dict[str, Any]) -> None:
    """Copy borrow fields to the evaluation result."""
    result["borrow_available"] = bool(borrow_record.get("borrow_available", False))
    result["available_qty"] = _as_float(borrow_record.get("available_qty"), 0.0)
    result["borrow_rate_annual"] = _as_float(borrow_record.get("borrow_rate_annual"), 0.0)
    result["b3_fee_annual"] = _as_float(borrow_record.get("b3_fee_annual"), 0.0)
    result["broker_fee_annual"] = _as_float(borrow_record.get("broker_fee_annual"), 0.0)


def evaluate_short_execution(
    short_setup: dict[str, Any],
    borrow_record: dict[str, Any] | None,
    profile: str = "CON",
    config: ShortExecutionConfig | None = None,
) -> dict[str, Any]:
    """
    Evaluate if a short setup is execution-ready.

    The function is deliberately conservative: no borrow data means no short execution.
    """
    config = config or ShortExecutionConfig()
    profile = _as_text(profile, "CON").upper()
    result = _default_short_setup_result(short_setup)

    if not config.enabled:
        result["execution"] = "BLOCKED"
        result["main_reason"] = "short execution disabled"
        return result

    borrow_status, borrow_reason = validate_borrow_record(
        borrow_record,
        qty_needed=result["qty"],
    )
    result["borrow_status"] = borrow_status

    if borrow_record:
        _apply_borrow_record(result, borrow_record)

    if borrow_status != "BORROW_OK":
        result["execution"] = "DATA_BLOCKED"
        result["main_reason"] = borrow_reason
        return result

    notional = result["notional"]
    holding_days = result["holding_days"] or config.default_holding_days

    cost = estimate_borrow_cost(
        notional=notional,
        borrow_rate_annual=result["borrow_rate_annual"],
        b3_fee_annual=result["b3_fee_annual"],
        broker_fee_annual=result["broker_fee_annual"],
        holding_days=holding_days,
    )
    result["borrow_cost_brl"] = cost["borrow_cost_brl"]
    result["borrow_cost_pct"] = cost["borrow_cost_pct"]
    result["total_annual_cost"] = cost["total_annual_cost"]

    if cost["total_annual_cost"] > config.max_borrow_cost_pct_annual:
        result["execution"] = "COST_BLOCKED"
        result["main_reason"] = (
            f"borrow cost too high: {cost['total_annual_cost']:.2f}% > "
            f"{config.max_borrow_cost_pct_annual:.2f}%"
        )
        return result

    gross_pnl = result["expected_gross_pnl"]
    net_pnl = gross_pnl - result["borrow_cost_brl"]
    result["net_expected_pnl"] = round(net_pnl, 2)

    if notional > 0:
        result["net_expected_return_pct"] = round((net_pnl / notional) * 100.0, 4)

    if net_pnl <= 0:
        result["execution"] = "COST_BLOCKED"
        result["main_reason"] = "net expected pnl negative after borrow cost"
        return result

    total_risk = _short_risk(result["entry"], result["stop"], result["qty"])
    if total_risk > 0:
        result["net_rr"] = round(net_pnl / total_risk, 4)

    min_rr = _as_float(config.min_short_net_rr.get(profile), 1.0)
    if result["net_rr"] < min_rr:
        result["execution"] = "RR_BLOCKED"
        result["main_reason"] = f"net rr {result['net_rr']:.2f} below minimum {min_rr:.2f}"
        return result

    if result["liquidity_status"] not in {"OK", "GOOD"}:
        result["execution"] = "LIQUIDITY_BLOCKED"
        result["main_reason"] = f"liquidity {result['liquidity_status']}"
        return result

    result["execution"] = "SHORT_READY"
    result["borrow_status"] = "BORROW_OK"
    result["margin_status"] = "OK"
    result["main_reason"] = "short execution approved"
    return result


def batch_evaluate_short_execution(
    short_setups: list[dict[str, Any]],
    borrow_records: dict[str, dict[str, Any]],
    profile: str = "CON",
    config: ShortExecutionConfig | None = None,
) -> list[dict[str, Any]]:
    """Evaluate multiple short setups in batch."""
    results: list[dict[str, Any]] = []
    for setup in short_setups:
        ticker = normalize_ticker(setup.get("ticker"))
        results.append(
            evaluate_short_execution(
                setup,
                borrow_records.get(ticker),
                profile=profile,
                config=config,
            )
        )
    return results
