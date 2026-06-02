from __future__ import annotations

from typing import Any

from pymercator.ui.colors import colorize, colorize_value

DEFAULT_WIDTH = 80


def muted_line(width: int = DEFAULT_WIDTH) -> str:
    return "-" * max(1, min(int(width), 100))


def format_title(title: str, *, width: int = DEFAULT_WIDTH, color: bool | None = None) -> str:
    return "\n".join(
        [
            colorize_value(title, role="HEADER", enabled=color),
            muted_line(width),
        ]
    )


def format_kv(
    label: str,
    value: Any,
    *,
    label_width: int = 18,
    status: Any = None,
    color: bool | None = None,
) -> str:
    value_text = colorize(value, status, enabled=color) if status is not None else str(value)
    return f"{label:<{label_width}} {value_text}"


def format_kv_section(
    title: str,
    rows: list[tuple[str, Any] | tuple[str, Any, Any]],
    *,
    label_width: int = 18,
    width: int = DEFAULT_WIDTH,
    color: bool | None = None,
) -> str:
    lines = [format_title(title, width=width, color=color)]
    for row in rows:
        if len(row) == 3:
            label, value, status = row
        else:
            label, value = row
            status = None
        lines.append(
            format_kv(
                str(label),
                value,
                label_width=label_width,
                status=status,
                color=color,
            )
        )
    return "\n".join(lines)
