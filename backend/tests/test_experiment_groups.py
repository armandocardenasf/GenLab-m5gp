from __future__ import annotations

import pytest
from pydantic import ValidationError

from genlab_api.lab_schemas import ExperimentGroupCreate
from genlab_api.services.lab import SYSTEM_PRESETS, validation_dict
from genlab_api.worker import _constructor_parameters


def test_system_profiles_have_expected_cost_levels():
    assert [item["parameters"]["generations"] for item in SYSTEM_PRESETS] == [30, 50, 100]
    assert [item["parameters"]["Individuals"] for item in SYSTEM_PRESETS] == [256, 512, 1024]
    assert [item["parameters"]["GenesIndividuals"] for item in SYSTEM_PRESETS] == [64, 64, 128]
    defaults = [item for item in SYSTEM_PRESETS if item["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["id"] == "system-standard"


def test_holdout_requires_train_plus_test_equal_one():
    with pytest.raises(ValueError):
        validation_dict({"strategy": "holdout", "train_size": 0.8, "test_size": 0.3})


def test_kfold_derives_train_and_test_proportion():
    value = validation_dict({"strategy": "kfold", "folds": 5})
    assert value["train_size"] == pytest.approx(0.8)
    assert value["test_size"] == pytest.approx(0.2)


def test_group_schema_rejects_invalid_regression_evaluation_method():
    with pytest.raises(ValidationError):
        ExperimentGroupCreate.model_validate(
            {
                "name": "demo",
                "task_type": "regression",
                "datasets": [{"dataset_id": "d", "target_column": "y"}],
                "parameters": {"evaluationMethod": 99},
            }
        )


def test_constructor_parameters_forward_future_split_arguments_when_declared():
    class Estimator:
        def __init__(self, generations=50, train_size=0.75, test_size=0.25):
            pass

    filtered = _constructor_parameters(
        Estimator,
        {
            "generations": 30,
            "train_size": 0.8,
            "test_size": 0.2,
            "internal": "ignored",
        },
    )
    assert filtered == {"generations": 30, "train_size": 0.8, "test_size": 0.2}
