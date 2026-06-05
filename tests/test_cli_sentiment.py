from pathlib import Path

from pymercator.cli import main


def test_sentiment_check_command(tmp_path: Path, capsys):
    (tmp_path / "PETR4_SA_sentiment_daily.csv").write_text(
        "date,sentiment_score\n2025-01-02,0.1\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "sentiment",
            "check",
            "--sentiment-dir",
            str(tmp_path),
        ]
    )

    assert exit_code == 0

    captured = capsys.readouterr()
    assert "PYMERCATOR SENTIMENT CHECK" in captured.out
    assert "VALID FILES" in captured.out
    assert "PETR4.SA" in captured.out
