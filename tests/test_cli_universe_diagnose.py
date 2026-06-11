from pathlib import Path

from aurum.cli import main
from aurum.data.universe_csv import write_universe_template


def test_universe_diagnose_command_prints_report(tmp_path: Path, capsys):
    universe = tmp_path / "template.csv"
    write_universe_template(universe)

    exit_code = main(
        [
            "universe",
            "diagnose",
            "--file",
            str(universe),
        ]
    )

    assert exit_code in {0, 1}

    captured = capsys.readouterr()
    assert "AURUM UNIVERSE DIAGNOSE" in captured.out
    assert "status" in captured.out
    assert "SECTOR WARNING SUMMARY" in captured.out
    assert "TOTAL" in captured.out
    assert "WEAK_TR" in captured.out
    assert "SUMMARY" in captured.out
    assert "WARNINGS BY ASSET" not in captured.out
    assert "SECTOR CONCENTRATION" in captured.out


def test_universe_diagnose_details_prints_asset_warnings(tmp_path: Path, capsys):
    universe = tmp_path / "template.csv"
    write_universe_template(universe)

    exit_code = main(
        [
            "universe",
            "diagnose",
            "--file",
            str(universe),
            "--details",
        ]
    )

    assert exit_code in {0, 1}

    captured = capsys.readouterr()
    assert "SECTOR WARNING SUMMARY" in captured.out
    assert "WARNINGS BY ASSET" in captured.out
    assert "SECTOR CONCENTRATION" in captured.out
