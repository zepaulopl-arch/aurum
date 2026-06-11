from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

DEFAULT_MARKET_CONTEXT_THRESHOLDS: dict[str, float] = {
    "trend_up_return_20d_pct": 3.0,
    "trend_up_sma_position_pct": 1.0,
    "trend_down_return_20d_pct": -3.0,
    "trend_down_sma_position_pct": -1.0,
    "volatility_high_pct": 28.0,
    "volatility_low_pct": 12.0,
    "oil_stress_return_5d_pct": 5.0,
    "oil_stress_return_20d_pct": 10.0,
    "fx_stress_return_5d_pct": 3.0,
    "fx_stress_return_20d_pct": 6.0,
}


def load_market_context_thresholds(
    path: str | Path = "config/market_context_thresholds.json",
) -> dict[str, float]:
    thresholds = dict(DEFAULT_MARKET_CONTEXT_THRESHOLDS)
    source = Path(path)
    if not source.exists():
        return thresholds
    try:
        payload = json.loads(source.read_text(encoding="utf-8-sig"))
    except Exception:
        return thresholds
    raw = payload.get("thresholds", payload) if isinstance(payload, dict) else {}
    if not isinstance(raw, dict):
        return thresholds
    for key, default in DEFAULT_MARKET_CONTEXT_THRESHOLDS.items():
        try:
            thresholds[key] = float(raw.get(key, default))
        except (TypeError, ValueError):
            thresholds[key] = default
    return thresholds


