"""CLI adapter for context audit/show/explain."""

from __future__ import annotations

import argparse
import json

from pymercator.context_audit import (
    DEFAULT_AUTO_CONTEXT_PATH,
    DEFAULT_CONFIG_PATH,
    DEFAULT_CONTEXT_PATH,
    DEFAULT_THRESHOLDS_PATH,
    audit_context,
    render_context_audit,
    render_context_explain,
    render_context_show,
    write_context_audit,
)


def build_context_audit_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pymercator context")
    subparsers = parser.add_subparsers(dest="context_audit_command", required=True)
    for name in ("audit", "show", "explain"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--context", default=DEFAULT_CONTEXT_PATH)
        sub.add_argument("--auto-context", default=DEFAULT_AUTO_CONTEXT_PATH)
        sub.add_argument("--config", default=DEFAULT_CONFIG_PATH)
        sub.add_argument("--thresholds", default=DEFAULT_THRESHOLDS_PATH)
        sub.add_argument("--output", default="")
        sub.add_argument("--json", action="store_true")
    return parser


def run_context_audit_argv(argv: list[str]) -> int:
    parser = build_context_audit_parser()
    args = parser.parse_args(argv)
    payload = audit_context(
        context_path=args.context,
        auto_context_path=args.auto_context,
        config_path=args.config,
        thresholds_path=args.thresholds,
    )
    if args.output:
        write_context_audit(payload, args.output)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif args.context_audit_command == "show":
        print(render_context_show(payload))
    elif args.context_audit_command == "explain":
        print(render_context_explain(payload))
    else:
        print(render_context_audit(payload))

    return 0 if payload.get("status") not in {"MISSING", "INVALID_JSON", "ERROR"} else 1
