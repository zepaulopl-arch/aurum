from __future__ import annotations

import json
from pathlib import Path

from pymercator.context_engine.builder import build_market_context
from pymercator.context_engine.macro_manual import load_macro_manual, macro_value


def test_load_macro_manual_values(tmp_path: Path) -> None:
    path = tmp_path / "macro.csv"
    path.write_text(
        "name,value,source,updated_at\n"
        "inflation_target,3.0,LOCAL_MANUAL,2026-06-06\n"
        "inflation_expectation,4.2,LOCAL_MANUAL,2026-06-06\n"
        "selic_target,10.5,LOCAL_MANUAL,2026-06-06\n",
        encoding="utf-8",
    )

    result = load_macro_manual(path)

    assert result.status == "OK"
    assert macro_value(result.data, "inflation_target") == 3.0
    assert macro_value(result.data, "inflation_expectation") == 4.2
    assert macro_value(result.data, "selic_target") == 10.5


def test_build_context_uses_macro_manual_when_offline(tmp_path: Path) -> None:
    existing = tmp_path / "existing.json"
    existing.write_text(json.dumps({"market_trend": "DOWN", "market_volatility": "NORMAL"}), encoding="utf-8")

    macro = tmp_path / "macro.csv"
    macro.write_text(
        "name,value,source,updated_at\n"
        "inflation_target,3.0,LOCAL_MANUAL,2026-06-06\n"
        "inflation_expectation,4.2,LOCAL_MANUAL,2026-06-06\n"
        "selic_target,10.5,LOCAL_MANUAL,2026-06-06\n",
        encoding="utf-8",
    )

    copom = tmp_path / "copom.csv"
    copom.write_text("date,event,source\n2099-06-17,COPOM,LOCAL\n", encoding="utf-8")
    commodities = tmp_path / "commodities.csv"
    commodities.write_text("name,value,change_pct,risk,source,updated_at\noil,80,0,HIGH,LOCAL,2026-06-06\n", encoding="utf-8")
    earnings = tmp_path / "earnings.csv"
    earnings.write_text("date,ticker,event,risk,source\n", encoding="utf-8")
    geo = tmp_path / "geo.json"
    geo.write_text(json.dumps({"geopolitical_risk": "MEDIUM"}), encoding="utf-8")
    sector = tmp_path / "sector.json"
    sector.write_text(json.dumps({"energy": "WATCH"}), encoding="utf-8")

    payload = build_market_context(
        output=tmp_path / "ctx.json",
        existing_context_path=existing,
        use_network=False,
        macro_manual_csv=macro,
        copom_csv=copom,
        commodities_csv=commodities,
        earnings_csv=earnings,
        geopolitical_json=geo,
        sector_json=sector,
    )

    assert payload["source_status"]["macro_manual"] == "OK"
    assert payload["inflation"]["target"] == 3.0
    assert payload["inflation"]["expectation"] == 4.2
    assert payload["inflation"]["bias"] == "ABOVE_TARGET"
    assert payload["rates"]["selic"] == 10.5
    assert payload["rates"]["selic_source"] == "macro_manual"
