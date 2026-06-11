from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from aurum.data.universe_csv import load_universe_csv
from aurum.policy import load_policy


def _code_join(codes: list[str]) -> str:
    if not codes:
        return "OK"
    return "+".join(codes)


def _sector_read(item: dict[str, Any]) -> str:
    assets = max(int(item["assets"]), 1)
    vol_high = int(item["vol_high"])
    atr_high = int(item["atr_high"])
    vol_pressure = (vol_high + atr_high) / assets
    weak_pressure = max(int(item["weak_trend"]), int(item["weak_momentum"])) / assets

    if vol_pressure == 0 and weak_pressure == 0:
        return "OK"
    if atr_high > 0 or vol_pressure >= 0.50:
        return "VOLATILE"
    if vol_high >= 2 and weak_pressure > 0:
        if assets >= 8:
            return "VOL+WEAK"
        return "MIXED"
    if weak_pressure >= 0.75:
        return "WEAK"
    if vol_pressure > 0 and weak_pressure > 0:
        return "MIXED"
    if vol_pressure > 0:
        return "VOLATILE"
    return "WEAK"


def _sector_volatility_load(item: dict[str, Any]) -> float:
    assets = max(int(item["assets"]), 1)
    return (int(item["vol_high"]) + int(item["atr_high"])) / assets


