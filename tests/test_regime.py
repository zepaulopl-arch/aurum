from aurum.engines.regime import classify_market_regime
from aurum.policy import load_policy


def test_extreme_headline_denies_market_regime():
    policy = load_policy("config/policy.json")

    result = classify_market_regime(
        headline_risk="EXTREME",
        headline_tags=["IRAN", "OIL"],
        market_trend="UP",
        market_volatility="NORMAL",
        policy=policy,
    )

    assert result.regime.value == "CRISIS"
    assert result.permission.value == "DENY"
    assert result.score_factor == 0.55


def test_downtrend_with_normal_volatility_is_risk_off_not_unknown():
    policy = load_policy("config/policy.json")

    result = classify_market_regime(
        headline_risk="OFF",
        headline_tags=["RISK_OFF"],
        market_trend="DOWN",
        market_volatility="NORMAL",
        policy=policy,
    )

    assert result.regime.value == "RISK_OFF"
    assert result.permission.value == "CAUTION"
    assert "DOWN" in "; ".join(result.reasons)


def test_unknown_market_trend_denies_by_policy():
    policy = load_policy("config/policy.json")

    result = classify_market_regime(
        headline_risk="OFF",
        headline_tags=[],
        market_trend="UNKNOWN",
        market_volatility="NORMAL",
        policy=policy,
    )

    assert result.regime.value == "UNKNOWN"
    assert result.permission.value == "DENY"
