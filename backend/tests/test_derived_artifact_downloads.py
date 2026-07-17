import json
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from genlab_api.db import Base, get_db
from genlab_api.main import app
from genlab_api.models import Dataset, Experiment, ExperimentStatus, User
from genlab_api.security import current_user


def _test_database():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_history_and_test_result_buttons_download_derived_json(tmp_path: Path):
    Session = _test_database()
    db = Session()
    user = User(
        email="derived@example.com",
        full_name="Derived Artifacts",
        password_hash="unused",
    )
    db.add(user)
    db.flush()

    dataset_path = tmp_path / "dataset.tsv"
    dataset_path.write_text("x\ty\n1\t2\n", encoding="utf-8")
    dataset = Dataset(
        owner_id=user.id,
        name="Dataset",
        original_name="dataset.tsv",
        path=str(dataset_path),
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
    pd.DataFrame(
        {
            "sample": [0, 1],
            "actual": [1.0, 2.0],
            "prediction": [1.1, 1.9],
        }
    ).to_csv(artifact_dir / "predictions.csv", index=False)

    experiment = Experiment(
        owner_id=user.id,
        dataset_id=dataset.id,
        name="Completed",
        task_type="regression",
        target_column="y",
        parameters={"generations": 2},
        status=ExperimentStatus.completed.value,
        artifact_dir=str(artifact_dir),
        progress={
            "history": [
                {"generation": 1, "fit": 0.9},
                {"generation": 2, "fit": 0.7},
            ]
        },
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

        history_response = client.get(
            f"/api/v1/experiments/{experiment.id}/artifacts/"
            "generation_history.json"
        )
        assert history_response.status_code == 200
        assert "application/json" in history_response.headers["content-type"]
        assert history_response.json()["history"] == [
            {"generation": 1, "fit": 0.9},
            {"generation": 2, "fit": 0.7},
        ]

        results_response = client.get(
            f"/api/v1/experiments/{experiment.id}/artifacts/"
            "test_results.json"
        )
        assert results_response.status_code == 200
        assert "application/json" in results_response.headers["content-type"]
        assert results_response.json() == {
            "task_type": "regression",
            "sample": [0, 1],
            "actual": [1.0, 2.0],
            "prediction": [1.1, 1.9],
        }

        assert json.loads(
            (artifact_dir / "generation_history.json").read_text()
        )["history"]
        assert (artifact_dir / "test_results.json").is_file()
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_legacy_artifact_urls_work_when_database_artifact_dir_is_empty(
    tmp_path: Path, monkeypatch,
):
    from types import SimpleNamespace
    import genlab_api.routers.experiments as experiment_routes

    Session = _test_database()
    db = Session()
    user = User(
        email="legacy-derived@example.com",
        full_name="Legacy Derived Artifacts",
        password_hash="unused",
    )
    db.add(user)
    db.flush()

    dataset_path = tmp_path / "legacy.tsv"
    dataset_path.write_text("x\ty\n1\t2\n", encoding="utf-8")
    dataset = Dataset(
        owner_id=user.id,
        name="Legacy dataset",
        original_name="legacy.tsv",
        path=str(dataset_path),
        sha256="2" * 64,
        rows=1,
        columns=2,
        column_names=["x", "y"],
        dtypes={"x": "int64", "y": "int64"},
    )
    db.add(dataset)
    db.flush()

    experiment = Experiment(
        owner_id=user.id,
        dataset_id=dataset.id,
        name="Legacy completed",
        task_type="regression",
        target_column="y",
        parameters={"generations": 2},
        status=ExperimentStatus.completed.value,
        artifact_dir=None,
        progress={
            "history": [
                {"generation": 1, "fit": 1.2},
                {"generation": 2, "fit": 0.8},
            ]
        },
    )
    db.add(experiment)
    db.commit()

    data_dir = tmp_path / "data"
    default_artifact_dir = data_dir / "artifacts" / user.id / experiment.id
    default_artifact_dir.mkdir(parents=True)
    pd.DataFrame(
        {
            "sample": [0, 1],
            "actual": [2.0, 3.0],
            "prediction": [2.1, 2.9],
        }
    ).to_csv(default_artifact_dir / "predictions.csv", index=False)

    monkeypatch.setattr(
        experiment_routes,
        "get_settings",
        lambda: SimpleNamespace(
            data_dir=data_dir,
            artifact_dir=data_dir / "artifacts",
        ),
    )

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
            f"/api/v1/experiments/{experiment.id}/artifacts/"
            "generation_history.json"
        )
        assert history.status_code == 200
        assert history.json()["history"][-1] == {
            "generation": 2,
            "fit": 0.8,
        }

        results = client.get(
            f"/api/v1/experiments/{experiment.id}/artifacts/"
            "test_results.json"
        )
        assert results.status_code == 200
        assert results.json()["prediction"] == [2.1, 2.9]
    finally:
        app.dependency_overrides.clear()
        db.close()
