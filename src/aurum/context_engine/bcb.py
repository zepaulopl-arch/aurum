"""Banco Central do Brasil sources.

Uses public SGS endpoints. The source is defensive:
1. Try `/dados/ultimos/{limit}?formato=json`.
2. If it fails or returns non-JSON/empty, try `/dados` with explicit dates.

For Selic, SGS series 11 (daily Selic) is used as the online working source.
It is converted to an annualized proxy inside the builder.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from aurum.context_engine.sources import SourceResult, http_get_json, parse_float


SGS_DEFAULT_SERIES = {
    # 11 = Selic daily rate. It has been more reliable than target series in
    # practical API tests.
    "selic_daily": 11,
    # 433 = IPCA monthly variation. It may fail depending on endpoint behavior;
    # it remains explicit and auditable.
    "ipca_monthly": 433,
}


def annualize_daily_rate(daily_rate_pct: float | None, business_days: int = 252) -> float | None:
    """Convert a daily percentage rate into an annualized percentage proxy."""
    if daily_rate_pct is None:
        return None
    daily = daily_rate_pct / 100.0
    annual = ((1.0 + daily) ** int(business_days) - 1.0) * 100.0
    return round(annual, 4)


def _parse_sgs_rows(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    parsed = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        parsed.append(
            {
                "date": row.get("data"),
                "value": parse_float(row.get("valor")),
                "raw": row,
            }
        )
    return parsed


def _date_range_url(series_code: int, days_back: int = 180) -> str:
    today = date.today()
    start = today - timedelta(days=days_back)
    data_inicial = start.strftime("%d/%m/%Y")
    data_final = today.strftime("%d/%m/%Y")
    return (
        "https://api.bcb.gov.br/dados/serie/bcdata.sgs."
        f"{int(series_code)}/dados?formato=json"
        f"&dataInicial={data_inicial}&dataFinal={data_final}"
    )


def _latest_url(series_code: int, limit: int = 1) -> str:
    return (
        "https://api.bcb.gov.br/dados/serie/bcdata.sgs."
        f"{int(series_code)}/dados/ultimos/{int(limit)}?formato=json"
    )


def fetch_bcb_series(series_code: int, limit: int = 1, timeout: float = 12.0) -> SourceResult:
    """Fetch latest values for a SGS series.

    Strategy:
    1. Try `/dados/ultimos/{limit}?formato=json`.
    2. If it fails or returns non-JSON/empty, try `/dados` with a date range.
    """
    latest = http_get_json(_latest_url(series_code, limit), timeout=timeout)
    latest.name = f"bcb_sgs_{series_code}"
    latest.detail["series_code"] = int(series_code)
    latest.detail["attempt"] = "latest"

    if latest.status == "OK":
        parsed = _parse_sgs_rows(latest.data)
        if parsed:
            latest.data = parsed[-int(limit):]
            return latest
        latest.status = "EMPTY"
        latest.error = "SGS latest endpoint returned no rows."

    fallback = http_get_json(_date_range_url(series_code), timeout=timeout)
    fallback.name = f"bcb_sgs_{series_code}"
    fallback.detail["series_code"] = int(series_code)
    fallback.detail["attempt"] = "date_range"
    fallback.detail["previous_status"] = latest.status
    fallback.detail["previous_error"] = latest.error
    fallback.detail["previous_url"] = latest.url

    if fallback.status == "OK":
        parsed = _parse_sgs_rows(fallback.data)
        if parsed:
            fallback.data = parsed[-int(limit):]
            return fallback
        fallback.status = "EMPTY"
        fallback.error = "SGS date-range endpoint returned no rows."

    fallback.error = (
        f"latest={latest.status}: {latest.error or '-'}; "
        f"date_range={fallback.status}: {fallback.error or '-'}"
    )
    return fallback


def fetch_bcb_snapshot(timeout: float = 12.0) -> SourceResult:
    """Fetch default BCB macro snapshot."""
    values: dict[str, Any] = {}
    source_status: dict[str, str] = {}
    errors: dict[str, str] = {}

    for name, code in SGS_DEFAULT_SERIES.items():
        item = fetch_bcb_series(code, limit=1, timeout=timeout)
        source_status[name] = item.status
        if item.status == "OK" and item.data:
            values[name] = item.data[-1]
        else:
            errors[name] = item.error or item.status

    status = "OK" if all(value == "OK" for value in source_status.values()) else "PARTIAL"
    if all(value != "OK" for value in source_status.values()):
        status = "ERROR"

    return SourceResult(
        name="bcb_sgs",
        status=status,
        data=values,
        detail={"source_status": source_status, "errors": errors},
        error="" if status == "OK" else str(errors),
    )

# ---------------------------------------------------------------------------
# Compatibility wrapper for Context Engine source repair
# ---------------------------------------------------------------------------

def _aurum_annualize_daily_rate(daily_rate_pct, business_days=252):
    if daily_rate_pct is None:
        return None
    try:
        daily = float(daily_rate_pct) / 100.0
        return round(((1.0 + daily) ** int(business_days) - 1.0) * 100.0, 4)
    except Exception:
        return None


def fetch_bcb_selic(timeout=12.0):
    """Fetch Selic for Context Engine.

    Compatibility wrapper:
    - prefers existing fetch_bcb_snapshot() when available;
    - accepts either selic_daily or selic_target from the snapshot;
    - returns SourceResult with annual_proxy_pct when possible;
    - never invents data.
    """
    from aurum.context_engine.sources import SourceResult

    if "fetch_bcb_snapshot" not in globals():
        return SourceResult(
            name="bcb_selic",
            status="MISSING",
            data={},
            error="fetch_bcb_snapshot is not available in bcb.py",
        )

    snapshot = fetch_bcb_snapshot(timeout=timeout)
    data = snapshot.data if isinstance(snapshot.data, dict) else {}

    item = None
    item_key = ""
    for key in ("selic_daily", "selic_target"):
        candidate = data.get(key)
        if isinstance(candidate, dict):
            item = candidate
            item_key = key
            break

    if not item:
        return SourceResult(
            name="bcb_selic",
            status=snapshot.status if snapshot.status else "MISSING",
            data={},
            error=snapshot.error or "No Selic item found in BCB snapshot.",
            detail=getattr(snapshot, "detail", {}),
        )

    raw_value = item.get("value")
    try:
        value = float(raw_value) if raw_value is not None else None
    except Exception:
        value = None

    if value is None:
        return SourceResult(
            name="bcb_selic",
            status="MISSING",
            data={},
            error="Selic value is missing or invalid.",
            detail=getattr(snapshot, "detail", {}),
        )

    if item_key == "selic_daily":
        annual_proxy = _aurum_annualize_daily_rate(value)
        daily_pct = value
        source = "BCB_SGS_DAILY"
    else:
        annual_proxy = value
        daily_pct = None
        source = "BCB_SGS_TARGET"

    return SourceResult(
        name="bcb_selic",
        status="OK",
        data={
            "daily_pct": daily_pct,
            "annual_proxy_pct": annual_proxy,
            "date": item.get("date"),
            "source": source,
        },
        detail=getattr(snapshot, "detail", {}),
    )