def _read_price_file(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    data = pd.read_csv(path)
    data.columns = [str(column).lower() for column in data.columns]

    if "date" not in data.columns or "close" not in data.columns:
        return pd.DataFrame()

    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data["close"] = pd.to_numeric(data["close"], errors="coerce")
    data = data.dropna(subset=["date", "close"])
    data = data[data["close"] > 0]
    data = data.sort_values("date")

    return data


def _last_return(data: pd.DataFrame, window: int) -> float:
    if len(data) <= window:
        return 0.0

    last = float(data["close"].iloc[-1])
    previous = float(data["close"].iloc[-window - 1])

    if previous <= 0:
        return 0.0

    return round(((last / previous) - 1.0) * 100.0, 2)


def _annualized_volatility(data: pd.DataFrame, window: int = 20) -> float:
    if len(data) <= window:
        return 0.0

    returns = data["close"].pct_change().dropna().tail(window)

    if returns.empty:
        return 0.0

    return round(float(returns.std() * (252**0.5) * 100.0), 2)


def _sma_position(data: pd.DataFrame, window: int = 20) -> float:
    if len(data) < window:
        return 0.0

    last = float(data["close"].iloc[-1])
    sma = float(data["close"].tail(window).mean())

    if sma <= 0:
        return 0.0

    return round(((last / sma) - 1.0) * 100.0, 2)


def _rolling_returns(data: pd.DataFrame, window: int) -> list[float]:
    if len(data) <= window:
        return []
    values: list[float] = []
    closes = list(data["close"])
    for index in range(window, len(closes)):
        previous = float(closes[index - window])
        current = float(closes[index])
        if previous > 0 and current > 0:
            values.append(((current / previous) - 1.0) * 100.0)
    return values


def _rolling_sma_positions(data: pd.DataFrame, window: int = 20) -> list[float]:
    if len(data) < window:
        return []
    values: list[float] = []
    closes = list(data["close"])
    for index in range(window - 1, len(closes)):
        recent = closes[index - window + 1 : index + 1]
        sma = float(sum(recent) / len(recent))
        current = float(closes[index])
        if sma > 0 and current > 0:
            values.append(((current / sma) - 1.0) * 100.0)
    return values


def _rolling_volatility(data: pd.DataFrame, window: int = 20) -> list[float]:
    if len(data) <= window:
        return []
    returns = data["close"].pct_change().dropna()
    values: list[float] = []
    for index in range(window, len(returns) + 1):
        sample = returns.iloc[index - window : index]
        if not sample.empty:
            values.append(float(sample.std() * (252**0.5) * 100.0))
    return values


def _quantile(values: list[float], q: float, fallback: float) -> float:
    valid = sorted(value for value in values if pd.notna(value))
    if not valid:
        return fallback
    if len(valid) == 1:
        return round(float(valid[0]), 2)
    position = (len(valid) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(valid) - 1)
    fraction = position - lower
    return round(float(valid[lower] * (1.0 - fraction) + valid[upper] * fraction), 2)


def _market_trend(ibov: pd.DataFrame, thresholds: dict[str, float]) -> str:
    ret_20 = _last_return(ibov, 20)
    sma_position = _sma_position(ibov, 20)

    if (
        ret_20 >= thresholds["trend_up_return_20d_pct"]
        and sma_position >= thresholds["trend_up_sma_position_pct"]
    ):
        return "UP"

    if (
        ret_20 <= thresholds["trend_down_return_20d_pct"]
        and sma_position <= thresholds["trend_down_sma_position_pct"]
    ):
        return "DOWN"

    return "CHOPPY"


def _market_volatility(ibov: pd.DataFrame, thresholds: dict[str, float]) -> str:
    vol = _annualized_volatility(ibov, 20)

    if vol >= thresholds["volatility_high_pct"]:
        return "HIGH"

    if vol <= thresholds["volatility_low_pct"] and vol > 0:
        return "LOW"

    return "NORMAL"


def build_auto_market_context(
    indices_dir: str | Path,
    *,
    thresholds_path: str | Path = "config/market_context_thresholds.json",
) -> dict[str, Any]:
    root = Path(indices_dir)
    thresholds = load_market_context_thresholds(thresholds_path)

    ibov = _read_price_file(root / "^BVSP.csv")
    brent = _read_price_file(root / "BZ=F.csv")
    usdbrl = _read_price_file(root / "USDBRL=X.csv")

    headline_tags: list[str] = []
    notes: list[str] = []

    market_trend = _market_trend(ibov, thresholds)
    market_volatility = _market_volatility(ibov, thresholds)

    ibov_ret_5 = _last_return(ibov, 5)
    ibov_ret_20 = _last_return(ibov, 20)
    ibov_vol_20 = _annualized_volatility(ibov, 20)

    brent_ret_5 = _last_return(brent, 5)
    brent_ret_20 = _last_return(brent, 20)

    usdbrl_ret_5 = _last_return(usdbrl, 5)
    usdbrl_ret_20 = _last_return(usdbrl, 20)

    if market_trend == "UP" and market_volatility != "HIGH":
        headline_tags.append("RISK_ON")
        notes.append("IBOV trend supports risk-on posture")

    if market_trend == "DOWN" or market_volatility == "HIGH":
        headline_tags.append("RISK_OFF")
        notes.append("IBOV trend/volatility supports caution")

    if (
        brent_ret_5 >= thresholds["oil_stress_return_5d_pct"]
        or brent_ret_20 >= thresholds["oil_stress_return_20d_pct"]
    ):
        headline_tags.extend(["OIL", "OIL_STRESS"])
        notes.append("Brent move indicates oil stress")

    if (
        usdbrl_ret_5 >= thresholds["fx_stress_return_5d_pct"]
        or usdbrl_ret_20 >= thresholds["fx_stress_return_20d_pct"]
    ):
        headline_tags.extend(["BRL", "FX_STRESS"])
        notes.append("USD/BRL move indicates FX stress")

    if not headline_tags:
        notes.append("No major automatic macro stress detected")

    unique_tags = sorted(set(headline_tags))

    return {
        "headline_tags": unique_tags,
        "market_trend": market_trend,
        "market_volatility": market_volatility,
        "notes": "; ".join(notes),
        "source": "auto_indices",
        "thresholds": thresholds,
        "metrics": {
            "ibov_return_5d_pct": ibov_ret_5,
            "ibov_return_20d_pct": ibov_ret_20,
            "ibov_volatility_20d_annualized_pct": ibov_vol_20,
            "brent_return_5d_pct": brent_ret_5,
            "brent_return_20d_pct": brent_ret_20,
            "usdbrl_return_5d_pct": usdbrl_ret_5,
            "usdbrl_return_20d_pct": usdbrl_ret_20,
        },
    }


def write_auto_market_context(
    *,
    indices_dir: str | Path,
    output: str | Path,
    thresholds_path: str | Path = "config/market_context_thresholds.json",
) -> dict[str, Any]:
    context = build_auto_market_context(indices_dir, thresholds_path=thresholds_path)

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        json.dumps(context, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "indices_dir": str(indices_dir),
        "output": str(output_path),
        "headline_tags": context["headline_tags"],
        "market_trend": context["market_trend"],
        "market_volatility": context["market_volatility"],
        "notes": context["notes"],
        "thresholds": context["thresholds"],
        "metrics": context["metrics"],
    }


def calibrate_market_context_thresholds(
    *,
    indices_dir: str | Path,
    output: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(indices_dir)
    ibov = _read_price_file(root / "^BVSP.csv")
    brent = _read_price_file(root / "BZ=F.csv")
    usdbrl = _read_price_file(root / "USDBRL=X.csv")
    defaults = dict(DEFAULT_MARKET_CONTEXT_THRESHOLDS)

    ibov_ret_20 = _rolling_returns(ibov, 20)
    ibov_sma_20 = _rolling_sma_positions(ibov, 20)
    ibov_vol_20 = _rolling_volatility(ibov, 20)
    brent_ret_5 = _rolling_returns(brent, 5)
    brent_ret_20 = _rolling_returns(brent, 20)
    usdbrl_ret_5 = _rolling_returns(usdbrl, 5)
    usdbrl_ret_20 = _rolling_returns(usdbrl, 20)

    thresholds = {
        "trend_up_return_20d_pct": max(
            1.5,
            _quantile(ibov_ret_20, 0.70, defaults["trend_up_return_20d_pct"]),
        ),
        "trend_up_sma_position_pct": max(
            0.5,
            _quantile(ibov_sma_20, 0.70, defaults["trend_up_sma_position_pct"]),
        ),
        "trend_down_return_20d_pct": min(
            -1.5,
            _quantile(ibov_ret_20, 0.30, defaults["trend_down_return_20d_pct"]),
        ),
        "trend_down_sma_position_pct": min(
            -0.5,
            _quantile(ibov_sma_20, 0.30, defaults["trend_down_sma_position_pct"]),
        ),
        "volatility_high_pct": max(
            18.0,
            _quantile(ibov_vol_20, 0.75, defaults["volatility_high_pct"]),
        ),
        "volatility_low_pct": min(
            18.0,
            _quantile(ibov_vol_20, 0.25, defaults["volatility_low_pct"]),
        ),
        "oil_stress_return_5d_pct": max(
            3.0,
            _quantile(brent_ret_5, 0.85, defaults["oil_stress_return_5d_pct"]),
        ),
        "oil_stress_return_20d_pct": max(
            6.0,
            _quantile(brent_ret_20, 0.85, defaults["oil_stress_return_20d_pct"]),
        ),
        "fx_stress_return_5d_pct": max(
            2.0,
            _quantile(usdbrl_ret_5, 0.85, defaults["fx_stress_return_5d_pct"]),
        ),
        "fx_stress_return_20d_pct": max(
            4.0,
            _quantile(usdbrl_ret_20, 0.85, defaults["fx_stress_return_20d_pct"]),
        ),
    }

    payload = {
        "command": "context_calibrate",
        "schema_version": "market_context_calibration.v1",
        "indices_dir": str(indices_dir),
        "calibration_type": "historical_indices_percentiles",
        "thresholds": thresholds,
        "config_patch": {
            "schema_version": "market_context_thresholds.v1",
            "thresholds": thresholds,
        },
        "sample_size": {
            "ibov_return_20d": len(ibov_ret_20),
            "ibov_volatility_20d": len(ibov_vol_20),
            "brent_return_20d": len(brent_ret_20),
            "usdbrl_return_20d": len(usdbrl_ret_20),
        },
    }
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload["output"] = str(output_path)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return payload
