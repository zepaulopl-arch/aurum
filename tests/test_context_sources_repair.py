from __future__ import annotations
import json
from pathlib import Path
from aurum.context_engine.builder import build_market_context
from aurum.context_engine.market_data import fetch_yahoo_quote
from aurum.context_engine.sources import SourceResult

def _local_files(tmp_path: Path) -> dict[str, Path]:
    macro = tmp_path / "macro.csv"
    macro.write_text("name,value,source,updated_at\ninflation_target,3.0,LOCAL_MANUAL,2026-06-06\ninflation_expectation,4.2,LOCAL_MANUAL,2026-06-06\nselic_target,10.5,LOCAL_MANUAL,2026-06-06\n", encoding="utf-8")
    copom = tmp_path / "copom.csv"; copom.write_text("date,event,source\n2099-06-17,COPOM,LOCAL\n", encoding="utf-8")
    earnings = tmp_path / "earnings.csv"; earnings.write_text("date,ticker,event,risk,source\n", encoding="utf-8")
    geo = tmp_path / "geo.json"; geo.write_text(json.dumps({"geopolitical_risk":"MEDIUM", "oil_war_risk":"HIGH"}), encoding="utf-8")
    sector = tmp_path / "sector.json"; sector.write_text(json.dumps({"energy":"WATCH"}), encoding="utf-8")
    existing = tmp_path / "existing.json"; existing.write_text(json.dumps({"market_trend":"DOWN", "market_volatility":"NORMAL"}), encoding="utf-8")
    return {"macro":macro, "copom":copom, "earnings":earnings, "geo":geo, "sector":sector, "existing":existing}

def test_builder_uses_manual_macro_and_skips_network_offline(tmp_path: Path) -> None:
    p = _local_files(tmp_path)
    payload = build_market_context(output=tmp_path/"ctx.json", existing_context_path=p["existing"], use_network=False, macro_manual_csv=p["macro"], copom_csv=p["copom"], earnings_csv=p["earnings"], geopolitical_json=p["geo"], sector_json=p["sector"])
    assert payload["source_status"]["market_public_yahoo"] == "SKIPPED"
    assert payload["source_status"]["macro_manual"] == "OK"
    assert payload["inflation"]["bias"] == "ABOVE_TARGET"
    assert payload["rates"]["selic"] == 10.5
    assert payload["commodities"]["oil_risk"] == "HIGH"

def test_yahoo_quote_parser(monkeypatch) -> None:
    def fake_http_get_json(url: str, timeout: float = 12.0) -> SourceResult:
        return SourceResult("http", "OK", {"chart":{"result":[{"meta":{"currency":"USD", "exchangeName":"NYM"}, "indicators":{"quote":[{"close":[80.0,82.4]}]}}], "error":None}}, url=url)
    monkeypatch.setattr("aurum.context_engine.market_data.http_get_json", fake_http_get_json)
    result = fetch_yahoo_quote("CL=F")
    assert result.status == "OK"
    assert result.data["change_pct"] == 3.0
    assert result.data["source"] == "YAHOO_CHART"
