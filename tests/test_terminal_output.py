import csv
import json
from pathlib import Path

from pymercator.cli import main
from pymercator.cli_train import render_train_summary
from pymercator.cli_universe import _render_universe_build
from pymercator.data.universe_csv import REQUIRED_COLUMNS
from pymercator.prediction_lab import render_prediction_lab_summary
from pymercator.ui import (
    available_palettes,
    color_metric,
    colorize,
    format_table,
    metric_status,
    set_color_mode,
    set_palette,
    set_ui_config_path,
    short_sector,
    strip_ansi,
)
from pymercator.ui.colors import ANSI_RE


def test_color_flags_control_terminal_output(capsys) -> None:
    exit_code = main(["diag", "--color", "always"])

    assert exit_code == 0
    assert "\x1b[" in capsys.readouterr().out

    exit_code = main(["diag", "--no-color"])

    assert exit_code == 0
    assert "\x1b[" not in capsys.readouterr().out


def test_palette_flag_selects_configured_palettes(capsys) -> None:
    assert {"soft", "bright", "classic"}.issubset(set(available_palettes()))

    classic_exit = main(["diag", "--color", "always", "--palette", "classic"])
    classic_output = capsys.readouterr().out

    bright_exit = main(["diag", "--color", "always", "--palette", "bright"])
    bright_output = capsys.readouterr().out

    assert classic_exit == 0
    assert bright_exit == 0
    assert "\x1b[32mOK\x1b[0m" in classic_output
    assert "\x1b[38;5;77mOK\x1b[0m" in bright_output


def test_strip_ansi_and_status_classes() -> None:
    blocked = colorize("BLOCKED", "BLOCKED", enabled=True)
    ok = colorize("OK", "OK", enabled=True)

    assert "\x1b[" in blocked
    assert "\x1b[" in ok
    assert strip_ansi(blocked) == "BLOCKED"
    assert strip_ansi(ok) == "OK"


def test_metric_color_classes_from_config() -> None:
    weak_trend = color_metric(30, "trend", width=5, enabled=True)
    warning_vol = color_metric(60, "vol", width=5, enabled=True)
    high_atr = color_metric(9, "atr", width=5, enabled=True)

    assert metric_status("trend", 70) == "OK"
    assert metric_status("mom", 50) == "WATCH"
    assert metric_status("mom", 30) == "WEAK"
    assert metric_status("vol", 90) == "HIGH"
    assert metric_status("atr", 9) == "HIGH"
    assert "\x1b[" in weak_trend
    assert "\x1b[" in warning_vol
    assert "\x1b[" in high_atr
    assert strip_ansi(weak_trend).strip() == "30"


