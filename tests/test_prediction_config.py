import json
from pathlib import Path

from pymercator.prediction_config import effective_prediction_config


def test_repository_prediction_config_declares_operational_default_engine():
    payload = json.loads(Path("config/prediction.json").read_text(encoding="utf-8"))

    assert payload["operational"]["default_engine"] == "multi_horizon_ridge"
    assert payload["operational"]["per_horizon_engine"] == "ridge_ensemble"


def test_effective_prediction_config_exposes_operational_engines(tmp_path):
    config = tmp_path / "prediction.json"
    config.write_text(
        json.dumps(
            {
                "operational": {
                    "default_engine": "multi_horizon_ridge",
                    "per_horizon_engine": "ridge_ensemble",
                }
            }
        ),
        encoding="utf-8",
    )

    resolved = effective_prediction_config(path=config)

    assert resolved["default_engine"] == "multi_horizon_ridge"
    assert resolved["per_horizon_engine"] == "ridge_ensemble"
