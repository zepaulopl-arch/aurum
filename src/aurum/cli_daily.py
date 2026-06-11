from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from aurum.pipeline import run_daily_pipeline
from aurum.reports.json_report import write_daily_report_json
from aurum.reports.terminal import render_daily_report


def make_timestamped_run_dir(base_dir: str | Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_path = Path(base_dir)
    candidate = base_path / stamp
    suffix = 1

    while candidate.exists():
        candidate = base_path / f"{stamp}_{suffix:02d}"
        suffix += 1

    candidate.mkdir(parents=True, exist_ok=False)
    return candidate


def run_daily_command(
    *,
    args: Any,
    resolved_output: str,
    json_output: str,
    resolved_run_dir: str,
    context_values: dict[str, Any],
) -> int:
    report = run_daily_pipeline(
        universe_path=args.universe,
        universe_name=args.universe_name,
        profile=args.profile,
        headline_risk=args.headline_risk,
        headline_tags=context_values["headline_tags"],
        market_trend=context_values["market_trend"],
        market_volatility=context_values["market_volatility"],
        policy_path=args.policy,
    )

    rendered = render_daily_report(report, limit=args.limit)

    if resolved_output:
        # write resolved_output created by caller
        Path(resolved_output).parent.mkdir(parents=True, exist_ok=True)
        Path(resolved_output).write_text(rendered, encoding="utf-8")

    if json_output:
        write_daily_report_json(report, json_output)

    run_path: Path | None = None
    if resolved_run_dir:
        run_path = make_timestamped_run_dir(resolved_run_dir)
        (run_path / "report.txt").write_text(rendered, encoding="utf-8")
        write_daily_report_json(report, run_path / "report.json")

    print(rendered)

    if run_path:
        print("")
        print(f"RUN DIR              {run_path}")

    return 0
