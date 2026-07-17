import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from genlab_api.db import Base, get_db
from genlab_api.main import app
from genlab_api.models import Dataset, Experiment, ExperimentStatus, User
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


def test_regression_result_document_matches_srbench_style_fields():
    document = build_experiment_json(
        dataset_name="192_vineyard",
        algorithm="m5gpRegressor",
        params={"generations": 40, "functions_set": ["+", "-"]},
        random_state=860,
        process_time=48.14,
        wall_time=48.13,
        target_noise=0.0,
        feature_noise=0.0,
        model_size=102,
        symbolic_model="X_0 + X_1",
        task_type="regression",
        train_metrics={"mse": 3.8, "mae": 1.4, "r2": 0.82},
        test_metrics={"mse": 6.2, "mae": 2.0, "r2": 0.41},
    )

    expected_fields = {
        "dataset",
        "algorithm",
        "params",
        "random_state",
        "process_time",
        "time_time",
        "target_noise",
        "feature_noise",
        "model_size",
        "symbolic_model",
        "mse_train",
        "mae_train",
        "r2_train",
        "mse_test",
        "mae_test",
        "r2_test",
    }
    assert set(document) == expected_fields
    assert document["dataset"] == "192_vineyard"
    assert document["algorithm"] == "m5gpRegressor"
    assert document["random_state"] == 860
    assert document["model_size"] == 102
    assert document["r2_test"] == 0.41
    json.dumps(document, allow_nan=False)


def test_completed_experiment_can_download_json_artifact(tmp_path: Path):
    Session = _test_database()
    db = Session()
    user = User(
        email="artifact@example.com",
        full_name="Artifact User",
        password_hash="unused",
    )
    db.add(user)
    db.flush()
    dataset_file = tmp_path / "dataset.tsv"
    dataset_file.write_text("x\ty\n1\t2\n", encoding="utf-8")
    dataset = Dataset(
        owner_id=user.id,
        name="Dataset",
        original_name="dataset.tsv",
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
    payload = {"dataset": "dataset", "algorithm": "m5gpRegressor"}
    (artifact_dir / "experiment.json").write_text(
        json.dumps(payload), encoding="utf-8"
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
            f"/api/v1/experiments/{experiment.id}/artifacts/experiment.json"
        )
        assert response.status_code == 200
        assert response.json() == payload
        assert "application/json" in response.headers["content-type"]
    finally:
        app.dependency_overrides.clear()
        db.close()
