from __future__ import annotations

import json
from pathlib import Path

import pytest

import aurum.core as core
from aurum.cli import main


ROOT = Path(__file__).resolve().parents[1]


def _raw_payload() -> dict:
    signal_ts = "2026-06-05T12:00:00Z"
    return {
        "status": "OK",
        "profile": "CON",
        "list": "IBOV",
        "report": {
            "decisions": [
                {
                    "asset": {"ticker": "LONG1", "last_close": 100.0},
                    "permission": {"status": "READY"},
                    "ranking": {"context_score": 88.0},
                    "ref_price": 100.0,
                    "ref_date": "2026-06-05",
                    "ref_ts": signal_ts,
                    "reason": "ready long",
                },
                {
                    "asset": {"ticker": "OBS1", "last_close": 50.0},
                    "permission": {"status": "BLOCKED"},
                    "ranking": {"context_score": 74.0},
                    "ref_price": 50.0,
                    "ref_date": "2026-06-05",
                    "ref_ts": signal_ts,
                    "blocker_reasons": ["MODEL_WEAK"],
                },
            ]
        },
        "observation_candidates": [
            {
                "ticker": "OBS2",
                "score": 71.0,
                "class": "OBS_FAVORABLE",
                "reason": "watch long",
                "ref_price": 20.0,
                "ref_date": "2026-06-05",
                "ref_ts": signal_ts,
            }
        ],
        "short_candidates": [
            {
                "ticker": "SHORT1",
                "score": 91.0,
                "short_permission": "SHORT_READY",
                "executable": True,
                "reason": "ready short",
                "ref_price": 40.0,
                "ref_date": "2026-06-05",
                "ref_ts": signal_ts,
            },
            {
                "ticker": "SOBS1",
                "score": 66.0,
                "short_permission": "SHORT_BLOCKED",
                "executable": False,
                "reason": "borrow missing",
                "ref_price": 30.0,
                "ref_date": "2026-06-05",
                "ref_ts": signal_ts,
            },
        ],
        "short_observation_candidates": [
            {
                "ticker": "SOBS2",
                "score": 70.0,
                "short_permission": "SHORT_BLOCKED",
                "executable": False,
                "reason": "watch short",
                "ref_price": 10.0,
                "ref_date": "2026-06-05",
                "ref_ts": signal_ts,
            }
        ],
    }


