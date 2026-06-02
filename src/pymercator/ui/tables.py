from __future__ import annotations

from typing import Any

from pymercator.ui.colors import colorize
from pymercator.ui.formatters import format_title

Column = tuple[str, str, int] | tuple[str, str, int, str]

SECTOR_ALIASES = {
    "consumer_discretionary": "consumer_disc.",
    "consumer_staples": "consumer_stap.",
    "communication_services": "comm.",
    "communication": "comm.",
    "health_care": "health",
    "healthcare": "health",
    "real_estate": "real_estate",
}


def truncate(value: object, width: int) -> str:
    text = str(value or "")
    if len(text) <= width:
        return text
    if width <= 1:
        return text[:width]
    return text[: width - 1] + "."


def short_sector(value: object, width: int = 16) -> str:
    key = str(value or "").strip().lower()
    return truncate(SECTOR_ALIASES.get(key, str(value or "-")), width)


def _format_cell(value: Any, width: int, align: str) -> str:
    text = truncate(value, width)
    if align == ">":
        return f"{text:>{width}}"
    return f"{text:<{width}}"


def format_table(
    title: str,
    columns: list[Column],
    rows: list[dict[str, Any]],
    *,
    color: bool | None = None,
    width: int = 80,
) -> str:
    lines = [format_title(title, width=width, color=color)]
    headers = []
    for column in columns:
        header, _key, col_width = column[:3]
        align = ">" if header.replace("_", "").isnumeric() else "<"
        headers.append(_format_cell(header, col_width, align))
    lines.append(" ".join(headers))

    for row in rows:
        cells = []
        for column in columns:
            _header, key, col_width = column[:3]
            status_key = column[3] if len(column) == 4 else ""
            value = row.get(key, "")
            align = ">" if isinstance(value, int | float) else "<"
            cell = _format_cell(value, col_width, align)
            if status_key:
                cell = colorize(cell, row.get(status_key, value), enabled=color)
            cells.append(cell)
        lines.append(" ".join(cells))
    return "\n".join(lines)
