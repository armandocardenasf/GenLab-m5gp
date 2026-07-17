from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from genlab_api.db import Base, get_db
from genlab_api.main import app
from genlab_api.models import Dataset, Experiment, ExperimentStatus, User
from genlab_api.routers import experiments as experiments_router
from genlab_api.security import current_user
from genlab_api.services.experiments import reset_for_run
from genlab_api.worker import generation_percent


def _test_database():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_generation_percent_uses_original_generation_count():
    assert generation_percent(0, 40) == 8
    assert generation_percent(20, 40) == 49
    assert generation_percent(40, 40) == 90
    assert generation_percent(99, 40) == 90


def test_reset_for_run_preserves_configuration_and_removes_outputs(tmp_path: Path):
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "metrics.json").write_text("{}", encoding="utf-8")
    log_path = tmp_path / "experiment.log"
    log_path.write_text("old log", encoding="utf-8")

    experiment = Experiment(
        owner_id="owner",
        dataset_id="dataset",
        name="Experiment",
        task_type="regression",
        target_column="y",
        parameters={"generations": 40},
        status=ExperimentStatus.completed.value,
        metrics={"r2": 0.9},
        symbolic_model="x0",
        complexity="1",
        artifact_dir=str(artifact_dir),
        log_path=str(log_path),
    )

    reset_for_run(experiment)

    assert experiment.parameters == {"generations": 40}
    assert experiment.target_column == "y"
    assert experiment.metrics is None
    assert experiment.symbolic_model is None
    assert experiment.status == ExperimentStatus.created.value
    assert not artifact_dir.exists()
    assert not log_path.exists()


def test_delete_and_rerun_endpoints(monkeypatch, tmp_path: Path):
    Session = _test_database()
    db = Session()
    user = User(
        email="user@example.com",
        full_name="Test User",
        password_hash="unused",
    )
    db.add(user)
    db.flush()
    dataset_path = tmp_path / "dataset.csv"
    dataset_path.write_text("x,y\n1,2\n", encoding="utf-8")
    dataset = Dataset(
        owner_id=user.id,
        name="Dataset",
        original_name="dataset.csv",
        path=str(dataset_path),
        sha256="0" * 64,
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
        name="Experiment",
        task_type="regression",
        target_column="y",
        parameters={"generations": 2},
        status=ExperimentStatus.completed.value,
        metrics={"r2": 0.5},
    )
    removable = Experiment(
        owner_id=user.id,
        dataset_id=dataset.id,
        name="Remove me",
        task_type="regression",
        target_column="y",
        parameters={},
        status=ExperimentStatus.created.value,
    )
    db.add_all([experiment, removable])
    db.commit()

    def override_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[current_user] = lambda: user

    def fake_launch(session, current):
        reset_for_run(current)
        current.status = ExperimentStatus.reserved.value
        current.gpu_id = 0
        current.worker_pid = 1234
        current.progress = {"stage": "reserved", "percent": 1}
        session.commit()
        return 1234

    monkeypatch.setattr(experiments_router, "launch", fake_launch)

    try:
        client = TestClient(app)
        rerun_response = client.post(
            f"/api/v1/experiments/{experiment.id}/rerun"
        )
        assert rerun_response.status_code == 202
        payload = rerun_response.json()
        assert payload["status"] == ExperimentStatus.reserved.value
        assert payload["parameters"] == {"generations": 2}
        assert payload["metrics"] is None

        delete_response = client.delete(
            f"/api/v1/experiments/{removable.id}"
        )
        assert delete_response.status_code == 204
        with Session() as check_db:
            assert check_db.get(Experiment, removable.id) is None
    finally:
        app.dependency_overrides.clear()
        db.close()