def _write_price(prices_dir: Path, ticker: str, latest: float) -> None:
    prices_dir.mkdir(parents=True, exist_ok=True)
    (prices_dir / f"{ticker}.SA.csv").write_text(
        "\n".join(
            [
                "date,open,high,low,close,volume",
                f"2026-06-05,{latest},{latest},{latest},{latest},1000",
                f"2026-06-08,{latest},{latest},{latest},{latest},1000",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _daily(tmp_path: Path) -> dict:
    return core.run_daily(
        profile="CON",
        list_name="IBOV",
        capital=100000.0,
        slots=10,
        signal_date="2026-06-05",
        signals_dir=tmp_path / "signals",
        update=False,
        force=False,
        raw_payload=_raw_payload(),
    )


def _review(tmp_path: Path) -> dict:
    _daily(tmp_path)
    prices_dir = tmp_path / "prices"
    _write_price(prices_dir, "LONG1", 110.0)
    _write_price(prices_dir, "OBS1", 55.0)
    _write_price(prices_dir, "OBS2", 22.0)
    _write_price(prices_dir, "SHORT1", 36.0)
    _write_price(prices_dir, "SOBS1", 33.0)
    _write_price(prices_dir, "SOBS2", 9.0)
    return core.run_review(
        profile="CON",
        list_name="IBOV",
        review_date="2026-06-08",
        signals_dir=tmp_path / "signals",
        prices_dir=prices_dir,
    )


def test_daily_outputs_four_tables(tmp_path: Path) -> None:
    snapshot = _daily(tmp_path)

    assert set(snapshot["tables"]) == set(core.TABLE_KEYS)
    assert [row["ticker"] for row in snapshot["tables"]["real_long"]] == ["LONG1"]
    assert [row["ticker"] for row in snapshot["tables"]["real_short"]] == ["SHORT1"]
    assert {row["ticker"] for row in snapshot["tables"]["obs_long"]} == {"OBS1", "OBS2"}
    assert {row["ticker"] for row in snapshot["tables"]["obs_short"]} == {"SOBS1", "SOBS2"}


def test_daily_saves_immutable_snapshot(tmp_path: Path) -> None:
    snapshot = _daily(tmp_path)
    path = Path(snapshot["files"]["snapshot_json"])

    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == "aurum_signal_snapshot.v1"
    with pytest.raises(FileExistsError):
        _daily(tmp_path)


def test_review_loads_previous_market_day_snapshot(tmp_path: Path) -> None:
    review = _review(tmp_path)

    assert review["signal_date"] == "2026-06-05"
    assert review["review_date"] == "2026-06-08"
    assert review["signal_source_file"].endswith("CON_IBOV_signal.json")


def test_review_reviews_real_long(tmp_path: Path) -> None:
    review = _review(tmp_path)
    row = review["tables"]["real_long"][0]

    assert row["ticker"] == "LONG1"
    assert row["pnl"] == 1000.0
    assert row["would_pnl"] is None


def test_review_reviews_real_short(tmp_path: Path) -> None:
    review = _review(tmp_path)
    row = review["tables"]["real_short"][0]

    assert row["ticker"] == "SHORT1"
    assert row["pnl"] == 1000.0
    assert row["would_pnl"] is None


def test_review_reviews_obs_long(tmp_path: Path) -> None:
    review = _review(tmp_path)
    rows = {row["ticker"]: row for row in review["tables"]["obs_long"]}

    assert rows["OBS2"]["would_pnl"] == 1000.0
    assert rows["OBS2"]["pnl"] is None


def test_review_reviews_obs_short(tmp_path: Path) -> None:
    review = _review(tmp_path)
    rows = {row["ticker"]: row for row in review["tables"]["obs_short"]}

    assert rows["SOBS2"]["would_pnl"] == 1000.0
    assert rows["SOBS2"]["pnl"] is None


def test_review_does_not_mix_real_and_obs(tmp_path: Path) -> None:
    review = _review(tmp_path)

    assert review["summary"]["real_long"]["real_pnl"] == 1000.0
    assert review["summary"]["obs_long"]["real_pnl"] == 0.0
    assert review["summary"]["real_short"]["would_pnl"] == 0.0
    assert review["summary"]["obs_short"]["would_pnl"] == 0.0


def test_review_uses_per_slot_sizing(tmp_path: Path) -> None:
    review = _review(tmp_path)

    for rows in review["tables"].values():
        for row in rows:
            assert row["notional"] == 10000.0
            assert row["sizing_mode"] == "per_slot"


def test_review_shows_empty_tables_explicitly(tmp_path: Path) -> None:
    snapshot = core.run_daily(
        profile="CON",
        list_name="IBOV",
        signal_date="2026-06-05",
        signals_dir=tmp_path / "signals",
        update=False,
        raw_payload={"status": "OK", "report": {"decisions": []}},
    )

    assert snapshot["text"].count("NO ITEMS") == 4
    for title in core.TABLE_TITLES.values():
        assert title in snapshot["text"]


def test_weekly_evaluates_features(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(core, "update_data", lambda **kwargs: {"status": "OK"})
    monkeypatch.setattr(core, "build_features", lambda payload: {"status": "OK", "rows": 10})
    monkeypatch.setattr(core, "train_models", lambda **kwargs: {"status": "OK"})
    monkeypatch.setattr(core, "evaluate_features", lambda record=False: {"status": "OPERABLE", "verdict": "BETTER"})
    monkeypatch.setattr(core, "evaluate_engines", lambda: {"best_engine": "ridge", "most_reliable_horizon": "D20"})

    payload = core.run_weekly(output=tmp_path / "weekly.txt")

    assert payload["feature_audit"]["status"] == "OPERABLE"
    assert "FEATURE AUDIT" in payload["text"]


def test_weekly_evaluates_engines(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(core, "update_data", lambda **kwargs: {"status": "OK"})
    monkeypatch.setattr(core, "build_features", lambda payload: {"status": "OK", "rows": 10})
    monkeypatch.setattr(core, "train_models", lambda **kwargs: {"status": "OK"})
    monkeypatch.setattr(core, "evaluate_features", lambda record=False: {"status": "OPERABLE", "verdict": "BETTER"})
    monkeypatch.setattr(core, "evaluate_engines", lambda: {"best_engine": "extratrees", "most_reliable_horizon": "D5"})

    payload = core.run_weekly(output=tmp_path / "weekly.txt")

    assert payload["engine_audit"]["best_engine"] == "extratrees"
    assert "ENGINE AUDIT" in payload["text"]


def test_commands_call_core_functions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    calls: dict[str, dict] = {}

    def fake_daily(**kwargs):
        calls["daily"] = kwargs
        return {"text": "CORE DAILY\n"}

    def fake_review(**kwargs):
        calls["review"] = kwargs
        return {"text": "CORE REVIEW\n"}

    def fake_weekly(**kwargs):
        calls["weekly"] = kwargs
        return {"text": "CORE WEEKLY\n"}

    monkeypatch.setattr(core, "run_daily", fake_daily)
    monkeypatch.setattr(core, "run_review", fake_review)
    monkeypatch.setattr(core, "run_weekly", fake_weekly)

    assert main(["daily", "--no-update", "--signals-dir", str(tmp_path / "signals")]) == 0
    assert main(["review", "--signals-dir", str(tmp_path / "signals")]) == 0
    assert main(["weekly", "--no-update", "--no-train", "--output", str(tmp_path / "weekly.txt")]) == 0

    output = capsys.readouterr().out
    assert "CORE DAILY" in output
    assert "CORE REVIEW" in output
    assert "CORE WEEKLY" in output
    assert calls["daily"]["update"] is False
    assert calls["review"]["signals_dir"] == str(tmp_path / "signals")
    assert calls["weekly"]["train"] is False

    for script in ("daily_signal.ps1", "daily_review.ps1", "weekly_train.ps1"):
        text = (ROOT / "scripts" / script).read_text(encoding="utf-8")
        assert "from aurum.core import" in text
        assert "python -m aurum" not in text
        assert "-m aurum" not in text
