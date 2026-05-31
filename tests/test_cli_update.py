import json
from pathlib import Path

from pymercator.cli import main


def _patch_update_ok(monkeypatch):
    import pymercator.cli_update as update_mod

    monkeypatch.setattr(
        update_mod,
        "fetch_yahoo_prices_from_ticker_file",
        lambda **kwargs: {"failed": 0, "fetched": 1, "requested": 1},
    )
    monkeypatch.setattr(
        update_mod,
        "check_prices_dir",
        lambda prices_dir: {"exists": True, "files": 1, "invalid_files": 0},
    )
    monkeypatch.setattr(
        update_mod,
        "fetch_indices_prices",
        lambda **kwargs: {"status": "OK", "required_failed": 0, "fetched": 1},
    )
    monkeypatch.setattr(
        update_mod,
        "check_indices_prices_dir",
        lambda prices_dir: {"exists": True, "files": 1, "invalid_files": 0},
    )
    monkeypatch.setattr(
        update_mod,
        "write_auto_market_context",
        lambda **kwargs: {
            "output": kwargs["output"],
            "headline_tags": [],
            "market_trend": "CHOPPY",
            "market_volatility": "NORMAL",
        },
    )
    monkeypatch.setattr(
        update_mod,
        "validate_market_context",
        lambda path: {"valid": True, "path": str(path), "errors": []},
    )
    monkeypatch.setattr(
        update_mod,
        "build_universe_csv_from_prices",
        lambda **kwargs: {"asset_count": 1, "error_count": 0, "output": kwargs["output"]},
    )
    monkeypatch.setattr(
        update_mod,
        "validate_universe_csv",
        lambda path: {"valid": True, "path": str(path), "rows": 1},
    )
    monkeypatch.setattr(
        update_mod,
        "validate_features_catalog",
        lambda path: {"valid": True, "file": str(path), "errors": []},
    )
    monkeypatch.setattr(
        update_mod,
        "write_feature_matrix",
        lambda **kwargs: {"rows": 1, "output": kwargs["output"]},
    )


def test_cli_update_accepts_defaults_and_prints_summary(monkeypatch, capsys):
    _patch_update_ok(monkeypatch)

    exit_code = main(["update", "--list", "IBOV"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "UPDATE | LIST IBOV | STATUS OK" in captured.out
    assert "prices_dir" in captured.out


def test_cli_update_json_uses_custom_paths(tmp_path: Path, monkeypatch, capsys):
    _patch_update_ok(monkeypatch)

    exit_code = main(
        [
            "update",
            "--list",
            "IBOV",
            "--tickers-file",
            str(tmp_path / "tickers.csv"),
            "--prices-dir",
            str(tmp_path / "prices"),
            "--matrix-output",
            str(tmp_path / "matrix.csv"),
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "OK"
    assert payload["files"]["prices_dir"] == str(tmp_path / "prices")
    assert payload["files"]["matrix"] == str(tmp_path / "matrix.csv")


def test_cli_update_fails_clearly_on_step_failure(monkeypatch, capsys):
    import pymercator.cli_update as update_mod

    monkeypatch.setattr(
        update_mod,
        "fetch_yahoo_prices_from_ticker_file",
        lambda **kwargs: {"failed": 1, "fetched": 0, "requested": 1},
    )

    exit_code = main(["update", "--list", "IBOV"])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "UPDATE | LIST IBOV | STATUS FAIL" in captured.out
    assert "STEP: prices" in captured.out
