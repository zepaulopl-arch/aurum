from pymercator.cli import main


def test_cli_diag_separates_libraries_from_prediction_engines(monkeypatch, capsys):
    import pymercator.legacy_prediction_engines as engines_mod

    monkeypatch.setattr(engines_mod, "SKLEARN_AVAILABLE", True)
    monkeypatch.setattr(engines_mod, "XGBOOST_AVAILABLE", False)
    monkeypatch.setattr(engines_mod, "CATBOOST_AVAILABLE", False)

    exit_code = main(["diag"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "PYMERCATOR DIAG" in output
    assert "LIBRARIES:" in output
    assert "- sklearn available: True" in output
    assert "PREDICTION ENGINES:" in output
    assert "- extratrees: available" in output
    assert "BASELINES:" in output
    assert "- rolling_majority: available" in output
    assert "- sklearn:" not in output
