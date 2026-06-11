from __future__ import annotations

from aurum.context_engine.inflation import fetch_focus_expectations


def test_focus_url_has_no_spaces_when_network_fails_or_succeeds(monkeypatch) -> None:
    captured = {}

    def fake_http_get_json(url: str, timeout: float = 12.0):
        captured["url"] = url
        from aurum.context_engine.sources import SourceResult

        return SourceResult(name="http", status="MISSING", data={"value": []}, url=url)

    monkeypatch.setattr("aurum.context_engine.inflation.http_get_json", fake_http_get_json)

    fetch_focus_expectations(reference_year=2026)

    assert " " not in captured["url"]
    assert "%24orderby=Data%20desc" in captured["url"] or "$orderby=Data%20desc" in captured["url"]
