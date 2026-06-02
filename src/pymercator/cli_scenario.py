from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from pymercator.cli_run import run_decision_flow
from pymercator.data.universe_csv import REQUIRED_COLUMNS

POSITIVE_PRESET = "positive_risk_on"

POSITIVE_ASSETS = (
    {
        "ticker": "POSA3",
        "sector": "Energy",
        "last_close": 48.0,
        "trend_score": 88.0,
        "momentum_score": 86.0,
        "quality_score": 82.0,
        "news_score": 76.0,
        "return_5d": 0.055,
    },
    {
        "ticker": "POSB3",
        "sector": "Financial",
        "last_close": 36.0,
        "trend_score": 84.0,
        "momentum_score": 83.0,
        "quality_score": 80.0,
        "news_score": 72.0,
        "return_5d": 0.044,
    },
    {
        "ticker": "POSC3",
        "sector": "Industrial",
        "last_close": 28.0,
        "trend_score": 82.0,
        "momentum_score": 81.0,
        "quality_score": 79.0,
        "news_score": 70.0,
        "return_5d": 0.041,
    },
    {
        "ticker": "POSD3",
        "sector": "Healthcare",
        "last_close": 52.0,
        "trend_score": 79.0,
        "momentum_score": 78.0,
        "quality_score": 83.0,
        "news_score": 69.0,
        "return_5d": 0.038,
    },
    {
        "ticker": "POSE3",
        "sector": "Utilities",
        "last_close": 42.0,
        "trend_score": 77.0,
        "momentum_score": 76.0,
        "quality_score": 81.0,
        "news_score": 68.0,
        "return_5d": 0.035,
    },
)


