from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

COLOR_MODE = "auto"
PALETTE_NAME = ""
UI_CONFIG_PATH = Path("config/ui.json")

RESET = "\x1b[0m"

DEFAULT_PALETTES = {
    "soft": {
        "green": "\x1b[38;5;71m",
        "yellow": "\x1b[38;5;179m",
        "red": "\x1b[38;5;167m",
        "gray": "\x1b[38;5;245m",
        "header": "\x1b[38;5;110m",
        "number": "\x1b[38;5;250m",
    },
    "bright": {
        "green": "\x1b[38;5;77m",
        "yellow": "\x1b[38;5;221m",
        "red": "\x1b[38;5;203m",
        "gray": "\x1b[38;5;248m",
        "header": "\x1b[38;5;117m",
        "number": "\x1b[38;5;255m",
    },
    "classic": {
        "green": "\x1b[32m",
        "yellow": "\x1b[33m",
        "red": "\x1b[31m",
        "gray": "\x1b[90m",
        "header": "\x1b[36m",
        "number": "\x1b[37m",
    },
}
DEFAULT_METRIC_THRESHOLDS = {
    "trend": [
        {"min": 60.0, "status": "OK"},
        {"min": 45.0, "status": "WATCH"},
        {"status": "WEAK"},
    ],
    "mom": [
        {"min": 60.0, "status": "OK"},
        {"min": 45.0, "status": "WATCH"},
        {"status": "WEAK"},
    ],
    "vol": [
        {"min": 80.0, "status": "HIGH"},
        {"min": 55.0, "status": "WATCH"},
        {"status": "NORMAL"},
    ],
    "atr": [
        {"min": 8.0, "status": "HIGH"},
        {"status": "NORMAL"},
    ],
    "accuracy": [
        {"min": 0.58, "status": "OK"},
        {"min": 0.52, "status": "WATCH"},
        {"status": "WEAK"},
    ],
    "precision": [
        {"min": 0.55, "status": "OK"},
        {"min": 0.50, "status": "WATCH"},
        {"status": "WEAK"},
    ],
    "recall": [
        {"min": 0.55, "status": "OK"},
        {"min": 0.50, "status": "WATCH"},
        {"status": "WEAK"},
    ],
    "edge": [
        {"min": 0.02, "status": "OK"},
        {"min": 0.0, "status": "WATCH"},
        {"status": "WEAK"},
    ],
    "false_positive_rate": [
        {"max": 0.20, "status": "OK"},
        {"max": 0.35, "status": "WATCH"},
        {"status": "WEAK"},
    ],
    "false_negative_rate": [
        {"max": 0.20, "status": "OK"},
        {"max": 0.35, "status": "WATCH"},
        {"status": "WEAK"},
    ],
    "combined_score": [
        {"min": 60.0, "status": "OK"},
        {"min": 50.0, "status": "WATCH"},
        {"status": "WEAK"},
    ],
    "mae_return": [
        {"max": 0.01, "status": "OK"},
        {"max": 0.03, "status": "WATCH"},
        {"status": "WEAK"},
    ],
    "target_up_rate": [
        {"min": 0.0, "status": "NORMAL"},
    ],
    "predicted_up_rate": [
        {"min": 0.0, "status": "NORMAL"},
    ],
}
DEFAULT_METRIC_ALIASES = {
    "trend_score": "trend",
    "trend": "trend",
    "tr": "trend",
    "mom": "mom",
    "momentum": "mom",
    "momentum_score": "mom",
    "weak_mom": "mom",
    "vol": "vol",
    "volatility": "vol",
    "volatility_pct": "vol",
    "vol_high": "vol",
    "atr": "atr",
    "atr_pct": "atr",
    "qtr": "atr",
    "atr_high": "atr",
    "accuracy": "accuracy",
    "best_accuracy": "accuracy",
    "baseline_accuracy": "accuracy",
    "ensemble_accuracy": "accuracy",
    "precision": "precision",
    "prec": "precision",
    "recall": "recall",
    "edge": "edge",
    "model_edge": "edge",
    "false_positive_rate": "false_positive_rate",
    "fpr": "false_positive_rate",
    "false_negative_rate": "false_negative_rate",
    "fnr": "false_negative_rate",
    "mae": "mae_return",
    "mae_return": "mae_return",
    "combined_score": "combined_score",
    "score": "combined_score",
    "target_up_rate": "target_up_rate",
    "predicted_up_rate": "predicted_up_rate",
}

GREEN = {
    "OK",
    "READY",
    "ACTIONABLE",
    "RISK_ON",
    "STRONG",
    "PASS",
    "LOW",
    "TRUE",
    "AVAILABLE",
    "TREND_CONFIRM",
    "SWING",
    "POSITIONAL_SETUP",
    "TACTICAL",
}
YELLOW = {
    "WATCH",
    "CAUTION",
    "PARTIAL",
    "DEGRADED",
    "MEDIUM",
    "MIXED",
    "SWING_WAIT",
    "POSITIONAL_EARLY",
    "DIVERGENT",
    "PASS_WITH_WARNINGS",
    "VOLATILE",
    "VOL+WEAK",
}
RED = {
    "BLOCKED",
    "FAIL",
    "FAILED",
    "RISK_OFF",
    "HIGH",
    "WEAK",
    "DEGENERATE",
    "AVOID",
    "WARN_SMALL_UNIVERSE",
    "MODEL_WEAK",
    "BEHAVIOR_AVOID",
    "UNAVAILABLE",
}
GRAY = {
    "NORMAL",
    "NEUTRAL",
    "REJECTED",
    "FALSE",
    "NONE",
    "-",
}


