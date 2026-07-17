import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from genlab_api.db import Base, get_db
from genlab_api.main import app
from genlab_api.models import Dataset, Experiment, ExperimentStatus, User
from genlab_api.schemas import ExperimentCreate
from genlab_api.security import current_user
from genlab_api.worker import build_experiment_json


def _test_database():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_classification_parameters_are_task_specific():
    payload = ExperimentCreate(
        name="Classifier",
        dataset_id="dataset",
        task_type="classification",
        target_column="class",
        parameters={"evaluationMethod": 2, "scorer": 2},
    )
    assert payload.parameters["evaluationMethod"] == 2
    assert payload.parameters["crossVal"] is True
    assert payload.parameters["k"] == 3
    assert payload.parameters["averageMode"] == "macro"

    with pytest.raises(ValidationError):
        ExperimentCreate(
            name="Invalid classifier",
            dataset_id="dataset",
            task_type="classification",
            target_column="class",
            parameters={"evaluationMethod": 4},
        )


def test_classification_result_document_has_classification_metrics():
    document = build_experiment_json(
        dataset_name="classes",
        algorithm="m5gpClassifier",
        params={"evaluationMethod": 0},
        random_state=42,
        process_time=1.0,
        wall_time=1.1,
        model_size=20,
        symbolic_model="X_0",
        task_type="classification",
        train_metrics={"accuracy": 0.9, "f1_macro": 0.88},
        test_metrics={"accuracy": 0.8, "f1_macro": 0.75},
    )
    assert document["algorithm"] == "m5gpClassifier"
    assert document["accuracy_train"] == 0.9
    assert document["accuracy_test"] == 0.8
    assert document["mse_test"] is None
    json.dumps(document, allow_nan=False)


def test_visualization_endpoint_returns_history_and_sampled_test_results(
    tmp_path: Path,
):
    Session = _test_database()
    db = Session()
    user = User(
        email="charts@example.com",
        full_name="Charts User",
        password_hash="unused",
    )
    db.add(user)
    db.flush()
    dataset_file = tmp_path / "dataset.csv"
    dataset_file.write_text("x,y\n1,2\n", encoding="utf-8")
    dataset = Dataset(
        owner_id=user.id,
        name="Dataset",
        original_name="dataset.csv",
        path=str(dataset_file),
        sha256="0" * 64,
        rows=1,
        columns=2,
        column_names=["x", "y"],
        dtypes={"x": "int64", "y": "int64"},
    )
    db.add(dataset)
    db.flush()
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "generation_history.json").write_text(
        json.dumps(
            {
                "task_type": "regression",
                "fit_label": "Train Fit",
                "history": [
                    {"generation": 1, "fit": 1.0},
                    {"generation": 2, "fit": 0.5},
                ],
            }
        ),
        encoding="utf-8",
    )
    count = 600
    (artifact_dir / "test_results.json").write_text(
        json.dumps(
            {
                "task_type": "regression",
                "sample": list(range(count)),
                "actual": [float(value) for value in range(count)],
                "prediction": [float(value) + 0.1 for value in range(count)],
            }
        ),
        encoding="utf-8",
    )
    experiment = Experiment(
        owner_id=user.id,
        dataset_id=dataset.id,
        name="Completed",
        task_type="regression",
        target_column="y",
        parameters={},
        status=ExperimentStatus.completed.value,
        artifact_dir=str(artifact_dir),
    )
    db.add(experiment)
    db.commit()

    def override_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[current_user] = lambda: user
    try:
        client = TestClient(app)
        response = client.get(
            f"/api/v1/experiments/{experiment.id}/visualization"
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["generation_history"][1]["fit"] == 0.5
        assert payload["test_results"]["total_points"] == 600
        assert payload["test_results"]["displayed_points"] <= 300
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_dedicated_visualization_json_endpoints_are_registered_and_return_data(
    tmp_path: Path,
):
    Session = _test_database()
    db = Session()
    user = User(
        email="dedicated@example.com",
        full_name="Dedicated Routes",
        password_hash="unused",
    )
    db.add(user)
    db.flush()
    dataset_file = tmp_path / "dataset.csv"
    dataset_file.write_text("x,y\n1,2\n", encoding="utf-8")
    dataset = Dataset(
        owner_id=user.id,
        name="Dataset",
        original_name="dataset.csv",
        path=str(dataset_file),
        sha256="1" * 64,
        rows=1,
        columns=2,
        column_names=["x", "y"],
        dtypes={"x": "int64", "y": "int64"},
    )
    db.add(dataset)
    db.flush()
    artifact_dir = tmp_path / "artifacts-dedicated"
    artifact_dir.mkdir()
    (artifact_dir / "generation_history.json").write_text(
        json.dumps(
            {
                "task_type": "regression",
                "fit_label": "Train Fit",
                "history": [{"generation": 1, "fit": 0.5}],
            }
        ),
        encoding="utf-8",
    )
    (artifact_dir / "test_results.json").write_text(
        json.dumps(
            {
                "task_type": "regression",
                "sample": [0, 1, 2],
                "actual": [1.0, 2.0, 3.0],
                "prediction": [1.1, 1.9, 3.2],
            }
        ),
        encoding="utf-8",
    )
    experiment = Experiment(
        owner_id=user.id,
        dataset_id=dataset.id,
        name="Completed dedicated",
        task_type="regression",
        target_column="y",
        parameters={},
        status=ExperimentStatus.completed.value,
        artifact_dir=str(artifact_dir),
    )
    db.add(experiment)
    db.commit()

    def override_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[current_user] = lambda: user
    try:
        client = TestClient(app)
        history = client.get(
            f"/api/v1/experiments/{experiment.id}/generation-history"
        )
        assert history.status_code == 200
        assert history.json()["history"][0]["generation"] == 1

        complete = client.get(
            f"/api/v1/experiments/{experiment.id}/test-results"
        )
        assert complete.status_code == 200
        assert complete.json()["displayed_points"] == 3

        sampled = client.get(
            f"/api/v1/experiments/{experiment.id}/test-results?max_points=2"
        )
        assert sampled.status_code == 200
        assert sampled.json()["displayed_points"] == 2

        paths = client.get("/openapi.json").json()["paths"]
        assert (
            "/api/v1/experiments/{experiment_id}/generation-history" in paths
        )
        assert "/api/v1/experiments/{experiment_id}/test-results" in paths
    finally:
        app.dependency_overrides.clear()
        db.close()
