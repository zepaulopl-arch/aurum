import csv
import json
from datetime import date, timedelta
from pathlib import Path

from pymercator.features_v2 import build_features_v2, write_features_v2
from pymercator.prediction_lab import build_prediction_dataset


def _write_price_file(path: Path, *, start: float = 10.0, rows: int = 90) -> None:
    lines = ["date,open,high,low,close,volume"]
    for index in range(rows):
        day = (date(2025, 1, 2) + timedelta(days=index)).isoformat()
        close = start + index * 0.2
        high = close * 1.01
        low = close * 0.99
        volume = 1000 + index * 5
        lines.append(f"{day},{close},{high},{low},{close},{volume}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    universe = tmp_path / "universe.csv"
    prices_dir = tmp_path / "prices"
    indices_dir = tmp_path / "indices"
    context = tmp_path / "context.json"
    config = tmp_path / "features.json"
    prices_dir.mkdir()
    indices_dir.mkdir()
    universe.write_text(
        "ticker,sector,last_close,trend_score,momentum_score,volatility_pct,atr_pct,news_score\n"
        "AAA3,energy,20,60,70,25,3,50\n"
        "BBB3,banks,30,40,35,22,2,50\n",
        encoding="utf-8",
    )
    _write_price_file(prices_dir / "AAA3.SA.csv", start=10)
    _write_price_file(prices_dir / "BBB3.SA.csv", start=20)
    _write_price_file(indices_dir / "^BVSP.csv", start=100)
    context.write_text(
        json.dumps(
            {
                "schema_version": "market_context.v2",
                "regime_summary": {
                    "market_regime": "RISK_OFF",
                    "market_trend": "DOWN",
                    "market_volatility": "NORMAL",
                    "context_score": 47.5,
                },
            }
        ),
        encoding="utf-8",
    )
    config.write_text(
        json.dumps(
            {
                "schema_version": "features_config.v2",
                "enabled": True,
                "feature_set": "core_v2",
                "enabled_groups": {
                    "returns": True,
                    "trend": True,
                    "momentum": True,
                    "volatility": True,
                    "volume_liquidity": True,
                    "relative_strength": True,
                    "sector_breadth": True,
                    "risk_drawdown": True,
                    "compression": True,
                    "market_context": True,
                },
                "selection": {
                    "enabled": True,
                    "max_missing_pct": 0.40,
                    "drop_constant": True,
                    "corr_threshold": 0.98,
                    "mutual_information_top_n": 20,
                    "per_horizon_selection": True,
                },
            }
        ),
        encoding="utf-8",
    )
    return universe, prices_dir, indices_dir, context, config


def test_features_v2_build_generates_selected_matrix_and_audit(tmp_path: Path) -> None:
    universe, prices_dir, indices_dir, context, config = _write_inputs(tmp_path)
    matrix = tmp_path / "latest_feature_matrix.csv"
    history = tmp_path / "latest_feature_history.csv"
    audit = tmp_path / "latest_feature_audit.json"
    feature_list = tmp_path / "latest_feature_list.json"

    payload = write_features_v2(
        universe=universe,
        prices_dir=prices_dir,
        indices_dir=indices_dir,
        context=context,
        config_path=config,
        matrix_output=matrix,
        history_output=history,
        audit_output=audit,
        feature_list_output=feature_list,
    )

    assert payload["status"] == "OK"
    assert matrix.exists()
    assert history.exists()
    assert audit.exists()
    assert feature_list.exists()
    assert payload["features_total"] > payload["features_used"] > 0

    audit_payload = json.loads(audit.read_text(encoding="utf-8"))
    assert audit_payload["feature_set"] == "core_v2"
    assert audit_payload["features_selected"] == payload["features_used"]
    assert "D5" in audit_payload["top_features_by_horizon"]

    with matrix.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    assert rows[0]["ticker"] == "AAA3"
    assert "ret_5d" in rows[0]
    assert "return_5d" in rows[0]
    assert "context_score" in rows[0]


def test_prediction_dataset_uses_feature_history_without_future_leakage(tmp_path: Path) -> None:
    universe, prices_dir, indices_dir, context, config = _write_inputs(tmp_path)
    matrix = tmp_path / "latest_feature_matrix.csv"
    history = tmp_path / "latest_feature_history.csv"
    audit = tmp_path / "latest_feature_audit.json"

    write_features_v2(
        universe=universe,
        prices_dir=prices_dir,
        indices_dir=indices_dir,
        context=context,
        config_path=config,
        matrix_output=matrix,
        history_output=history,
        audit_output=audit,
        feature_list_output=tmp_path / "latest_feature_list.json",
    )

    payload = build_prediction_dataset(
        matrix=matrix,
        prices_dir=prices_dir,
        horizon=5,
        min_history=20,
    )

    assert payload["feature_set"] == "core_v2"
    assert payload["features_used"] > 0
    assert payload["rows"] > 0
    row = payload["dataset"][0]
    assert "target_return_5d" in row
    assert "target_up_5d" in row
    assert "_close" not in payload["columns"]
    assert "ret_5d" in payload["columns"]


def test_features_v2_selection_removes_constant_and_correlated_features(tmp_path: Path) -> None:
    universe, prices_dir, indices_dir, context, config = _write_inputs(tmp_path)
    payload = build_features_v2(
        universe=universe,
        prices_dir=prices_dir,
        indices_dir=indices_dir,
        context=context,
        config_path=config,
    )

    summary = payload["audit"]["feature_selection_summary"]
    assert payload["audit"]["features_after_nan"] >= payload["audit"]["features_after_corr"]
    assert summary["dropped_constant"] or summary["dropped_corr"]
