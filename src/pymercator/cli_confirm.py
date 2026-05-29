from __future__ import annotations

import json
from typing import Any

from pymercator.human_confirmation import register_human_confirmation


def run_confirm_command(args: Any) -> int:
    payload = register_human_confirmation(
        pack=args.pack,
        ticker=args.ticker,
        decision=args.decision,
        notes=args.notes,
        operator=args.operator,
        execution_policy_path=args.execution_policy,
    )

    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("PYMERCATOR HUMAN CONFIRMATION")
        print("-" * 100)
        print(f"{'PACK':<20} {payload['pack']}")
        print(f"{'TICKER':<20} {payload['ticker']}")
        print(f"{'DECISION':<20} {payload['human_decision']}")
        print(f"{'FOUND IN PACK':<20} {payload['found_in_pack']}")
        print(f"{'COUNT':<20} {payload['confirmation_count']}")
        print(f"{'MODE':<20} {payload['execution_mode']}")
        print(f"{'JSON':<20} {payload['json_path']}")
        print(f"{'TXT':<20} {payload['txt_path']}")

    return 0
