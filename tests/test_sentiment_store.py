from aurum.sentiment_store import (
    check_sentiment_dir,
    check_sentiment_file,
)


def test_check_sentiment_file_accepts_daily_csv(tmp_path):
    path = tmp_path / "PETR4_sentiment_daily.csv"
    path.write_text(
        "date,sentiment,news_count\n2025-01-02,0.25,3\n",
        encoding="utf-8",
    )

    payload = check_sentiment_file(path)

    assert payload["valid"] is True
    assert payload["rows"] == 1
    assert payload["ticker"] == "PETR4"


def test_check_sentiment_dir_summarizes_files(tmp_path):
    (tmp_path / "VALE3_sentiment_daily.csv").write_text(
        "date,score\n2025-01-02,0.2\n",
        encoding="utf-8",
    )

    payload = check_sentiment_dir(tmp_path)

    assert payload["exists"] is True
    assert payload["files"] == 1
    assert payload["valid_files"] == 1
    assert payload["tickers"] == 1
