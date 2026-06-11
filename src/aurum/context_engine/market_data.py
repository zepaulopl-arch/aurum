"""Serious public market data via Yahoo Finance chart API.

This is not official macro data. It is a public market-data source used for
FX/commodities context when available. Every value is tagged with source and
source_status. If Yahoo fails, the builder falls back to local/manual context.
"""

from __future__ import annotations

from urllib.parse import quote

from aurum.context_engine.sources import SourceResult, http_get_json, parse_float


YAHOO_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"


def fetch_yahoo_quote(symbol: str, timeout: float = 12.0) -> SourceResult:
    """Fetch a simple latest/previous quote from Yahoo chart API."""
    url = f"{YAHOO_BASE}/{quote(symbol, safe='')}?range=5d&interval=1d"
    result = http_get_json(url, timeout=timeout)
    result.name = f"yahoo_{symbol}"
    result.kind = "public_market_data"
    if result.status != "OK":
        return result

    payload = result.data if isinstance(result.data, dict) else {}
    chart = payload.get("chart", {})
    if chart.get("error"):
        result.status = "ERROR"
        result.error = str(chart.get("error"))
        result.data = {}
        return result

    try:
        item = chart["result"][0]
        meta = item.get("meta", {})
        quote_data = item.get("indicators", {}).get("quote", [{}])[0]
        closes = [value for value in quote_data.get("close", []) if value is not None]
        if not closes:
            result.status = "MISSING"
            result.error = "No close prices returned."
            result.data = {}
            return result
        last = parse_float(closes[-1])
        prev = parse_float(closes[-2]) if len(closes) >= 2 else None
        change_pct = None
        if last is not None and prev not in (None, 0):
            change_pct = round(((last / prev) - 1.0) * 100.0, 2)
        result.data = {
            "symbol": symbol,
            "value": last,
            "previous": prev,
            "change_pct": change_pct,
            "currency": meta.get("currency", ""),
            "exchange": meta.get("exchangeName", ""),
            "source": "YAHOO_CHART",
        }
        return result
    except Exception as exc:
        result.status = "ERROR"
        result.error = f"Could not parse Yahoo chart payload: {exc}"
        result.data = {}
        return result


def fetch_market_snapshot(timeout: float = 12.0) -> SourceResult:
    """Fetch market proxies used by context.

    Symbols:
    - USDBRL=X: USD/BRL
    - CL=F: WTI crude
    - BZ=F: Brent crude
    - DX-Y.NYB: DXY dollar index
    """
    symbols = {
        "usdbrl": "USDBRL=X",
        "wti_oil": "CL=F",
        "brent_oil": "BZ=F",
        "dxy": "DX-Y.NYB",
    }
    data = {}
    statuses = {}
    errors = {}
    for name, symbol in symbols.items():
        item = fetch_yahoo_quote(symbol, timeout=timeout)
        statuses[name] = item.status
        if item.status == "OK":
            data[name] = item.data
        else:
            errors[name] = item.error or item.status

    ok = sum(1 for status in statuses.values() if status == "OK")
    status = "OK" if ok == len(statuses) else "PARTIAL" if ok else "ERROR"
    return SourceResult(
        name="market_public_yahoo",
        status=status,
        data=data,
        kind="public_market_data",
        detail={"source_status": statuses, "errors": errors},
        error="" if not errors else str(errors),
    )


def infer_oil_risk(market_data: dict) -> str:
    """Classify oil risk from daily movement if available."""
    for key in ("brent_oil", "wti_oil"):
        item = market_data.get(key)
        if isinstance(item, dict) and isinstance(item.get("change_pct"), (int, float)):
            change = abs(item["change_pct"])
            if change >= 3.0:
                return "HIGH"
            if change >= 1.0:
                return "MEDIUM"
            return "LOW"
    return "UNKNOWN"
