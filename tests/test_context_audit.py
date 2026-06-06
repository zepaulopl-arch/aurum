from __future__ import annotations

import json
from pathlib import Path

from pymercator.context_audit import (
    audit_context,
    render_context_audit,
    render_context_explain,
    render_context_show,
    write_context_audit,
)


def test_audit_context_detects_missing_macro_fields(tmp_path: Path) -> None:
    context = tmp_path / "latest_market_context.json"
    context.write_text(
        json.dumps(
            {
                "date": "2026-06-06",
                "market_trend": "DOWN",
                "market_volatility": "NORMAL",
                "context_score": 46.9,
                "headline_tags": ["OIL", "RISK_OFF"],
                "notes": "manual context",
            }
        ),
        encoding="utf-8",
    )

    payload = audit_context(context_path=context)

    assert payload["status"] in {"PARTIAL", "WEAK"}
    assert payload["coverage"]["core"] == "OK"
    assert "macro_inflation_rates" in payload["missing_context"]
    assert "copom" in payload["missing_context"]
    assert "commodities" in payload["missing_context"]


def test_audit_context_ok_when_all_coverage_exists(tmp_path: Path) -> None:
    context = tmp_path / "latest_market_context.json"
    context.write_text(
        json.dumps(
            {
                "date": "2026-06-06",
                "market_trend": "DOWN",
                "market_volatility": "NORMAL",
                "context_score": 46.9,
                "headline_tags": ["COPOM", "OIL"],
                "inflation_target": 3.0,
                "inflation_current": 4.2,
                "selic": 10.5,
                "copom_next_meeting": "2026-06-17",
                "oil": {"risk": "HIGH"},
                "earnings_calendar": [{"ticker": "PETR4"}],
                "geopolitical_risk": "MEDIUM",
                "sector_context": {"energy": "watch"},
            }
        ),
        encoding="utf-8",
    )

    payload = audit_context(context_path=context)

    assert payload["status"] == "OK"
    assert payload["missing_context"] == []


def test_context_renderers_have_expected_titles(tmp_path: Path) -> None:
    context = tmp_path / "latest_market_context.json"
    context.write_text(
        json.dumps({"market_trend": "CHOPPY", "market_volatility": "NORMAL"}),
        encoding="utf-8",
    )
    payload = audit_context(context_path=context)

    assert "AURUM CONTEXT AUDIT" in render_context_audit(payload)
    assert "AURUM CONTEXT" in render_context_show(payload)
    assert "AURUM CONTEXT EXPLAIN" in render_context_explain(payload)


def test_write_context_audit(tmp_path: Path) -> None:
    context = tmp_path / "latest_market_context.json"
    context.write_text(json.dumps({"market_trend": "UP"}), encoding="utf-8")
    payload = audit_context(context_path=context)

    output = write_context_audit(payload, tmp_path / "audit.json")

    assert output.exists()
    assert "aurum_context_audit.v1" in output.read_text(encoding="utf-8")
