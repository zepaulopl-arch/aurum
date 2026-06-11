from __future__ import annotations

import json
from typing import Any

from aurum.features_catalog import (
    render_features_catalog,
    validate_features_catalog,
)
from aurum.features_v2 import (
    load_latest_feature_audit,
    render_feature_audit,
    write_features_v2,
)


def run_features_command(args: Any) -> int:
    if args.features_command in {"check", "catalog"}:
        payload = validate_features_catalog(args.file)

        if getattr(args, "json", False):
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(render_features_catalog(payload))

        return 0 if payload["valid"] else 1

    if args.features_command == "build":
        payload = write_features_v2(
            universe=args.universe,
            prices_dir=args.prices_dir,
            context=args.context,
            indices_dir=args.indices_dir,
            config_path=args.config,
            matrix_output=args.output,
            history_output=args.history_output,
            audit_output=args.audit_output,
            feature_list_output=args.feature_list_output,
        )

        if getattr(args, "json", False):
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(render_feature_audit(payload))

        return 0 if payload.get("status") == "OK" else 1

    if args.features_command == "audit":
        payload = load_latest_feature_audit(args.audit)
        if not payload:
            payload = {
                "schema_version": "feature_audit.v2",
                "status": "MISSING",
                "feature_set": "-",
                "features_total": 0,
                "features_after_nan": 0,
                "features_after_corr": 0,
                "features_selected": 0,
                "assets": 0,
                "rows": 0,
                "top_features_by_horizon": {},
            }

        if getattr(args, "json", False):
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(render_feature_audit(payload))

        return 0 if payload.get("status", "OK") != "MISSING" else 1

    raise ValueError(f"Unknown features command: {args.features_command}")
