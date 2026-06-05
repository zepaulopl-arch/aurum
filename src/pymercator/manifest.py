from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: str | Path, default: Any = None) -> Any:
    source = Path(path)
    if not source.exists():
        return default

    return json.loads(source.read_text(encoding="utf-8-sig"))


def write_json(path: str | Path, payload: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
