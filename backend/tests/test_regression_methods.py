from __future__ import annotations

import pytest
from pydantic import ValidationError

from genlab_api.schemas import ExperimentCreate


@pytest.mark.parametrize("evaluation_method", range(11))
def test_all_original_regression_methods_are_accepted(evaluation_method: int):
    experiment = ExperimentCreate(
        name="Regression method test",
        dataset_id="dataset-id",
        task_type="regression",
        target_column="target",
        parameters={
            "evaluationMethod": evaluation_method,
            "scorer": 0,
        },
    )
    assert experiment.parameters["evaluationMethod"] == evaluation_method


def test_regression_method_outside_original_range_is_rejected():
    with pytest.raises(ValidationError):
        ExperimentCreate(
            name="Invalid regression method",
            dataset_id="dataset-id",
            task_type="regression",
            target_column="target",
            parameters={"evaluationMethod": 11, "scorer": 0},
        )


@pytest.mark.parametrize("scorer", [0, 1, 2])
def test_original_regression_scorers_are_accepted(scorer: int):
    experiment = ExperimentCreate(
        name="Regression scorer test",
        dataset_id="dataset-id",
        task_type="regression",
        target_column="target",
        parameters={"evaluationMethod": 4, "scorer": scorer},
    )
    assert experiment.parameters["scorer"] == scorer
