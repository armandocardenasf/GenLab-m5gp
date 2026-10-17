from __future__ import annotations

import io
import zipfile
from types import SimpleNamespace

from genlab_api.services.exports import export_xlsx_bytes
from genlab_api.services.lab import REGRESSION_FUNCTION_SET, SYSTEM_PRESETS, summarize_runs


EXPECTED_FUNCTIONS = [
    "+", "-", "*", "/", "sin", "cos", "tan", "tanh",
    "exp", "log", "Abs", "sqrt",
]


def test_regression_system_profiles_match_requested_defaults():
    profiles = {
        item["name"]: item
        for item in SYSTEM_PRESETS
        if item["task_type"] == "regression"
    }
    expected = {
        "Mínima": (15, 64, 256),
        "Estándar": (40, 64, 512),
        "Intensiva": (128, 128, 1024),
    }
    assert REGRESSION_FUNCTION_SET == EXPECTED_FUNCTIONS
    for name, (generations, genes, individuals) in expected.items():
        parameters = profiles[name]["parameters"]
        assert parameters["evaluationMethod"] == 4
        assert parameters["generations"] == generations
        assert parameters["GenesIndividuals"] == genes
        assert parameters["Individuals"] == individuals
        assert parameters["maxRandomConstant"] == 1
        assert parameters["functions_set"] == EXPECTED_FUNCTIONS
    assert profiles["Estándar"]["is_default"] is True


def test_model_size_and_training_time_are_aggregated():
    runs = [
        SimpleNamespace(metrics={
            "train": {"r2": 0.90, "rmse": 1.0, "mse": 1.0, "mae": 0.8},
            "test": {"r2": 0.80, "rmse": 2.0, "mse": 4.0, "mae": 1.5},
            "model_size": 12,
            "training_time": 3.0,
        }),
        SimpleNamespace(metrics={
            "train": {"r2": 0.92, "rmse": 0.9, "mse": 0.81, "mae": 0.7},
            "test": {"r2": 0.84, "rmse": 1.8, "mse": 3.24, "mae": 1.4},
            "model_size": 16,
            "training_time": 5.0,
        }),
    ]
    summary = summarize_runs(runs, "regression")
    assert summary["execution"]["model_size"]["mean"] == 14
    assert summary["execution"]["training_time"]["mean"] == 4
    assert summary["test"]["r2"]["n"] == 2


def test_xlsx_export_is_a_valid_openxml_package():
    payload = {
        "experiment": {
            "id": "exp-1",
            "name": "Demo",
            "task_type": "regression",
            "preset_name": "Estándar",
            "runs_per_dataset": 2,
            "validation": {"strategy": "holdout"},
            "parameters": {"generations": 40},
            "created_at": "2026-10-15T00:00:00",
            "status": "completed",
        },
        "scope": "experiment",
        "dataset_id": None,
        "aggregate": {
            "overall": {
                "test": {"r2": {"mean": 0.8, "std": 0.1, "min": 0.7, "max": 0.9, "n": 2}},
                "execution": {"model_size": {"mean": 14, "std": 2, "min": 12, "max": 16, "n": 2}},
            },
            "by_dataset": [],
        },
        "runs": [],
    }
    data = export_xlsx_bytes(payload)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = set(archive.namelist())
        assert "xl/workbook.xml" in names
        assert "xl/worksheets/sheet1.xml" in names
        assert "xl/worksheets/sheet2.xml" in names
        assert "xl/worksheets/sheet3.xml" in names
