"""Tests for borrow_rates module."""

from __future__ import annotations

from pathlib import Path

import pytest

from aurum.borrow_rates import (
    estimate_borrow_cost,
    get_borrow_record,
    read_borrow_rates_csv,
    validate_borrow_record,
)


def _write_borrow_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = [
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
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(",".join(headers) + "\n")
        for row in rows:
            values = [str(row.get(header, "")) for header in headers]
            f.write(",".join(values) + "\n")


def test_read_borrow_rates_csv_basic(tmp_path: Path) -> None:
    csv_path = tmp_path / "borrow.csv"
    _write_borrow_csv(
        csv_path,
        [
            {
                "date": "2026-06-05",
                "ticker": "AZZA3",
                "borrow_available": "true",
                "available_qty": "100000",
                "borrow_rate_annual": "8.50",
                "b3_fee_annual": "0.70",
                "broker_fee_annual": "0.00",
                "min_days": "1",
                "expiry_date": "2026-06-30",
                "reversible": "true",
                "source": "BROKER",
            },
            {
                "date": "2026-06-05",
                "ticker": "MGLU3",
                "borrow_available": "false",
                "available_qty": "0",
                "borrow_rate_annual": "0",
                "b3_fee_annual": "0",
                "broker_fee_annual": "0",
                "min_days": "1",
                "expiry_date": "2026-06-30",
                "reversible": "false",
                "source": "BROKER",
            },
        ],
    )

    rates = read_borrow_rates_csv(csv_path)

    assert "AZZA3" in rates
    assert "MGLU3" in rates
    assert rates["AZZA3"]["borrow_available"] is True
    assert rates["AZZA3"]["borrow_rate_annual"] == 8.50
    assert rates["MGLU3"]["borrow_available"] is False


def test_read_borrow_rates_csv_by_signal_date(tmp_path: Path) -> None:
    csv_path = tmp_path / "borrow.csv"
    _write_borrow_csv(
        csv_path,
        [
            {
                "date": "2026-06-03",
                "ticker": "AZZA3",
                "borrow_available": "true",
                "available_qty": "50000",
                "borrow_rate_annual": "10.00",
                "b3_fee_annual": "0.70",
                "broker_fee_annual": "0.00",
                "min_days": "1",
                "expiry_date": "2026-06-30",
                "reversible": "true",
                "source": "BROKER",
            },
            {
                "date": "2026-06-05",
                "ticker": "AZZA3",
                "borrow_available": "true",
                "available_qty": "100000",
                "borrow_rate_annual": "8.50",
                "b3_fee_annual": "0.70",
                "broker_fee_annual": "0.00",
                "min_days": "1",
                "expiry_date": "2026-06-30",
                "reversible": "true",
                "source": "BROKER",
            },
        ],
    )

    rates = read_borrow_rates_csv(csv_path, signal_date="2026-06-04")
    assert rates["AZZA3"]["borrow_rate_annual"] == 10.00

    rates = read_borrow_rates_csv(csv_path, signal_date="2026-06-05")
    assert rates["AZZA3"]["borrow_rate_annual"] == 8.50


def test_get_borrow_record_normalizes_ticker(tmp_path: Path) -> None:
    csv_path = tmp_path / "borrow.csv"
    _write_borrow_csv(
        csv_path,
        [
            {
                "date": "2026-06-05",
                "ticker": "AZZA3.SA",
                "borrow_available": "true",
                "available_qty": "100000",
                "borrow_rate_annual": "8.50",
                "b3_fee_annual": "0.70",
                "broker_fee_annual": "0.00",
                "min_days": "1",
                "expiry_date": "2026-06-30",
                "reversible": "true",
                "source": "BROKER",
            },
        ],
    )

    record = get_borrow_record("AZZA3.SA", csv_path)
    assert record is not None
    assert record["ticker"] == "AZZA3"
    assert record["borrow_rate_annual"] == 8.50


def test_estimate_borrow_cost() -> None:
    result = estimate_borrow_cost(
        notional=100000.0,
        borrow_rate_annual=8.50,
        b3_fee_annual=0.70,
        broker_fee_annual=0.00,
        holding_days=1,
    )

    assert result["borrow_cost_brl"] == pytest.approx(36.51, abs=0.1)
    assert result["borrow_cost_pct"] == pytest.approx(0.0365, abs=0.0001)


def test_estimate_borrow_cost_multi_day() -> None:
    one_day = estimate_borrow_cost(
        notional=100000.0,
        borrow_rate_annual=8.50,
        b3_fee_annual=0.70,
        broker_fee_annual=0.00,
        holding_days=1,
    )
    five_days = estimate_borrow_cost(
        notional=100000.0,
        borrow_rate_annual=8.50,
        b3_fee_annual=0.70,
        broker_fee_annual=0.00,
        holding_days=5,
    )

    assert five_days["borrow_cost_brl"] == pytest.approx(
        one_day["borrow_cost_brl"] * 5,
        abs=0.1,
    )


def test_validate_borrow_record_ok() -> None:
    status, reason = validate_borrow_record(
        {
            "borrow_available": True,
            "available_qty": 100000.0,
            "borrow_rate_annual": 8.50,
        },
        qty_needed=50000.0,
    )
    assert status == "BORROW_OK"
    assert reason == "borrow ok"


def test_validate_borrow_record_missing() -> None:
    status, _reason = validate_borrow_record(None)
    assert status == "BORROW_DATA_MISSING"


def test_validate_borrow_record_unavailable() -> None:
    status, _reason = validate_borrow_record(
        {
            "borrow_available": False,
            "available_qty": 0.0,
            "borrow_rate_annual": 0.0,
        },
    )
    assert status == "BORROW_UNAVAILABLE"


def test_validate_borrow_record_insufficient_qty() -> None:
    status, reason = validate_borrow_record(
        {
            "borrow_available": True,
            "available_qty": 10000.0,
            "borrow_rate_annual": 8.50,
        },
        qty_needed=50000.0,
    )
    assert status == "BORROW_INSUFFICIENT"
    assert "insufficient qty" in reason


def test_validate_borrow_record_missing_rate() -> None:
    status, _reason = validate_borrow_record(
        {
            "borrow_available": True,
            "available_qty": 100000.0,
            "borrow_rate_annual": 0.0,
        },
    )
    assert status == "BORROW_COST_MISSING"


def test_read_missing_csv() -> None:
    rates = read_borrow_rates_csv(Path("/tmp/nonexistent_borrow_rates.csv"))
    assert rates == {}
