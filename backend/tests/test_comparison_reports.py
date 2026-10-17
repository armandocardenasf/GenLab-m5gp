from __future__ import annotations

import io
import zipfile

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from genlab_api.db import Base
from genlab_api.lab_models import (
    ComparisonReport,
    ExperimentDatasetLink,
    ExperimentGroup,
    ExperimentRunLink,
)
from genlab_api.models import Dataset, Experiment, User
from genlab_api.services.comparison_exports import comparison_xlsx_bytes
from genlab_api.services.comparisons import build_comparison_snapshot


def _dataset(owner_id: str, index: int) -> Dataset:
    return Dataset(
        owner_id=owner_id,
        name=f"Dataset {index}",
        original_name=f"dataset_{index}.csv",
        path=f"/tmp/dataset_{index}.csv",
        sha256=f"{index:064d}"[-64:],
        rows=100 * (index + 1),
        columns=6 + index,
        column_names=["x1", "x2", "target"],
        dtypes={"x1": "float64", "x2": "float64", "target": "float64"},
    )


def test_comparison_snapshot_wilcoxon_and_scaling():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(email="compare@example.com", full_name="Compare", password_hash="x")
        db.add(user)
        db.flush()
        datasets = [_dataset(user.id, index) for index in range(5)]
        db.add_all(datasets)
        db.flush()

        groups = []
        for group_index, generations in enumerate((15, 40, 128)):
            group = ExperimentGroup(
                owner_id=user.id,
                name=f"Config {generations}",
                task_type="regression",
                parameters={
                    "generations": generations,
                    "Individuals": 256 * (group_index + 1),
                    "GenesIndividuals": 64,
                    "evaluationMethod": 4,
                },
                validation={"strategy": "holdout", "train_size": 0.75, "test_size": 0.25},
                runs_per_dataset=2,
                status="completed",
            )
            db.add(group)
            db.flush()
            groups.append(group)
            for position, dataset in enumerate(datasets):
                db.add(ExperimentDatasetLink(group_id=group.id, dataset_id=dataset.id, target_column="target", position=position))
                for repeat in range(2):
                    quality = 0.70 + group_index * 0.05 + position * 0.005 + repeat * 0.001
                    run = Experiment(
                        owner_id=user.id,
                        dataset_id=dataset.id,
                        name=f"run-{group_index}-{position}-{repeat}",
                        task_type="regression",
                        target_column="target",
                        parameters={},
                        status="completed",
                        metrics={
                            "train": {"r2": quality + 0.02, "rmse": 1.0},
                            "test": {"r2": quality, "rmse": 1.0 / quality, "mae": 0.5 / quality},
                            "model_size": 50 + group_index * 10,
                            "training_time": (group_index + 1) * (position + 1) * 2.0,
                        },
                    )
                    db.add(run)
                    db.flush()
                    db.add(ExperimentRunLink(group_id=group.id, run_id=run.id, repeat_index=repeat, fold_index=None, seed=42 + repeat))
        db.commit()

        snapshot = build_comparison_snapshot(db, groups, "regression", "r2_test", 0.05)
        assert len(snapshot["experiments"]) == 3
        assert len(snapshot["datasets"]) == 5
        assert snapshot["rankings"]["r2_test"][0]["label"] == "Config 128"
        assert len(snapshot["wilcoxon"]["cells"]) == 3
        assert all(cell["n_pairs"] == 5 for cell in snapshot["wilcoxon"]["cells"])
        assert all(not cell["exploratory"] for cell in snapshot["wilcoxon"]["cells"])
        assert len(snapshot["computational"]["samples"]) == 15
        assert any(item["parameter"] == "generations" for item in snapshot["varying_parameters"])

        report = ComparisonReport(
            owner_id=user.id,
            name="Comparativo",
            description="Prueba",
            task_type="regression",
            experiment_ids=[group.id for group in groups],
            config={"primary_metric": "r2_test", "alpha": 0.05},
            snapshot=snapshot,
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        assert report.id

        payload = {
            "id": report.id,
            "name": report.name,
            "description": report.description,
            "task_type": report.task_type,
            "experiment_ids": report.experiment_ids,
            "config": report.config,
            "created_at": report.created_at.isoformat(),
            "updated_at": report.updated_at.isoformat(),
            "analysis": snapshot,
        }
        workbook = comparison_xlsx_bytes(payload)
        with zipfile.ZipFile(io.BytesIO(workbook)) as archive:
            names = set(archive.namelist())
            assert "xl/workbook.xml" in names
            workbook_xml = archive.read("xl/workbook.xml").decode("utf-8")
            assert "Wilcoxon" in workbook_xml
            assert "Computacional" in workbook_xml


def test_classification_comparison_metrics():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(email="class@example.com", full_name="Class", password_hash="x")
        db.add(user)
        db.flush()
        datasets = [_dataset(user.id, index) for index in range(5)]
        db.add_all(datasets)
        db.flush()
        groups = []
        for group_index in range(2):
            group = ExperimentGroup(
                owner_id=user.id,
                name=f"Classifier {group_index}",
                task_type="classification",
                parameters={"generations": 40 + group_index * 20, "Individuals": 512},
                validation={"strategy": "holdout", "train_size": 0.75, "test_size": 0.25},
                runs_per_dataset=1,
                status="completed",
            )
            db.add(group)
            db.flush()
            groups.append(group)
            for position, dataset in enumerate(datasets):
                db.add(ExperimentDatasetLink(group_id=group.id, dataset_id=dataset.id, target_column="target", position=position))
                score = 0.75 + group_index * 0.05 + position * 0.002
                run = Experiment(
                    owner_id=user.id,
                    dataset_id=dataset.id,
                    name=f"class-run-{group_index}-{position}",
                    task_type="classification",
                    target_column="target",
                    parameters={},
                    status="completed",
                    metrics={
                        "train": {"accuracy": score + 0.02, "f1_macro": score + 0.01, "precision_macro": score, "recall_macro": score},
                        "test": {"accuracy": score, "f1_macro": score - 0.01, "precision_macro": score - 0.02, "recall_macro": score - 0.015},
                        "model_size": 40 + group_index * 5,
                        "training_time": 2.0 + group_index,
                    },
                )
                db.add(run)
                db.flush()
                db.add(ExperimentRunLink(group_id=group.id, run_id=run.id, repeat_index=0, fold_index=None, seed=42))
        db.commit()
        snapshot = build_comparison_snapshot(db, groups, "classification", "f1_macro_test", 0.05)
        assert snapshot["rankings"]["f1_macro_test"][0]["label"] == "Classifier 1"
        assert snapshot["wilcoxon"]["cells"][0]["n_pairs"] == 5
        assert snapshot["coverage"]["comparable_on_common_datasets"] is True