def test_custom_ui_config_registers_arbitrary_index(tmp_path: Path) -> None:
    config = tmp_path / "ui.json"
    config.write_text(
        json.dumps(
            {
                "default_palette": "custom",
                "palettes": {
                    "custom": {
                        "green": "\u001b[38;5;82m",
                        "yellow": "\u001b[38;5;214m",
                        "red": "\u001b[38;5;196m",
                        "gray": "\u001b[38;5;244m",
                        "header": "\u001b[38;5;39m",
                        "number": "\u001b[38;5;250m",
                    }
                },
                "metric_aliases": {"my_index": "custom_edge"},
                "metric_thresholds": {
                    "custom_edge": [
                        {"min": 10.0, "status": "OK"},
                        {"min": 5.0, "status": "WATCH"},
                        {"status": "WEAK"},
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    try:
        set_ui_config_path(config)
        set_palette("custom")

        assert metric_status("my_index", 12) == "OK"
        assert metric_status("custom_edge", 7) == "WATCH"
        assert color_metric(12, "my_index", enabled=True).startswith("\x1b[38;5;82m")

        table = format_table(
            "CUSTOM TABLE",
            [("ASSET", "asset", 8), ("MY_INDEX", "my_index", 8)],
            [{"asset": "ABC3", "my_index": 12}],
            color=True,
        )
        assert "\x1b[38;5;82m" in table
    finally:
        set_ui_config_path("config/ui.json")
        set_palette("soft")


def test_sector_abbreviations_are_stable() -> None:
    assert short_sector("consumer_discretionary") == "consumer_disc."
    assert short_sector("consumer_staples") == "consumer_stap."
    assert short_sector("communication") == "comm."
    assert short_sector("health_care") == "health"


def test_universe_details_colors_core_metrics(tmp_path: Path, capsys) -> None:
    universe = tmp_path / "universe.csv"
    rows = [
        {
            "ticker": "BAD3",
            "sector": "consumer_discretionary",
            "last_close": "10",
            "avg_volume_brl": "100000000",
            "trend_score": "30",
            "momentum_score": "35",
            "volatility_pct": "70",
            "atr_pct": "9",
            "liquidity_score": "90",
            "quality_score": "50",
            "news_score": "50",
            "entry": "10",
            "stop": "9",
            "target": "12",
        }
    ]
    with universe.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    exit_code = main(
        [
            "universe",
            "diagnose",
            "--file",
            str(universe),
            "--details",
            "--color",
            "always",
        ]
    )

    assert exit_code in {0, 1}
    output = capsys.readouterr().out
    asset_line = next(line for line in output.splitlines() if line.startswith("BAD3"))
    sector_line = next(line for line in output.splitlines() if "consumer_disc." in line)
    assert asset_line.count("\x1b[") >= 4
    assert sector_line.count("\x1b[") >= 5
    assert strip_ansi(asset_line).split()[2:6] == ["70.0", "9.0", "30.0", "35.0"]


def test_universe_summary_colors_aggregate_indices(tmp_path: Path, capsys) -> None:
    universe = tmp_path / "universe.csv"
    rows = [
        {
            "ticker": "GOOD3",
            "sector": "utilities",
            "last_close": "10",
            "avg_volume_brl": "100000000",
            "trend_score": "70",
            "momentum_score": "65",
            "volatility_pct": "20",
            "atr_pct": "2",
            "liquidity_score": "90",
            "quality_score": "50",
            "news_score": "50",
            "entry": "10",
            "stop": "9",
            "target": "12",
        }
    ]
    with universe.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    exit_code = main(["universe", "summary", "--file", str(universe), "--color", "always"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "\x1b[" in next(line for line in output.splitlines() if "avg_trend" in line)
    assert "\x1b[" in next(line for line in output.splitlines() if "avg_momentum" in line)
    assert "\x1b[" in next(line for line in output.splitlines() if "avg_volatility" in line)


def test_universe_build_colors_asset_metric_table() -> None:
    set_color_mode("always")
    payload = {
        "prices_dir": "prices",
        "tickers_file": "",
        "output": "universe.csv",
        "asset_count": 1,
        "error_count": 0,
        "assets": [
            {
                "ticker": "BAD3",
                "sector": "consumer_discretionary",
                "last_close": 10.0,
                "trend_score": 30.0,
                "momentum_score": 35.0,
                "volatility_pct": 70.0,
                "atr_pct": 9.0,
                "news_score": 50.0,
            }
        ],
        "errors": [],
    }

    output = _render_universe_build(payload)

    try:
        asset_line = next(line for line in output.splitlines() if line.startswith("BAD3"))
        assert asset_line.count("\x1b[") >= 4
        assert strip_ansi(asset_line).split()[3:7] == ["30.00", "35.00", "70.00", "9.00"]
    finally:
        set_color_mode("auto")


def test_train_summary_colors_evaluation_metrics() -> None:
    set_color_mode("always")
    payload = {
        "status": "OK",
        "engine_used": "multi_horizon_ridge",
        "horizons": [5, 20, 60],
        "base_engines": ["extratrees", "randomforest", "gradientboosting"],
        "meta_model": "ridge",
        "observer": {"mode": "weighted"},
        "training": {"autotune": False},
        "dataset": {"rows": 1000, "assets": 40, "output": "storage/prediction"},
        "evaluation": {
            "output": "storage/prediction/latest_evaluation.json",
            "base_engines": ["extratrees", "randomforest", "gradientboosting"],
            "meta_model": "ridge",
        },
        "model_quality": {
            "status": "WEAK",
            "baseline_accuracy": 0.5,
            "ensemble_accuracy": 0.48,
            "edge": -0.02,
            "precision": 0.49,
            "recall": 0.51,
            "false_positive_rate": 0.4,
        },
        "horizon_observer": {
            "status": "OK",
            "combined_score": 48.0,
            "dominant_horizon": "D5",
            "behavior": "AVOID",
        },
        "horizon_models": {
            "D5": {
                "status": "OK",
                "ensemble_metrics": {
                    "accuracy": 0.48,
                    "precision": 0.49,
                    "recall": 0.51,
                },
            }
        },
    }

    try:
        output = render_train_summary(payload)
        assert output.count("\x1b[") >= 10
        assert "ensemble_accuracy:" in strip_ansi(output)
        assert "false_positive_rate:" in strip_ansi(output)
        assert "D5: OK acc=0.48" in strip_ansi(output)
    finally:
        set_color_mode("auto")


def test_prediction_lab_summary_colors_model_metrics() -> None:
    set_color_mode("always")
    payload = {
        "status": "OK",
        "dataset": {"file": "dataset.csv", "rows": 100},
        "evaluation": {
            "file": "evaluation.json",
            "evaluated_rows": 50,
            "n_jobs": 4,
            "engine_used": "ridge_ensemble",
            "is_baseline": False,
            "engine_status": {"extratrees": "OK"},
            "models": {
                "extratrees": {
                    "accuracy": 0.61,
                    "mae_return": 0.02,
                    "precision": 0.58,
                    "recall": 0.57,
                    "observations": 50,
                }
            },
        },
    }

    try:
        output = render_prediction_lab_summary(payload)
        assert output.count("\x1b[") >= 5
        plain = strip_ansi(output)
        assert "acc=0.61" in plain
        assert "mae=0.02" in plain
        assert "prec=0.58" in plain
        assert "recall=0.57" in plain
    finally:
        set_color_mode("auto")


def test_colorized_scenario_does_not_write_ansi_artifacts(
    tmp_path: Path,
    capsys,
) -> None:
    report_txt = tmp_path / "latest_daily_report.txt"
    report_json = tmp_path / "latest_daily_report.json"
    basket_csv = tmp_path / "latest_daily_basket.csv"

    exit_code = main(
        [
            "scenario",
            "run",
            "--preset",
            "positive_risk_on",
            "--profile",
            "AGR",
            "--basket",
            "--output-root",
            str(tmp_path / "scenarios"),
            "--report-output",
            str(report_txt),
            "--json-output",
            str(report_json),
            "--run-dir",
            str(tmp_path / "run"),
            "--basket-output",
            str(basket_csv),
            "--color",
            "always",
        ]
    )

    assert exit_code == 0
    assert "\x1b[" in capsys.readouterr().out

    basket_json = basket_csv.with_suffix(".json")
    basket_txt = basket_csv.with_suffix(".txt")
    for path in [report_txt, report_json, basket_csv, basket_json, basket_txt]:
        text = path.read_text(encoding="utf-8")
        assert not ANSI_RE.search(text), path

    report_payload = json.loads(report_json.read_text(encoding="utf-8"))
    basket_payload = json.loads(basket_json.read_text(encoding="utf-8"))
    assert report_payload["basket"]["status"] == "OK"
    assert basket_payload["status"] == "OK"

    set_color_mode("auto")
