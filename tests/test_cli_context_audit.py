from __future__ import annotations

import json
from pathlib import Path

from pymercator.cli import main


def _context_file(tmp_path: Path) -> Path:
    context = tmp_path / "context.json"
    context.write_text(
        json.dumps(
            {
                "date": "2026-06-06",
                "market_trend": "DOWN",
                "market_volatility": "NORMAL",
                "context_score": 46.9,
                "headline_tags": ["OIL", "RISK_OFF"],
            }
        ),
        encoding="utf-8",
    )
    return context


def test_context_audit_command(tmp_path: Path, capsys) -> None:
    context = _context_file(tmp_path)

    exit_code = main(["context", "audit", "--context", str(context)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "AURUM CONTEXT AUDIT" in output
    assert "SOURCE STATUS" in output
    assert "macro_inflation_rates" in output


def test_context_show_command(tmp_path: Path, capsys) -> None:
    context = _context_file(tmp_path)

    exit_code = main(["context", "show", "--context", str(context)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "AURUM CONTEXT" in output
    assert "DOWN" in output


def test_context_explain_command(tmp_path: Path, capsys) -> None:
    context = _context_file(tmp_path)

    exit_code = main(["context", "explain", "--context", str(context)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "AURUM CONTEXT EXPLAIN" in output
    assert "Missing coverage" in output


def test_context_audit_json_and_output(tmp_path: Path, capsys) -> None:
    context = _context_file(tmp_path)
    output_path = tmp_path / "context_audit.json"

    exit_code = main(
        [
            "context",
            "audit",
            "--context",
            str(context),
            "--json",
            "--output",
            str(output_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert output_path.exists()
    assert '"schema_version": "aurum_context_audit.v1"' in output