def set_color_mode(mode: str | None) -> None:
    global COLOR_MODE
    normalized = str(mode or "auto").strip().lower()
    if normalized not in {"auto", "always", "never"}:
        normalized = "auto"
    COLOR_MODE = normalized


def _load_ui_config() -> dict[str, Any]:
    try:
        payload = json.loads(UI_CONFIG_PATH.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _configured_palettes() -> dict[str, dict[str, str]]:
    palettes = {key: dict(value) for key, value in DEFAULT_PALETTES.items()}
    configured = _load_ui_config().get("palettes", {})
    if not isinstance(configured, dict):
        return palettes
    for name, palette in configured.items():
        if isinstance(palette, dict):
            merged = dict(palettes.get(str(name), {}))
            merged.update({str(key): str(value) for key, value in palette.items()})
            palettes[str(name)] = merged
    return palettes


def available_palettes() -> list[str]:
    return sorted(_configured_palettes())


def _default_palette_name() -> str:
    configured = str(_load_ui_config().get("default_palette", "soft")).strip().lower()
    return configured or "soft"


def set_palette(name: str | None) -> None:
    global PALETTE_NAME
    requested = str(name or "").strip().lower()
    if not requested:
        PALETTE_NAME = ""
        return
    PALETTE_NAME = requested if requested in _configured_palettes() else _default_palette_name()


def set_ui_config_path(path: str | Path | None) -> None:
    global UI_CONFIG_PATH
    UI_CONFIG_PATH = Path(path or "config/ui.json")


def _active_palette() -> dict[str, str]:
    palettes = _configured_palettes()
    requested = (
        PALETTE_NAME
        or os.environ.get("AURUM_PALETTE", "")
        or _default_palette_name()
    )
    name = str(requested).strip().lower()
    return palettes.get(name, palettes.get("soft", DEFAULT_PALETTES["soft"]))


def color_enabled(enabled: bool | None = None) -> bool:
    if enabled is not None:
        return bool(enabled)
    if COLOR_MODE == "always":
        return True
    if COLOR_MODE == "never":
        return False
    return bool(getattr(sys.stdout, "isatty", lambda: False)())


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", str(text))


def _class_for_status(status: object) -> str:
    key = str(status or "").strip().upper()
    if key in GREEN:
        return "green"
    if key in YELLOW:
        return "yellow"
    if key in RED:
        return "red"
    if key in GRAY:
        return "gray"
    return "gray"


def colorize(text: object, status: object | None = None, enabled: bool | None = None) -> str:
    value = str(text)
    if not color_enabled(enabled):
        return value
    style = _active_palette()[_class_for_status(status if status is not None else text)]
    return f"{style}{value}{RESET}"


def colorize_value(value: Any, *, role: str = "", enabled: bool | None = None) -> str:
    text = str(value)
    if not color_enabled(enabled):
        return text
    key = str(role or value or "").strip().upper()
    if key == "HEADER":
        return f"{_active_palette()['header']}{text}{RESET}"
    if key == "NUMBER":
        return f"{_active_palette()['number']}{text}{RESET}"
    if key in {"LABEL", "PATH", "FALSE"}:
        return f"{_active_palette()['gray']}{text}{RESET}"
    return colorize(text, key, enabled=True)


def _to_float(value: object) -> float:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def _metric_key(metric: str) -> str:
    name = str(metric or "").strip().lower()
    return _configured_metric_aliases().get(name, name)


def _configured_metric_aliases() -> dict[str, str]:
    aliases = dict(DEFAULT_METRIC_ALIASES)
    configured = _load_ui_config().get("metric_aliases", {})
    if not isinstance(configured, dict):
        return aliases
    for alias, canonical in configured.items():
        alias_text = str(alias).strip().lower()
        canonical_text = str(canonical).strip().lower()
        if alias_text and canonical_text:
            aliases[alias_text] = canonical_text
    return aliases


def _configured_metric_thresholds() -> dict[str, list[dict[str, Any]]]:
    thresholds = {
        key: [dict(rule) for rule in rules]
        for key, rules in DEFAULT_METRIC_THRESHOLDS.items()
    }
    configured = _load_ui_config().get("metric_thresholds", {})
    if not isinstance(configured, dict):
        return thresholds
    for metric, rules in configured.items():
        if isinstance(rules, list):
            thresholds[_metric_key(str(metric))] = [
                dict(rule)
                for rule in rules
                if isinstance(rule, dict)
            ]
    return thresholds


def _rule_matches(rule: dict[str, Any], number: float) -> bool:
    if "min" in rule and number < _to_float(rule["min"]):
        return False
    if "max" in rule and number > _to_float(rule["max"]):
        return False
    return True


def metric_status(metric: str, value: object) -> str:
    number = _to_float(value)
    rules = _configured_metric_thresholds().get(_metric_key(metric), [])
    for rule in rules:
        if _rule_matches(rule, number):
            return str(rule.get("status", "NORMAL")).strip().upper() or "NORMAL"
    return "NORMAL"


def is_metric_configured(metric: str) -> bool:
    return _metric_key(metric) in _configured_metric_thresholds()


def color_metric(
    value: object,
    metric: str,
    *,
    width: int = 0,
    precision: int | None = None,
    enabled: bool | None = None,
) -> str:
    number = _to_float(value)
    if precision is None:
        text = str(value)
    else:
        text = f"{number:.{precision}f}"
    if width > 0:
        text = f"{text:>{width}}"
    return colorize(text, metric_status(metric, number), enabled=enabled)
