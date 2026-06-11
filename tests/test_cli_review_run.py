from __future__ import annotations

import json
import os
from pathlib import Path

from aurum.cli_review_run import _ensure_review_report_bridge


def _write_json(path: Path, payload: dict[str, str], mtime: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    os.utime(path, (mtime, mtime))


def test_review_bridge_refreshes_stale_default_profile_report(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    run_dir = Path("storage/runs/latest")
    expected = run_dir / "report_CON.json"
    latest = Path("storage/reports/latest_daily_report.json")
    _write_json(expected, {"id": "old"}, 1000)
    _write_json(latest, {"id": "new"}, 2000)

    bridged = _ensure_review_report_bridge(run_dir, "CON")

    assert bridged == expected
    assert json.loads(expected.read_text(encoding="utf-8")) == {"id": "new"}
    assert int(expected.stat().st_mtime) == 2000


def test_review_bridge_prefers_default_latest_even_when_bridge_mtime_is_newer(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    run_dir = Path("storage/runs/latest")
    expected = run_dir / "report_CON.json"
    latest = Path("storage/reports/latest_daily_report.json")
    _write_json(expected, {"id": "mtime_polluted_bridge"}, 3000)
    _write_json(latest, {"id": "canonical_latest"}, 2000)

    bridged = _ensure_review_report_bridge(run_dir, "CON")

    assert bridged == expected
    assert json.loads(expected.read_text(encoding="utf-8")) == {"id": "canonical_latest"}
    assert int(expected.stat().st_mtime) == 2000


def test_review_bridge_respects_explicit_run_dir_report(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    run_dir = Path("runtime/daily_signal_20260605_120000")
    expected = run_dir / "report_CON.json"
    latest = Path("storage/reports/latest_daily_report.json")
    _write_json(expected, {"id": "explicit"}, 1000)
    _write_json(latest, {"id": "newer_global"}, 2000)

    bridged = _ensure_review_report_bridge(run_dir, "CON")

    assert bridged == expected
    assert json.loads(expected.read_text(encoding="utf-8")) == {"id": "explicit"}
