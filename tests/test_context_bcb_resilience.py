from __future__ import annotations

from pymercator.context_engine.bcb import fetch_bcb_series
from pymercator.context_engine.sources import SourceResult


def test_bcb_series_retries_date_range_when_latest_returns_non_json(monkeypatch) -> None:
    calls: list[str] = []

    def fake_http_get_json(url: str, timeout: float = 12.0) -> SourceResult:
        calls.append(url)
        if "ultimos" in url:
            return SourceResult(
                name="http",
                status="JSON_DECODE_ERROR",
                url=url,
                error="empty body",
            )
        return SourceResult(
            name="http",
            status="OK",
            url=url,
            data=[{"data": "01/06/2026", "valor": "10.50"}],
        )

    monkeypatch.setattr("pymercator.context_engine.bcb.http_get_json", fake_http_get_json)

    result = fetch_bcb_series(432)

    assert result.status == "OK"
    assert result.data[-1]["value"] == 10.5
    assert len(calls) == 2
    assert "ultimos" in calls[0]
    assert "dataInicial" in calls[1]


def test_bcb_series_preserves_both_errors(monkeypatch) -> None:
    def fake_http_get_json(url: str, timeout: float = 12.0) -> SourceResult:
        return SourceResult(name="http", status="ERROR", url=url, error="network down")

    monkeypatch.setattr("pymercator.context_engine.bcb.http_get_json", fake_http_get_json)

    result = fetch_bcb_series(432)

    assert result.status == "ERROR"
    assert "latest=ERROR" in result.error
    assert "date_range=ERROR" in result.error
