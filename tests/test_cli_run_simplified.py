import json
from pathlib import Path

from pymercator.cli import main


def _write_context(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "headline_tags": [],
                "market_trend": "UP",
                "market_volatility": "NORMAL",
                "notes": "test context",
            }
        ),
        encoding="utf-8",
    )


def test_cli_run_executes_daily_with_defaults_for_outputs(tmp_path: Path, capsys):
    context = tmp_path / "context.json"
    report = tmp_path / "report.txt"
    json_report = tmp_path / "report.json"
    run_dir = tmp_path / "latest"
    basket_output = tmp_path / "basket.csv"
    _write_context(context)

    exit_code = main(
        [
            "run",
            "--profile",
            "CON",
            "--universe",
            "data/universes/ibov_sample.csv",
            "--context",
            str(context),
            "--report-output",
            str(report),
            "--json-output",
            str(json_report),
            "--run-dir",
            str(run_dir),
            "--basket-output",
            str(basket_output),
            "--json",
        ]
    )

    assert exit_code == 0
    assert report.exists()
    assert json_report.exists()
    assert (run_dir / "report.txt").exists()
    assert (run_dir / "report.json").exists()
    assert not basket_output.exists()

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "OK"
    assert payload["profile"] == "CON"
    assert payload["basket"] is None


def test_cli_run_with_basket_generates_basket(tmp_path: Path, monkeypatch, capsys):
    import pymercator.cli_run as run_mod

    context = tmp_path / "context.json"
    report = tmp_path / "report.txt"
    json_report = tmp_path / "report.json"
    run_dir = tmp_path / "latest"
    basket_output = tmp_path / "basket.csv"
    _write_context(context)

    def fake_basket(**kwargs):
        assert kwargs["eligible_tickers"]
        Path(kwargs["output_csv"]).parent.mkdir(parents=True, exist_ok=True)
        Path(kwargs["output_csv"]).write_text("ticker,weight\nPRIO3,0.2\n", encoding="utf-8")
        return {
            "status": "OK",
            "slots": kwargs["slots"],
            "output_csv": kwargs["output_csv"],
            "rows": [{"ticker": "PRIO3"}],
        }

    monkeypatch.setattr(run_mod, "run_daily_basket", fake_basket)

    exit_code = main(
        [
            "run",
            "--profile",
            "CON",
            "--universe",
            "data/universes/ibov_sample.csv",
            "--context",
            str(context),
            "--report-output",
            str(report),
            "--json-output",
            str(json_report),
            "--run-dir",
            str(run_dir),
            "--basket",
            "--basket-output",
            str(basket_output),
            "--json",
        ]
    )

    assert exit_code == 0
    assert basket_output.exists()
    payload = json.loads(capsys.readouterr().out)
    assert payload["decision"]["actionable"] > 0
    assert payload["basket"]["status"] == "OK"
    assert payload["basket"]["assets"] == 1


def test_cli_run_blocks_invalid_unknown_context(
    tmp_path: Path,
    capsys,
):
    context = tmp_path / "context.json"
    report = tmp_path / "report.txt"
    json_report = tmp_path / "report.json"
    run_dir = tmp_path / "latest"
    context.write_text(
        json.dumps(
            {
                "headline_tags": [],
                "market_trend": "UNKNOWN",
                "market_volatility": "NORMAL",
                "notes": "unknown trend blocks operational basket",
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "run",
            "--profile",
            "CON",
            "--universe",
            "data/universes/ibov_sample.csv",
            "--context",
            str(context),
            "--report-output",
            str(report),
            "--json-output",
            str(json_report),
            "--run-dir",
            str(run_dir),
            "--json",
        ]
    )

    assert exit_code == 1
    assert not report.exists()
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "BLOCKED"
    assert payload["reason"] == "invalid or insufficient market context"


def test_cli_run_with_basket_blocks_when_no_actionable_assets(
    tmp_path: Path,
    capsys,
):
    context = tmp_path / "context.json"
    report = tmp_path / "report.txt"
    json_report = tmp_path / "report.json"
    run_dir = tmp_path / "latest"
    basket_output = tmp_path / "basket.csv"
    context.write_text(
        json.dumps(
            {
                "headline_tags": ["RISK_OFF"],
                "market_trend": "DOWN",
                "market_volatility": "NORMAL",
                "notes": "defensive context should not create operational basket",
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "run",
            "--profile",
            "CON",
            "--universe",
            "data/universes/ibov_sample.csv",
            "--context",
            str(context),
            "--report-output",
            str(report),
            "--json-output",
            str(json_report),
            "--run-dir",
            str(run_dir),
            "--basket",
            "--basket-output",
            str(basket_output),
            "--json",
        ]
    )

    assert exit_code == 0
    assert basket_output.exists()
    assert basket_output.read_text(encoding="utf-8").splitlines() == [
        (
            "ticker,sector,rank,score,entry,initial_stop,target_1,target_2,"
            "stop_after_t1,trailing_rule,weight,position_value,risk_per_share,"
            "max_loss,quantity,status,warnings"
        )
    ]

    payload = json.loads(capsys.readouterr().out)
    assert payload["decision"]["actionable"] == 0
    assert payload["basket"]["status"] == "BLOCKED"
    assert payload["basket"]["assets"] == 0
    assert payload["basket"]["reason"] == "no actionable assets"

    basket_manifest = json.loads(basket_output.with_suffix(".json").read_text(encoding="utf-8"))
    assert basket_manifest["status"] == "BLOCKED"
    assert basket_manifest["rows"] == []
