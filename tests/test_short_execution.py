"""Tests for short_execution module."""

from __future__ import annotations

from aurum.short_execution import (
    ShortExecutionConfig,
    batch_evaluate_short_execution,
    evaluate_short_execution,
)


def _setup(**overrides):
    data = {
        "ticker": "AZZA3",
        "short_signal": "SELL_SETUP",
        "setup_score": 85.0,
        "entry": 10.0,
        "stop": 12.0,
        "target": 8.0,
        "qty": 1000.0,
        "notional": 10000.0,
        # Default must be high enough to pass CON min RR 1.20:
        # risk = (12 - 10) * 1000 = 2000
        # net RR must be >= 1.20, so net pnl must be >= 2400.
        "expected_gross_pnl": 3000.0,
        "holding_days": 1,
        "liquidity_status": "OK",
    }
    data.update(overrides)
    return data


def _borrow(**overrides):
    data = {
        "date": "2026-06-05",
        "ticker": "AZZA3",
        "borrow_available": True,
        "available_qty": 100000.0,
        "borrow_rate_annual": 8.50,
        "b3_fee_annual": 0.70,
        "broker_fee_annual": 0.00,
        "min_days": 1,
        "expiry_date": "2026-06-30",
        "reversible": True,
        "source": "BROKER",
    }
    data.update(overrides)
    return data


def test_short_execution_config_defaults() -> None:
    config = ShortExecutionConfig()

    assert config.enabled is True
    assert config.max_borrow_cost_pct_annual == 20.0
    assert config.default_holding_days == 1
    assert config.min_short_net_rr["CON"] == 1.20
    assert config.require_borrow_data is True


def test_short_execution_config_from_dict() -> None:
    config = ShortExecutionConfig.from_dict(
        {
            "enabled": True,
            "max_borrow_cost_pct_annual": 15.0,
            "default_holding_days": 2,
            "min_short_net_rr": {"CON": 1.5},
            "max_short_exposure_pct": {"CON": 12.0},
        }
    )

    assert config.enabled is True
    assert config.max_borrow_cost_pct_annual == 15.0
    assert config.default_holding_days == 2
    assert config.min_short_net_rr["CON"] == 1.5


def test_evaluate_short_execution_disabled() -> None:
    result = evaluate_short_execution(
        _setup(),
        None,
        config=ShortExecutionConfig(enabled=False),
    )

    assert result["execution"] == "BLOCKED"
    assert result["main_reason"] == "short execution disabled"


def test_evaluate_short_execution_missing_borrow_data() -> None:
    result = evaluate_short_execution(_setup(), None)

    assert result["execution"] == "DATA_BLOCKED"
    assert "borrow data missing" in result["main_reason"]
    assert result["borrow_status"] == "BORROW_DATA_MISSING"


def test_evaluate_short_execution_borrow_unavailable() -> None:
    result = evaluate_short_execution(
        _setup(),
        _borrow(borrow_available=False, available_qty=0.0, borrow_rate_annual=0.0),
    )

    assert result["execution"] == "DATA_BLOCKED"
    assert "borrow unavailable" in result["main_reason"]


def test_evaluate_short_execution_insufficient_qty() -> None:
    result = evaluate_short_execution(
        _setup(qty=1000.0),
        _borrow(available_qty=500.0),
    )

    assert result["execution"] == "DATA_BLOCKED"
    assert "insufficient qty" in result["main_reason"]


def test_evaluate_short_execution_cost_too_high() -> None:
    result = evaluate_short_execution(
        _setup(),
        _borrow(borrow_rate_annual=35.00, b3_fee_annual=0.70),
    )

    assert result["execution"] == "COST_BLOCKED"
    assert "borrow cost too high" in result["main_reason"]


def test_evaluate_short_execution_net_pnl_negative() -> None:
    config = ShortExecutionConfig(max_borrow_cost_pct_annual=20.0)
    result = evaluate_short_execution(
        _setup(expected_gross_pnl=5.0, holding_days=252),
        _borrow(borrow_rate_annual=8.50, b3_fee_annual=0.70),
        config=config,
    )

    assert result["execution"] == "COST_BLOCKED"
    assert "net expected pnl negative" in result["main_reason"]


def test_evaluate_short_execution_rr_below_minimum() -> None:
    config = ShortExecutionConfig(min_short_net_rr={"CON": 2.0})
    result = evaluate_short_execution(
        # risk = (11 - 10) * 1000 = 1000
        # net pnl around 100, therefore net_rr around 0.10 < 2.00.
        _setup(expected_gross_pnl=100.0, entry=10.0, stop=11.0),
        _borrow(),
        "CON",
        config,
    )

    assert result["execution"] == "RR_BLOCKED"
    assert "below minimum" in result["main_reason"]


def test_evaluate_short_execution_liquidity_bad() -> None:
    result = evaluate_short_execution(
        # High gross pnl ensures RR passes first; then liquidity blocks.
        _setup(liquidity_status="WEAK", expected_gross_pnl=3000.0),
        _borrow(),
    )

    assert result["execution"] == "LIQUIDITY_BLOCKED"
    assert "liquidity" in result["main_reason"]


def test_evaluate_short_execution_approved() -> None:
    result = evaluate_short_execution(_setup(expected_gross_pnl=3000.0), _borrow())

    assert result["execution"] == "SHORT_READY"
    assert result["borrow_status"] == "BORROW_OK"
    assert result["main_reason"] == "short execution approved"
    assert result["borrow_cost_brl"] > 0
    assert result["net_expected_pnl"] > 0
    assert result["net_expected_return_pct"] > 0
    assert result["net_rr"] >= 1.20


def test_batch_evaluate_short_execution() -> None:
    borrow_records = {
        "AZZA3": _borrow(),
        "MGLU3": _borrow(
            ticker="MGLU3",
            borrow_available=False,
            available_qty=0.0,
            borrow_rate_annual=0.0,
        ),
    }
    setups = [
        _setup(ticker="AZZA3", expected_gross_pnl=3000.0),
        _setup(ticker="MGLU3", setup_score=80.0),
    ]

    results = batch_evaluate_short_execution(setups, borrow_records)

    assert len(results) == 2
    assert results[0]["execution"] == "SHORT_READY"
    assert results[1]["execution"] == "DATA_BLOCKED"
