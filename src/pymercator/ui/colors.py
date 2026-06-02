from __future__ import annotations

import re
import sys
from typing import Any

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

COLOR_MODE = "auto"

RESET = "\x1b[0m"
DIM = "\x1b[2m"

PALETTE = {
    "green": "\x1b[2;32m",
    "yellow": "\x1b[2;33m",
    "red": "\x1b[2;31m",
    "gray": "\x1b[2;37m",
    "header": "\x1b[2;36m",
    "number": "\x1b[37m",
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
    style = PALETTE[_class_for_status(status if status is not None else text)]
    return f"{style}{value}{RESET}"


def colorize_value(value: Any, *, role: str = "", enabled: bool | None = None) -> str:
    text = str(value)
    if not color_enabled(enabled):
        return text
    key = str(role or value or "").strip().upper()
    if key == "HEADER":
        return f"{PALETTE['header']}{text}{RESET}"
    if key == "NUMBER":
        return f"{PALETTE['number']}{text}{RESET}"
    if key in {"LABEL", "PATH", "FALSE"}:
        return f"{PALETTE['gray']}{text}{RESET}"
    return colorize(text, key, enabled=True)
