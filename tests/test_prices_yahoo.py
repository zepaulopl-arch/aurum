from pathlib import Path

from aurum.data.prices_csv import read_price_rows_csv, write_price_rows_csv
from aurum.data.prices_yahoo import fetch_yahoo_prices_to_dir


def _write_cached_price(path: Path, rows: list[dict[str, object]]) -> None:
    write_price_rows_csv(path, rows)


def test_fetch_yahoo_prices_to_dir_uses_cache_when_end_is_covered(
    tmp_path: Path,
    monkeypatch,
):
    _write_cached_price(
        tmp_path / "PRIO3.SA.csv",
        [
            {
                "date": "2025-01-02",
                "open": 10,
                "high": 11,
                "low": 9,
                "close": 10.5,
                "volume": 1000,
            },
            {
                "date": "2025-01-03",
                "open": 11,
                "high": 12,
                "low": 10,
                "close": 11.5,
                "volume": 1200,
            },
        ],
    )

    def fail_fetch(**kwargs):
        raise AssertionError("cache hit should not download")

    monkeypatch.setattr("aurum.data.prices_yahoo.fetch_yahoo_prices", fail_fetch)

    payload = fetch_yahoo_prices_to_dir(
        tickers=["PRIO3.SA"],
        start="2000-01-01",
        end="2025-01-03",
        output_dir=tmp_path,
    )

    assert payload["failed"] == 0
    assert payload["required_failed"] == 0
    assert payload["cache_hits"] == 1
    assert payload["results"][0]["mode"] == "cache_hit"


def test_fetch_yahoo_prices_to_dir_merges_incremental_cache(
    tmp_path: Path,
    monkeypatch,
):
    output = tmp_path / "PRIO3.SA.csv"
    _write_cached_price(
        output,
        [
            {
                "date": "2025-01-02",
                "open": 10,
                "high": 11,
                "low": 9,
                "close": 10.5,
                "volume": 1000,
            }
        ],
    )

    def fake_fetch(**kwargs):
        assert kwargs["start"] == "2025-01-02"
        return [
            {
                "date": "2025-01-02",
                "open": 10,
                "high": 11,
                "low": 9,
                "close": 10.75,
                "volume": 1100,
            },
            {
                "date": "2025-01-03",
                "open": 11,
                "high": 12,
                "low": 10,
                "close": 11.5,
                "volume": 1200,
            },
        ]

    monkeypatch.setattr("aurum.data.prices_yahoo.fetch_yahoo_prices", fake_fetch)

    payload = fetch_yahoo_prices_to_dir(
        tickers=["PRIO3.SA"],
        start="2025-01-02",
        end="2025-01-04",
        output_dir=tmp_path,
    )

    rows = read_price_rows_csv(output)

    assert payload["updated"] == 1
    assert payload["failed"] == 0
    assert [row["date"] for row in rows] == ["2025-01-02", "2025-01-03"]
    assert rows[0]["close"] == "10.75"


def test_fetch_yahoo_prices_to_dir_treats_public_end_as_inclusive(
    tmp_path: Path,
    monkeypatch,
):
    output = tmp_path / "PRIO3.SA.csv"

    def fake_fetch(**kwargs):
        assert kwargs["end"] == "2025-01-05"
        return [
            {
                "date": "2025-01-04",
                "open": 12,
                "high": 13,
                "low": 11,
                "close": 12.5,
                "volume": 1300,
            }
        ]

    monkeypatch.setattr("aurum.data.prices_yahoo.fetch_yahoo_prices", fake_fetch)

    payload = fetch_yahoo_prices_to_dir(
        tickers=["PRIO3.SA"],
        start="2025-01-01",
        end="2025-01-04",
        output_dir=tmp_path,
        use_cache=False,
    )

    rows = read_price_rows_csv(output)

    assert payload["end"] == "2025-01-04"
    assert payload["provider_end"] == "2025-01-05"
    assert [row["date"] for row in rows] == ["2025-01-04"]


def test_fetch_yahoo_prices_to_dir_preserves_cache_on_provider_failure(
    tmp_path: Path,
    monkeypatch,
):
    output = tmp_path / "PRIO3.SA.csv"
    _write_cached_price(
        output,
        [
            {
                "date": "2025-01-02",
                "open": 10,
                "high": 11,
                "low": 9,
                "close": 10.5,
                "volume": 1000,
            }
        ],
    )

    def fail_fetch(**kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr("aurum.data.prices_yahoo.fetch_yahoo_prices", fail_fetch)

    payload = fetch_yahoo_prices_to_dir(
        tickers=["PRIO3.SA"],
        start="2025-01-01",
        end="2025-01-04",
        output_dir=tmp_path,
    )

    rows = read_price_rows_csv(output)

    assert payload["failed"] == 0
    assert payload["cache_fallbacks"] == 1
    assert payload["results"][0]["status"] == "CACHE_FALLBACK"
    assert rows[0]["close"] == "10.5"


def test_fetch_yahoo_prices_to_dir_no_cache_does_not_hide_failure(
    tmp_path: Path,
    monkeypatch,
):
    _write_cached_price(
        tmp_path / "PRIO3.SA.csv",
        [
            {
                "date": "2025-01-02",
                "open": 10,
                "high": 11,
                "low": 9,
                "close": 10.5,
                "volume": 1000,
            }
        ],
    )

    def fail_fetch(**kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr("aurum.data.prices_yahoo.fetch_yahoo_prices", fail_fetch)

    payload = fetch_yahoo_prices_to_dir(
        tickers=["PRIO3.SA"],
        start="2025-01-01",
        end="2025-01-04",
        output_dir=tmp_path,
        use_cache=False,
    )

    assert payload["failed"] == 1
    assert payload["required_failed"] == 1
    assert payload["results"][0]["status"] == "FAILED"