def _write_csv(
    path: Path,
    fieldnames: list[str] | tuple[str, ...],
    rows: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_prices(path: Path, base_close: float) -> None:
    rows: list[dict[str, Any]] = []
    for day in range(1, 31):
        close = base_close + day * 0.18
        rows.append(
            {
                "date": f"2026-05-{day:02d}",
                "open": round(close - 0.08, 4),
                "high": round(close + 0.42, 4),
                "low": round(close - 0.42, 4),
                "close": round(close, 4),
                "volume": 1_000_000 + day * 1_000,
            }
        )
    _write_csv(path, ["date", "open", "high", "low", "close", "volume"], rows)


def _write_positive_artifacts(output_root: str | Path) -> dict[str, str]:
    root = Path(output_root) / POSITIVE_PRESET
    prices_dir = root / "prices"
    context_dir = root / "context"
    universe = root / "universe.csv"
    matrix = root / "feature_matrix.csv"
    evaluation = root / "evaluation.json"
    context = context_dir / "latest_market_context.json"
    update_status = context_dir / "latest_update_status.json"

    universe_rows: list[dict[str, Any]] = []
    matrix_rows: list[dict[str, Any]] = []
    for asset in POSITIVE_ASSETS:
        entry = float(asset["last_close"])
        stop = round(entry * 0.965, 4)
        target = round(entry * 1.105, 4)
        universe_rows.append(
            {
                "ticker": asset["ticker"],
                "sector": asset["sector"],
                "last_close": entry,
                "avg_volume_brl": 250_000_000,
                "trend_score": asset["trend_score"],
                "momentum_score": asset["momentum_score"],
                "volatility_pct": 14.0,
                "atr_pct": 1.6,
                "liquidity_score": 92.0,
                "quality_score": asset["quality_score"],
                "news_score": asset["news_score"],
                "entry": entry,
                "stop": stop,
                "target": target,
            }
        )
        matrix_rows.append(
            {
                "ticker": asset["ticker"],
                "sector": asset["sector"],
                "momentum_score": asset["momentum_score"],
                "trend_score": asset["trend_score"],
                "news_score": asset["news_score"],
                "return_5d": asset["return_5d"],
                "volatility_20d": 0.11,
                "atr_pct": 1.6,
            }
        )
        _write_prices(prices_dir / f"{asset['ticker']}.csv", entry)

    _write_csv(universe, REQUIRED_COLUMNS, universe_rows)
    _write_csv(
        matrix,
        [
            "ticker",
            "sector",
            "momentum_score",
            "trend_score",
            "news_score",
            "return_5d",
            "volatility_20d",
            "atr_pct",
        ],
        matrix_rows,
    )

    context.parent.mkdir(parents=True, exist_ok=True)
    context.write_text(
        json.dumps(
            {
                "headline_tags": [],
                "market_trend": "UP",
                "market_volatility": "NORMAL",
                "notes": "synthetic positive RISK_ON scenario",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    update_status.write_text(
        json.dumps(
            {
                "status": "OK",
                "impact": "LOW",
                "context_valid": "YES",
                "regime_reliability": "OK",
                "warnings": [],
                "failed_step": "",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    evaluation.write_text(
        json.dumps(
            {
                "engine_used": "multi_horizon_ridge",
                "is_baseline": False,
                "status": "OK",
                "experimental": False,
                "horizons": [5, 20, 60],
                "horizon_observer": {
                    "mode": "weighted",
                    "weights": {"D5": 0.3, "D20": 0.4, "D60": 0.3},
                    "scores": {"D5": 72.0, "D20": 76.0, "D60": 69.0},
                    "combined_score": 72.7,
                    "dominant_horizon": "D20",
                    "behavior": "TREND_CONFIRM",
                },
                "model_quality": {
                    "baseline_accuracy": 0.5,
                    "ensemble_accuracy": 0.64,
                    "edge": 0.14,
                    "precision": 0.66,
                    "recall": 0.62,
                    "false_positive_rate": 0.16,
                    "status": "STRONG",
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "root": str(root),
        "prices_dir": str(prices_dir),
        "context": str(context),
        "universe": str(universe),
        "matrix": str(matrix),
        "evaluation": str(evaluation),
    }


def _load_json(path: str | Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _positive_checks(
    payload: dict[str, Any],
    json_output: str,
    basket_requested: bool,
) -> dict[str, bool]:
    basket = payload.get("basket") or {}
    basket_manifest = (
        Path(str(basket.get("output", ""))).with_suffix(".json")
        if basket.get("output")
        else Path("")
    )
    basket_rows = _load_json(basket_manifest).get("rows", []) if basket.get("output") else []
    report_json = _load_json(json_output)
    top = payload.get("top", [])

    checks = {
        "actionable_positive": payload.get("decision", {}).get("actionable", 0) > 0,
        "top_reasons_clear": bool(top)
        and all(str(row.get("guard", "")) not in {"", "BLOCKED", "UNKNOWN"} for row in top),
        "report_has_prediction": isinstance(report_json.get("prediction"), dict),
        "report_has_model_quality": bool(report_json.get("model_quality")),
        "report_has_blockers": "blockers" in report_json or "blockers_count" in report_json,
    }
    if basket_requested:
        checks.update(
            {
                "basket_ok": basket.get("status") == "OK",
                "basket_assets_positive": int(basket.get("assets", 0) or 0) > 0,
                "basket_has_no_blocked_assets": bool(basket_rows)
                and all(str(row.get("status", "")).upper() != "BLOCKED" for row in basket_rows),
                "report_has_basket": isinstance(report_json.get("basket"), dict),
            }
        )
    return checks


def _render_summary(payload: dict[str, Any]) -> str:
    run = payload["run"]
    decision = run.get("decision", {})
    basket = run.get("basket") or {}
    prediction = run.get("prediction", {})
    quality = prediction.get("model_quality", {})
    lines = [
        (
            f"SCENARIO RUN | PRESET {payload['preset']} | "
            f"PROFILE {payload['profile']} | STATUS {payload['status']}"
        ),
        "",
        "MARKET:",
        f"- regime: {run.get('market', {}).get('regime', '-')}",
        "",
        "PREDICTION:",
        f"- engine: {prediction.get('engine_used', '-')}",
        f"- behavior: {prediction.get('behavior', '-')}",
        f"- dominant_horizon: {prediction.get('dominant_horizon', '-')}",
        f"- combined_score: {prediction.get('combined_score', '-')}",
        "",
        "MODEL QUALITY:",
        f"- status: {quality.get('status', '-')}",
        f"- edge: {quality.get('edge', '-')}",
        "",
        "DECISION:",
        f"- actionable: {decision.get('actionable', 0)}",
        f"- watch: {decision.get('watch', 0)}",
        f"- blocked: {decision.get('blocked', 0)}",
        "",
        "BASKET:",
        f"- status: {basket.get('status', '-')}",
        f"- assets: {basket.get('assets', 0)}",
        "",
        "TOP:",
    ]
    for index, item in enumerate(run.get("top", []), start=1):
        lines.append(
            f"{index}. {item['ticker']} | {item['decision']} | "
            f"{item['score']} | {item['guard']} | "
            f"{item.get('dominant_horizon', '-')} {item.get('behavior', '-')}"
        )
    lines.extend(["", "CHECKS:"])
    for name, passed in payload["checks"].items():
        lines.append(f"- {name}: {'PASS' if passed else 'FAIL'}")
    lines.extend(
        [
            "",
            "FILES:",
            f"- report_json: {payload['files']['json']}",
            f"- basket: {payload['files']['basket']}",
            f"- scenario_root: {payload['artifacts']['root']}",
        ]
    )
    return "\n".join(lines)


def run_scenario_command(args: Any) -> int:
    if getattr(args, "scenario_command", "") != "run":
        print("ERROR: missing scenario subcommand. Valid: run")
        return 1

    preset = str(args.preset).strip().lower()
    if preset != POSITIVE_PRESET:
        print(f"ERROR: Unknown scenario preset: {args.preset}")
        print(f"Valid presets: {POSITIVE_PRESET}")
        return 1

    artifacts = _write_positive_artifacts(args.output_root)
    run_payload = run_decision_flow(
        profile=args.profile,
        list_name="POSITIVE_RISK_ON",
        policy=args.policy,
        universe=artifacts["universe"],
        context=artifacts["context"],
        matrix=artifacts["matrix"],
        evaluation=artifacts["evaluation"],
        prices_dir=artifacts["prices_dir"],
        limit=args.limit,
        run_dir=args.run_dir,
        report_output=args.report_output,
        json_output=args.json_output,
        basket=args.basket,
        slots=args.slots,
        min_sectors=args.min_sectors,
        min_weight=args.min_weight,
        capital=args.capital,
        risk_per_trade=args.risk_per_trade,
        basket_output=args.basket_output,
    )
    checks = _positive_checks(run_payload, args.json_output, args.basket)
    status = "OK" if run_payload.get("status") == "OK" and all(checks.values()) else "FAIL"
    payload = {
        "command": "scenario run",
        "preset": preset,
        "profile": args.profile,
        "status": status,
        "checks": checks,
        "artifacts": artifacts,
        "files": run_payload.get("files", {}),
        "run": run_payload,
    }

    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(_render_summary(payload))

    return 0 if status == "OK" else 1
