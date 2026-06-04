from __future__ import annotations

import json
from typing import Any

from pymercator.observation import (
    calibrate_observation_thresholds,
    render_observation_report,
    run_observation,
)


def run_observe_command(args: Any) -> int:
    if getattr(args, "observe_command", "run") == "calibrate":
        payload = calibrate_observation_thresholds(
            universe=args.universe,
            list_name=args.list,
            config_path=args.config,
            output=getattr(args, "output", ""),
        )
        if getattr(args, "json", False):
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print("OBSERVATION CALIBRATION")
            print("-" * 80)
            print(f"{'LIST':<18} {payload['list']}")
            print(f"{'UNIVERSE':<18} {payload['universe']}")
            print(f"{'ASSETS':<18} {payload['asset_count']}")
            print(f"{'OUTPUT':<18} {payload.get('output', '-')}")
            print("")
            print("THRESHOLDS")
            print("-" * 80)
            for key, value in payload["thresholds"].items():
                print(f"{key:<24} {float(value):>7.2f}")
        return 0

    payload = run_observation(
        universe=args.universe,
        list_name=args.list,
        config_path=args.config,
        limit=args.limit,
        cluster=bool(getattr(args, "cluster", False)),
    )

    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_observation_report(payload, limit=args.limit))
    return 0
