from __future__ import annotations

from aurum.context_engine.bcb import annualize_daily_rate


def test_annualize_daily_selic_rate() -> None:
    value = annualize_daily_rate(0.0534)
    assert value is not None
    assert 14.0 < value < 15.0