def _summarize_sectors(diagnostics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_sector: dict[str, dict[str, Any]] = {}
    for item in diagnostics:
        sector = str(item["sector"]).strip() or "UNKNOWN"
        row = by_sector.setdefault(
            sector,
            {
                "sector": sector,
                "assets": 0,
                "vol_high": 0,
                "atr_high": 0,
                "weak_trend": 0,
                "weak_momentum": 0,
                "warning_assets": 0,
                "trend_sum": 0.0,
                "momentum_sum": 0.0,
            },
        )
        codes = set(item.get("codes", []))
        row["assets"] += 1
        row["vol_high"] += int("VOL_HIGH" in codes)
        row["atr_high"] += int("ATR_HIGH" in codes)
        row["weak_trend"] += int("WEAK_TREND" in codes)
        row["weak_momentum"] += int("WEAK_MOM" in codes)
        row["warning_assets"] += int(bool(codes))
        row["trend_sum"] += float(item.get("trend_score", 0.0) or 0.0)
        row["momentum_sum"] += float(item.get("momentum_score", 0.0) or 0.0)

    rows: list[dict[str, Any]] = []
    for row in by_sector.values():
        assets = max(int(row["assets"]), 1)
        row["avg_trend"] = round(float(row["trend_sum"]) / assets, 2)
        row["avg_momentum"] = round(float(row["momentum_sum"]) / assets, 2)
        row["read"] = _sector_read(row)
        row.pop("trend_sum")
        row.pop("momentum_sum")
        rows.append(row)

    return sorted(
        rows,
        key=lambda item: (
            -int(item["assets"]),
            -int(item["warning_assets"]),
            str(item["sector"]).lower(),
        ),
    )


def _operational_summary(
    *,
    warning_count: int,
    weak_trend: int,
    weak_momentum: int,
    volatility_high: int,
    atr_high: int,
    sector_summary: list[dict[str, Any]],
) -> dict[str, Any]:
    if weak_trend >= volatility_high + atr_high and weak_momentum >= volatility_high:
        dominant_problem = "weak trend + weak momentum"
    elif volatility_high + atr_high > weak_trend:
        dominant_problem = "volatility"
    else:
        dominant_problem = "mixed warnings"

    worst = sorted(
        sector_summary,
        key=lambda item: (
            -int(item["warning_assets"]),
            -int(item["assets"]),
            str(item["sector"]).lower(),
        ),
    )[:4]
    volatile = [
        item
        for item in sorted(
            sector_summary,
            key=lambda row: (
                -(int(row["vol_high"]) + int(row["atr_high"])),
                -int(row["assets"]),
                str(row["sector"]).lower(),
            ),
        )
        if (
            _sector_volatility_load(item) >= 0.25
            or int(item["atr_high"]) > 0
            or int(item["vol_high"]) >= 2
        )
    ][:3]
    best_candidates = [
        item
        for item in sector_summary
        if int(item["assets"]) >= 3
    ]
    best = max(
        best_candidates or sector_summary,
        key=lambda item: (
            float(item.get("avg_trend", 0.0)) + float(item.get("avg_momentum", 0.0)),
            -int(item["warning_assets"]),
        ),
        default=None,
    )
    best_relative_sector = "-"
    if best:
        best_relative_sector = str(best["sector"])
        if int(best["vol_high"]) + int(best["atr_high"]) > 0:
            best_relative_sector = f"{best_relative_sector}, but volatile"

    return {
        "warnings_assets": warning_count,
        "dominant_problem": dominant_problem,
        "worst_sectors": [str(item["sector"]) for item in worst],
        "volatile_sectors": [str(item["sector"]) for item in volatile],
        "best_relative_sector": best_relative_sector,
    }


def diagnose_universe_csv(
    *,
    path: str | Path,
    policy_path: str | Path = "config/policy.json",
) -> dict[str, Any]:
    policy = load_policy(policy_path)
    assets = load_universe_csv(path)

    universe_policy = policy["universe_health"]
    min_volume = float(universe_policy["min_avg_volume_brl"])
    max_volatility = float(universe_policy["max_volatility_pct"])
    max_atr = float(universe_policy["max_atr_pct"])
    min_assets = int(universe_policy["min_valid_assets"])

    weak_trend_threshold = 45.0
    weak_momentum_threshold = 45.0

    diagnostics: list[dict[str, Any]] = []

    liquidity_low = 0
    volatility_high = 0
    atr_high = 0
    weak_trend = 0
    weak_momentum = 0
    missing_trade_plan = 0

    for asset in assets:
        codes: list[str] = []

        if asset.avg_volume_brl < min_volume:
            codes.append("LIQ_LOW")
            liquidity_low += 1

        if asset.volatility_pct > max_volatility:
            codes.append("VOL_HIGH")
            volatility_high += 1

        if asset.atr_pct > max_atr:
            codes.append("ATR_HIGH")
            atr_high += 1

        if asset.trend_score < weak_trend_threshold:
            codes.append("WEAK_TREND")
            weak_trend += 1

        if asset.momentum_score < weak_momentum_threshold:
            codes.append("WEAK_MOM")
            weak_momentum += 1

        if asset.entry is None or asset.stop is None or asset.target is None:
            codes.append("NO_PLAN")
            missing_trade_plan += 1

        diagnostics.append(
            {
                "ticker": asset.ticker,
                "sector": asset.sector,
                "avg_volume_brl": asset.avg_volume_brl,
                "volatility_pct": asset.volatility_pct,
                "atr_pct": asset.atr_pct,
                "trend_score": asset.trend_score,
                "momentum_score": asset.momentum_score,
                "codes": codes,
                "label": _code_join(codes),
            }
        )

    sectors = Counter(asset.sector for asset in assets)
    top_sector = sectors.most_common(1)[0] if sectors else ("-", 0)
    concentration_pct = (top_sector[1] / len(assets)) if assets else 0.0

    if len(assets) < min_assets:
        asset_count_status = "TOO_SMALL"
    else:
        asset_count_status = "OK"

    if concentration_pct >= 0.50:
        concentration_status = "HIGH"
    elif concentration_pct >= 0.35:
        concentration_status = "MODERATE"
    else:
        concentration_status = "LOW"

    warning_count = sum(1 for item in diagnostics if item["codes"])
    sector_warning_summary = _summarize_sectors(diagnostics)
    summary = _operational_summary(
        warning_count=warning_count,
        weak_trend=weak_trend,
        weak_momentum=weak_momentum,
        volatility_high=volatility_high,
        atr_high=atr_high,
        sector_summary=sector_warning_summary,
    )

    if not assets:
        data_status = "FAIL"
    elif asset_count_status == "TOO_SMALL":
        data_status = "WARN_SMALL_UNIVERSE"
    elif warning_count == 0 and concentration_status == "LOW":
        data_status = "PASS"
    else:
        data_status = "PASS_WITH_WARNINGS"

    return {
        "path": str(path),
        "policy": str(policy_path),
        "assets": len(assets),
        "min_assets": min_assets,
        "data_status": data_status,
        "asset_count_status": asset_count_status,
        "warning_count": warning_count,
        "liquidity_low": liquidity_low,
        "volatility_high": volatility_high,
        "atr_high": atr_high,
        "weak_trend": weak_trend,
        "weak_momentum": weak_momentum,
        "missing_trade_plan": missing_trade_plan,
        "sector_concentration": {
            "status": concentration_status,
            "top_sector": top_sector[0],
            "top_sector_count": top_sector[1],
            "top_sector_pct": round(concentration_pct * 100.0, 2),
            "sectors": dict(sorted(sectors.items())),
        },
        "sector_warning_summary": sector_warning_summary,
        "summary": summary,
        "diagnostics": diagnostics,
    }
