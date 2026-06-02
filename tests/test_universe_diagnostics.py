import csv
from pathlib import Path

from pymercator.data.universe_csv import REQUIRED_COLUMNS, write_universe_template
from pymercator.data.universe_diagnostics import diagnose_universe_csv


def test_diagnose_universe_csv_returns_status_for_template(tmp_path: Path):
    universe = tmp_path / "template.csv"
    write_universe_template(universe)

    payload = diagnose_universe_csv(path=universe)

    assert payload["assets"] == 2
    assert payload["data_status"] in {
        "WARN_SMALL_UNIVERSE",
        "PASS_WITH_WARNINGS",
        "PASS",
    }
    assert "sector_concentration" in payload
    assert "sector_warning_summary" in payload
    assert "summary" in payload
    assert "diagnostics" in payload


def test_diagnose_universe_csv_flags_small_universe_for_template(tmp_path: Path):
    universe = tmp_path / "template.csv"
    write_universe_template(universe)

    payload = diagnose_universe_csv(path=universe)

    assert payload["asset_count_status"] == "TOO_SMALL"
    assert payload["assets"] < payload["min_assets"]


def test_diagnose_universe_csv_summarizes_warnings_by_sector(tmp_path: Path):
    universe = tmp_path / "universe.csv"
    rows = [
        {
            "ticker": "AAA3",
            "sector": "consumer_discretionary",
            "last_close": "10",
            "avg_volume_brl": "20000000",
            "trend_score": "30",
            "momentum_score": "35",
            "volatility_pct": "70",
            "atr_pct": "2",
            "liquidity_score": "80",
            "quality_score": "80",
            "news_score": "60",
            "entry": "10",
            "stop": "9",
            "target": "12",
        },
        {
            "ticker": "BBB3",
            "sector": "consumer_discretionary",
            "last_close": "11",
            "avg_volume_brl": "20000000",
            "trend_score": "34",
            "momentum_score": "32",
            "volatility_pct": "20",
            "atr_pct": "2",
            "liquidity_score": "80",
            "quality_score": "80",
            "news_score": "60",
            "entry": "11",
            "stop": "10",
            "target": "13",
        },
        {
            "ticker": "CCC3",
            "sector": "utilities",
            "last_close": "12",
            "avg_volume_brl": "20000000",
            "trend_score": "80",
            "momentum_score": "75",
            "volatility_pct": "10",
            "atr_pct": "2",
            "liquidity_score": "80",
            "quality_score": "80",
            "news_score": "60",
            "entry": "12",
            "stop": "11",
            "target": "14",
        },
    ]
    with universe.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    payload = diagnose_universe_csv(path=universe)

    by_sector = {
        item["sector"]: item
        for item in payload["sector_warning_summary"]
    }
    discretionary = by_sector["consumer_discretionary"]
    utilities = by_sector["utilities"]

    assert discretionary["assets"] == 2
    assert discretionary["vol_high"] == 1
    assert discretionary["weak_trend"] == 2
    assert discretionary["weak_momentum"] == 2
    assert discretionary["read"] in {"MIXED", "VOL+WEAK", "VOLATILE", "WEAK"}
    assert utilities["read"] == "OK"
    assert payload["summary"]["warnings_assets"] == 2
    assert "consumer_discretionary" in payload["summary"]["worst_sectors"]
