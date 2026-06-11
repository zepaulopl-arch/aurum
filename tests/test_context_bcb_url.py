from __future__ import annotations

from aurum.context_engine.bcb import _date_range_url, fetch_bcb_series
from aurum.context_engine.sources import SourceResult


def test_bcb_date_range_url_keeps_date_slashes_unencoded() -> None:
    url = _date_range_url(432)
    assert "dataInicial=" in url
    assert "dataFinal=" in url
    assert "%2F" not in url
    assert "/dados?formato=json&dataInicial=" in url


def test_bcb_series_uses_unencoded_date_range_on_retry(monkeypatch) -> None:
    calls: list[str] = []

    def fake_http_get_json(url: str, timeout: float = 12.0) -> SourceResult:
        calls.append(url)
        if "ultimos" in url:
            return SourceResult(name="http", status="EMPTY", url=url, error="empty")
        return SourceResult(
            name="http",
            status="OK",
            url=url,
            data=[{"data": "01/06/2026", "valor": "10.50"}],
        )

    monkeypatch.setattr("aurum.context_engine.bcb.http_get_json", fake_http_get_json)

    result = fetch_bcb_series(432)

    assert result.status == "OK"
    assert result.data[-1]["value"] == 10.5
    assert "%2F" not in calls[1]
    assert "dataInicial=" in calls[1]
