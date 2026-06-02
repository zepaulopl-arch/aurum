import json
from pathlib import Path

from pymercator.cli import main
from pymercator.ui import colorize, set_color_mode, short_sector, strip_ansi
from pymercator.ui.colors import ANSI_RE


def test_color_flags_control_terminal_output(capsys) -> None:
    exit_code = main(["diag", "--color", "always"])

    assert exit_code == 0
    assert "\x1b[" in capsys.readouterr().out

    exit_code = main(["diag", "--no-color"])

    assert exit_code == 0
    assert "\x1b[" not in capsys.readouterr().out


def test_strip_ansi_and_status_classes() -> None:
    blocked = colorize("BLOCKED", "BLOCKED", enabled=True)
    ok = colorize("OK", "OK", enabled=True)

    assert "\x1b[" in blocked
    assert "\x1b[" in ok
    assert strip_ansi(blocked) == "BLOCKED"
    assert strip_ansi(ok) == "OK"


def test_sector_abbreviations_are_stable() -> None:
    assert short_sector("consumer_discretionary") == "consumer_disc."
    assert short_sector("consumer_staples") == "consumer_stap."
    assert short_sector("communication") == "comm."
    assert short_sector("health_care") == "health"


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
