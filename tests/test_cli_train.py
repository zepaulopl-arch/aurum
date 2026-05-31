import json
from pathlib import Path

import pytest

from pymercator.cli import build_parser, main


def test_cli_train_generates_dataset_and_evaluation(tmp_path: Path, monkeypatch, capsys):
    import pymercator.cli_train as train_mod

    matrix = tmp_path / "matrix.csv"
    prices_dir = tmp_path / "prices"
    dataset = tmp_path / "dataset.csv"
    evaluation = tmp_path / "evaluation.json"
    matrix.write_text("ticker,sector,return_1d\nPRIO3,OilGas,1\n", encoding="utf-8")
    prices_dir.mkdir()

    def fake_lab(**kwargs):
        Path(kwargs["dataset_output"]).write_text(
            "date,ticker\n2025-01-01,PRIO3\n2025-01-02,PRIO3\n",
            encoding="utf-8",
        )
        Path(kwargs["evaluation_output"]).write_text("{}", encoding="utf-8")
        return {
            "dataset": {"rows": 2, "output": str(kwargs["dataset_output"])},
            "evaluation": {
                "rows": 2,
                "evaluated_rows": 1,
                "engines": kwargs["engines"],
                "engine_status": {"rolling_majority": "BASELINE"},
                "models": {"rolling_majority": {"accuracy": 0.5, "observations": 1}},
                "output": str(kwargs["evaluation_output"]),
            },
        }

    monkeypatch.setattr(train_mod, "run_prediction_lab", fake_lab)

    exit_code = main(
        [
            "train",
            "--horizon",
            "5",
            "--matrix",
            str(matrix),
            "--prices-dir",
            str(prices_dir),
            "--dataset-output",
            str(dataset),
            "--evaluation-output",
            str(evaluation),
            "--min-train-rows",
            "2",
            "--engines",
            "rolling_majority",
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "BASELINE"
    assert "profile" not in payload
    assert payload["engine_used"] == "rolling_majority"
    assert payload["is_baseline"] is True
    assert payload["dataset"]["rows"] == 2
    assert payload["dataset"]["assets"] == 1

    evaluation_payload = json.loads(evaluation.read_text(encoding="utf-8"))
    assert evaluation_payload["engine_used"] == "rolling_majority"
    assert evaluation_payload["is_baseline"] is True
    assert evaluation_payload["trained_models"] == []
    assert evaluation_payload["metrics"] == {"accuracy": 0.5, "observations": 1}
    assert "trained_at" in evaluation_payload
    assert "profile" not in evaluation_payload
    assert "profile_scope" not in evaluation_payload


def test_cli_train_profile_is_ignored_with_warning(tmp_path: Path, monkeypatch, capsys):
    import pymercator.cli_train as train_mod

    matrix = tmp_path / "matrix.csv"
    prices_dir = tmp_path / "prices"
    dataset = tmp_path / "dataset.csv"
    evaluation = tmp_path / "evaluation.json"
    matrix.write_text("ticker,sector,return_1d\nPRIO3,OilGas,1\n", encoding="utf-8")
    prices_dir.mkdir()

    def fake_lab(**kwargs):
        Path(kwargs["dataset_output"]).write_text(
            "date,ticker\n2025-01-01,PRIO3\n2025-01-02,PRIO3\n",
            encoding="utf-8",
        )
        Path(kwargs["evaluation_output"]).write_text("{}", encoding="utf-8")
        return {
            "dataset": {"rows": 2, "output": str(kwargs["dataset_output"])},
            "evaluation": {
                "rows": 2,
                "evaluated_rows": 1,
                "engines": kwargs["engines"],
                "engine_status": {"rolling_majority": "BASELINE"},
                "models": {"rolling_majority": {"accuracy": 0.5, "observations": 1}},
                "output": str(kwargs["evaluation_output"]),
            },
        }

    monkeypatch.setattr(train_mod, "run_prediction_lab", fake_lab)

    base_args = [
        "--matrix",
        str(matrix),
        "--prices-dir",
        str(prices_dir),
        "--dataset-output",
        str(dataset),
        "--min-train-rows",
        "2",
        "--engines",
        "rolling_majority",
        "--json",
    ]
    plain_exit = main(["train", *base_args, "--evaluation-output", str(evaluation)])
    plain = json.loads(capsys.readouterr().out)

    profile_exit = main(
        [
            "train",
            "--profile",
            "CON",
            *base_args,
            "--evaluation-output",
            str(evaluation),
        ]
    )
    captured = capsys.readouterr()
    with_profile = json.loads(captured.out)

    assert plain_exit == 0
    assert profile_exit == 0
    assert "WARNING: --profile is ignored by train. Profiles are applied in run." in captured.err
    assert plain["status"] == with_profile["status"]
    assert plain["engine_used"] == with_profile["engine_used"]
    assert "profile" not in with_profile
    assert evaluation.exists()
    assert not (tmp_path / "evaluation_CON.json").exists()
    profile_evaluation = json.loads(evaluation.read_text(encoding="utf-8"))
    assert "profile" not in profile_evaluation
    assert "profile_scope" not in profile_evaluation


def test_cli_train_blocks_when_matrix_is_missing(tmp_path: Path, capsys):
    prices_dir = tmp_path / "prices"
    prices_dir.mkdir()

    exit_code = main(
        [
            "train",
            "--matrix",
            str(tmp_path / "missing.csv"),
            "--prices-dir",
            str(prices_dir),
            "--json",
        ]
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "BLOCKED"
    assert payload["reason"] == "feature matrix not found"


def test_cli_train_accepts_engine_aliases():
    from pymercator.cli_train import parse_engines

    assert parse_engines("extratrees,xgboost") == ["extratrees", "xgb"]


def test_cli_train_defaults_to_extratrees_when_sklearn_library_is_available(
    tmp_path: Path,
    monkeypatch,
    capsys,
):
    import pymercator.cli_train as train_mod

    matrix = tmp_path / "matrix.csv"
    prices_dir = tmp_path / "prices"
    dataset = tmp_path / "dataset.csv"
    evaluation = tmp_path / "evaluation.json"
    matrix.write_text("ticker,sector,return_1d\nPRIO3,OilGas,1\n", encoding="utf-8")
    prices_dir.mkdir()
    monkeypatch.setattr(train_mod, "SKLEARN_AVAILABLE", True)
    monkeypatch.setattr(train_mod, "XGBOOST_AVAILABLE", False)
    monkeypatch.setattr(train_mod, "CATBOOST_AVAILABLE", False)
    calls = []

    def fake_lab(**kwargs):
        calls.append(kwargs)
        Path(kwargs["dataset_output"]).write_text(
            "date,ticker\n2025-01-01,PRIO3\n2025-01-02,PRIO3\n",
            encoding="utf-8",
        )
        Path(kwargs["evaluation_output"]).write_text("{}", encoding="utf-8")
        return {
            "dataset": {"rows": 2, "output": str(kwargs["dataset_output"])},
            "evaluation": {
                "rows": 2,
                "evaluated_rows": 1,
                "engines": kwargs["engines"],
                "engine_status": {"extratrees": "OK"},
                "models": {"extratrees": {"accuracy": 1.0, "observations": 1}},
                "output": str(kwargs["evaluation_output"]),
            },
        }

    monkeypatch.setattr(train_mod, "run_prediction_lab", fake_lab)

    exit_code = main(
        [
            "train",
            "--matrix",
            str(matrix),
            "--prices-dir",
            str(prices_dir),
            "--dataset-output",
            str(dataset),
            "--evaluation-output",
            str(evaluation),
            "--min-train-rows",
            "2",
            "--json",
        ]
    )

    assert exit_code == 0
    assert calls[0]["engines"] == ["extratrees"]
    assert calls[0]["n_jobs"] == 4
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "OK"
    assert payload["engine_used"] == "extratrees"
    assert "rolling_majority" not in payload["evaluation"]["engines"]

    evaluation_payload = json.loads(evaluation.read_text(encoding="utf-8"))
    assert evaluation_payload["engine_used"] == "extratrees"
    assert evaluation_payload["is_baseline"] is False
    assert evaluation_payload["trained_models"] == ["extratrees"]
    assert evaluation_payload["rows"] == 2
    assert evaluation_payload["assets"] == 1
    assert evaluation_payload["horizon"] == 5
    assert evaluation_payload["metrics"] == {"accuracy": 1.0, "observations": 1}
    assert "trained_at" in evaluation_payload
    assert "profile" not in evaluation_payload


def test_cli_train_parser_uses_operational_defaults():
    args = build_parser().parse_args(["train"])

    assert args.profile == ""
    assert args.horizon == 5
    assert args.n_jobs == 4
    assert args.min_history == 20
    assert args.min_train_rows == 100

    override_args = build_parser().parse_args(
        [
            "train",
            "--horizon",
            "7",
            "--n-jobs",
            "2",
            "--min-history",
            "30",
            "--min-train-rows",
            "120",
        ]
    )

    assert override_args.horizon == 7
    assert override_args.n_jobs == 2
    assert override_args.min_history == 30
    assert override_args.min_train_rows == 120


def test_cli_train_help_lists_prediction_defaults(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["train", "--help"])

    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    assert "Train/evaluate prediction model. Profile-independent." in help_text
    assert "--profile" not in help_text
    assert "Prediction horizon in trading days. Default: 5" in help_text
    assert "Parallel workers. Default: 4" in help_text
    assert "Minimum price history. Default: 20" in help_text
    assert "Minimum training rows. Default: 100" in help_text


def test_cli_train_falls_back_when_requested_real_engine_is_unavailable(
    tmp_path: Path,
    monkeypatch,
    capsys,
):
    import pymercator.cli_train as train_mod

    matrix = tmp_path / "matrix.csv"
    prices_dir = tmp_path / "prices"
    dataset = tmp_path / "dataset.csv"
    evaluation = tmp_path / "evaluation.json"
    matrix.write_text("ticker,sector,return_1d\nPRIO3,OilGas,1\n", encoding="utf-8")
    prices_dir.mkdir()
    calls = []

    def fake_lab(**kwargs):
        calls.append(kwargs)
        Path(kwargs["dataset_output"]).write_text(
            "date,ticker\n2025-01-01,PRIO3\n2025-01-02,PRIO3\n",
            encoding="utf-8",
        )
        Path(kwargs["evaluation_output"]).write_text("{}", encoding="utf-8")
        if kwargs["engines"] == ["extratrees"]:
            return {
                "dataset": {"rows": 2, "output": str(kwargs["dataset_output"])},
                "evaluation": {
                    "rows": 2,
                    "evaluated_rows": 1,
                    "engines": kwargs["engines"],
                    "engine_status": {"extratrees": "UNAVAILABLE"},
                    "output": str(kwargs["evaluation_output"]),
                },
            }

        return {
            "dataset": {"rows": 2, "output": str(kwargs["dataset_output"])},
            "evaluation": {
                "rows": 2,
                "evaluated_rows": 1,
                "engines": kwargs["engines"],
                "engine_status": {},
                "output": str(kwargs["evaluation_output"]),
            },
        }

    monkeypatch.setattr(train_mod, "run_prediction_lab", fake_lab)

    exit_code = main(
        [
            "train",
            "--matrix",
            str(matrix),
            "--prices-dir",
            str(prices_dir),
            "--dataset-output",
            str(dataset),
            "--evaluation-output",
            str(evaluation),
            "--min-train-rows",
            "2",
            "--engines",
            "extratrees",
            "--json",
        ]
    )

    assert exit_code == 0
    assert [call["engines"] for call in calls] == [["extratrees"], ["rolling_majority"]]
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "FALLBACK"
    assert payload["engine_used"] == "rolling_majority"
    assert payload["is_baseline"] is True
    assert payload["fallback_reason"].startswith("extratrees failed:")


def test_cli_train_falls_back_without_false_ok_when_no_real_engine_is_available(
    tmp_path: Path,
    monkeypatch,
    capsys,
):
    import pymercator.cli_train as train_mod

    matrix = tmp_path / "matrix.csv"
    prices_dir = tmp_path / "prices"
    dataset = tmp_path / "dataset.csv"
    evaluation = tmp_path / "evaluation.json"
    matrix.write_text("ticker,sector,return_1d\nPRIO3,OilGas,1\n", encoding="utf-8")
    prices_dir.mkdir()
    monkeypatch.setattr(train_mod, "SKLEARN_AVAILABLE", False)
    monkeypatch.setattr(train_mod, "XGBOOST_AVAILABLE", False)
    monkeypatch.setattr(train_mod, "CATBOOST_AVAILABLE", False)

    def fake_lab(**kwargs):
        Path(kwargs["dataset_output"]).write_text(
            "date,ticker\n2025-01-01,PRIO3\n2025-01-02,PRIO3\n",
            encoding="utf-8",
        )
        Path(kwargs["evaluation_output"]).write_text("{}", encoding="utf-8")
        return {
            "dataset": {"rows": 2, "output": str(kwargs["dataset_output"])},
            "evaluation": {
                "rows": 2,
                "evaluated_rows": 1,
                "engines": kwargs["engines"],
                "engine_status": {"rolling_majority": "BASELINE"},
                "output": str(kwargs["evaluation_output"]),
            },
        }

    monkeypatch.setattr(train_mod, "run_prediction_lab", fake_lab)

    exit_code = main(
        [
            "train",
            "--matrix",
            str(matrix),
            "--prices-dir",
            str(prices_dir),
            "--dataset-output",
            str(dataset),
            "--evaluation-output",
            str(evaluation),
            "--min-train-rows",
            "2",
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "FALLBACK"
    assert payload["engine_used"] == "rolling_majority"
    assert payload["is_baseline"] is True
