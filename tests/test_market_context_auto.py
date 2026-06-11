from pathlib import Path

from aurum.market_context_auto import (
    build_auto_market_context,
    calibrate_market_context_thresholds,
    write_auto_market_context,
)


def _write_prices(path: Path, closes: list[float]) -> None:
    lines = ["date,open,high,low,close,volume"]

    for index, close in enumerate(closes, start=1):
        lines.append(
            f"2025-01-{index:02d},{close},{close},{close},{close},1000"
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_build_auto_market_context_detects_risk_on(tmp_path: Path):
    indices = tmp_path / "indices"
    indices.mkdir()

    _write_prices(indices / "^BVSP.csv", [100 + i for i in range(30)])
    _write_prices(indices / "BZ=F.csv", [70.0 for _ in range(30)])
    _write_prices(indices / "USDBRL=X.csv", [5.0 for _ in range(30)])

    context = build_auto_market_context(indices)

    assert context["market_trend"] == "UP"
    assert "RISK_ON" in context["headline_tags"]
    assert context["source"] == "auto_indices"


def test_build_auto_market_context_detects_oil_and_fx_stress(tmp_path: Path):
    indices = tmp_path / "indices"
    indices.mkdir()

    _write_prices(indices / "^BVSP.csv", [100.0 for _ in range(30)])
    _write_prices(indices / "BZ=F.csv", [70.0 for _ in range(24)] + [80, 81, 82, 83, 84, 85])
    _write_prices(
        indices / "USDBRL=X.csv",
        [5.0 for _ in range(24)] + [5.2, 5.3, 5.4, 5.5, 5.6, 5.7],
    )

    context = build_auto_market_context(indices)

    assert "OIL_STRESS" in context["headline_tags"]
    assert "FX_STRESS" in context["headline_tags"]


def test_write_auto_market_context_creates_json(tmp_path: Path):
    indices = tmp_path / "indices"
    output = tmp_path / "market_context_auto.json"
    indices.mkdir()

    _write_prices(indices / "^BVSP.csv", [100.0 for _ in range(30)])
    _write_prices(indices / "BZ=F.csv", [70.0 for _ in range(30)])
    _write_prices(indices / "USDBRL=X.csv", [5.0 for _ in range(30)])

    payload = write_auto_market_context(
        indices_dir=indices,
        output=output,
    )

    assert output.exists()
    assert payload["output"] == str(output)
    assert payload["market_trend"] in {"UP", "DOWN", "CHOPPY"}


def test_auto_market_context_uses_threshold_file(tmp_path: Path):
    indices = tmp_path / "indices"
    thresholds = tmp_path / "thresholds.json"
    indices.mkdir()
    thresholds.write_text(
        """
{
  "schema_version": "market_context_thresholds.v1",
  "thresholds": {
    "trend_up_return_20d_pct": 100.0,
    "trend_up_sma_position_pct": 100.0,
    "trend_down_return_20d_pct": -100.0,
    "trend_down_sma_position_pct": -100.0,
    "volatility_high_pct": 99.0,
    "volatility_low_pct": 0.1,
    "oil_stress_return_5d_pct": 99.0,
    "oil_stress_return_20d_pct": 99.0,
    "fx_stress_return_5d_pct": 99.0,
    "fx_stress_return_20d_pct": 99.0
  }
}
""",
        encoding="utf-8",
    )

    _write_prices(indices / "^BVSP.csv", [100 + i for i in range(30)])
    _write_prices(indices / "BZ=F.csv", [70.0 for _ in range(30)])
    _write_prices(indices / "USDBRL=X.csv", [5.0 for _ in range(30)])

    context = build_auto_market_context(indices, thresholds_path=thresholds)

    assert context["market_trend"] == "CHOPPY"
    assert "RISK_ON" not in context["headline_tags"]


def test_calibrate_market_context_thresholds_writes_config_patch(tmp_path: Path):
    indices = tmp_path / "indices"
    output = tmp_path / "market_context_calibration.json"
    indices.mkdir()

    _write_prices(indices / "^BVSP.csv", [100 + i for i in range(40)])
    _write_prices(indices / "BZ=F.csv", [70 + i * 0.1 for i in range(40)])
    _write_prices(indices / "USDBRL=X.csv", [5 + i * 0.01 for i in range(40)])

    payload = calibrate_market_context_thresholds(indices_dir=indices, output=output)

    assert payload["command"] == "context_calibrate"
    assert payload["config_patch"]["thresholds"] == payload["thresholds"]
    assert output.exists()
