from __future__ import annotations

import math
from pathlib import Path
from statistics import mean, pstdev

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..lab_models import (
    Batch,
    BatchExperimentLink,
    ExperimentDatasetLink,
    ExperimentGroup,
    ExperimentRunLink,
    ParameterPreset,
)
from ..models import Dataset, Experiment, ExperimentStatus, GPULease
from .experiments import ACTIVE_STATUSES, cleanup_outputs, launch


# Operational profiles.  They are intentionally labelled as presets rather than
# scientifically optimal configurations; investigators can create their own
# reproducible presets from the Advanced Parameters page.
COMMON_EVOLUTION_PARAMETERS = {
    "mutationProb": 0.10,
    "mutationDeleteRateProb": 0.05,
    "sizeTournament": 0.15,
    "genOperatorProb": 0.45,
    "genVariableProb": 0.40,
    "genConstantProb": 0.10,
    "genNoopProb": 0.001,
    "log": 1,
    "verbose": 1,
}

REGRESSION_FUNCTION_SET = [
    "+",
    "-",
    "*",
    "/",
    "sin",
    "cos",
    "tan",
    "tanh",
    "exp",
    "log",
    "Abs",
    "sqrt",
]


def _regression_profile(*, generations: int, individuals: int, genes: int) -> dict:
    return {
        **COMMON_EVOLUTION_PARAMETERS,
        "evaluationMethod": 4,
        "generations": generations,
        "GenesIndividuals": genes,
        "Individuals": individuals,
        "maxRandomConstant": 1,
        "functions_set": list(REGRESSION_FUNCTION_SET),
    }


SYSTEM_PRESETS = [
    {
        "id": "system-minimum",
        "name": "Mínima",
        "description": "Perfil mínimo para regresión simbólica con evaluación Ridge (método 4).",
        "task_type": "regression",
        "is_default": False,
        "system": True,
        "parameters": _regression_profile(generations=15, individuals=256, genes=64),
    },
    {
        "id": "system-standard",
        "name": "Estándar",
        "description": "Perfil predeterminado para regresión simbólica con evaluación Ridge (método 4).",
        "task_type": "regression",
        "is_default": True,
        "system": True,
        "parameters": _regression_profile(generations=40, individuals=512, genes=64),
    },
    {
        "id": "system-intensive",
        "name": "Intensiva",
        "description": "Perfil intensivo para regresión simbólica con evaluación Ridge (método 4).",
        "task_type": "regression",
        "is_default": False,
        "system": True,
        "parameters": _regression_profile(generations=128, individuals=1024, genes=128),
    },
    {
        "id": "system-classification-standard",
        "name": "Clasificación estándar",
        "description": "Perfil de compatibilidad para experimentos de clasificación; usa el método de clasificación predeterminado.",
        "task_type": "classification",
        "is_default": False,
        "system": True,
        "parameters": {
            **COMMON_EVOLUTION_PARAMETERS,
            "evaluationMethod": 0,
            "scorer": 0,
            "generations": 40,
            "GenesIndividuals": 64,
            "Individuals": 512,
            "maxRandomConstant": 1,
            "functions_set": list(REGRESSION_FUNCTION_SET),
        },
    },
]


def task_parameter_defaults(task_type: str) -> dict:
    if task_type == "classification":
        return {
            "evaluationMethod": 0,
            "scorer": 0,
            "averageMode": "macro",
        }
    return {"evaluationMethod": 4, "scorer": 0}


def validation_dict(value: dict | None = None) -> dict:
    result = {
        "strategy": "holdout",
        "train_size": 0.75,
        "test_size": 0.25,
        "random_state": 42,
        "folds": 5,
        "shuffle": True,
    }
    result.update(value or {})
    result["strategy"] = str(result.get("strategy", "holdout")).lower()
    if result["strategy"] not in {"holdout", "kfold"}:
        raise ValueError("strategy debe ser holdout o kfold")
    result["train_size"] = float(result.get("train_size", 0.75))
    result["test_size"] = float(result.get("test_size", 0.25))
    result["random_state"] = int(result.get("random_state", 42))
    result["folds"] = max(2, int(result.get("folds", 5)))
    result["shuffle"] = bool(result.get("shuffle", True))
    if result["strategy"] == "holdout":
        if result["train_size"] <= 0 or result["test_size"] <= 0:
            raise ValueError("train_size y test_size deben ser mayores que cero")
        if abs(result["train_size"] + result["test_size"] - 1.0) > 1e-6:
            raise ValueError("train_size + test_size debe ser igual a 1.0")
    else:
        result["train_size"] = (result["folds"] - 1) / result["folds"]
        result["test_size"] = 1 / result["folds"]
    return result


def effective_preset_list(db: Session, owner_id: str) -> list[dict]:
    custom = list(
        db.scalars(
            select(ParameterPreset)
            .where(ParameterPreset.owner_id == owner_id)
            .order_by(ParameterPreset.name)
        )
    )
    custom_default = any(item.is_default for item in custom)
    system = []
    for item in SYSTEM_PRESETS:
        current = dict(item)
        if custom_default:
            current["is_default"] = False
        system.append(current)
    system.extend(
        {
            "id": item.id,
            "name": item.name,
            "description": item.description,
            "task_type": item.task_type,
            "parameters": item.parameters or {},
            "is_default": item.is_default,
            "system": False,
        }
        for item in custom
    )
    return system


def group_dataset_links(db: Session, group_id: str) -> list[ExperimentDatasetLink]:
    return list(
        db.scalars(
            select(ExperimentDatasetLink)
            .where(ExperimentDatasetLink.group_id == group_id)
            .order_by(ExperimentDatasetLink.position)
        )
    )


def group_runs(db: Session, group_id: str) -> list[tuple[ExperimentRunLink, Experiment]]:
    rows: list[tuple[ExperimentRunLink, Experiment]] = []
    links = db.scalars(
        select(ExperimentRunLink)
        .where(ExperimentRunLink.group_id == group_id)
        .order_by(ExperimentRunLink.created_at, ExperimentRunLink.repeat_index)
    )
    for link in links:
        run = db.get(Experiment, link.run_id)
        if run is not None:
            rows.append((link, run))
    return rows


def _run_name(
    group: ExperimentGroup,
    dataset: Dataset,
    repeat_index: int,
    fold_index: int | None,
) -> str:
    parts = [group.name, dataset.name, f"R{repeat_index + 1}"]
    if fold_index is not None:
        parts.append(f"F{fold_index + 1}")
    return " · ".join(parts)


def create_runs(db: Session, group: ExperimentGroup) -> list[Experiment]:
    """Materialize queued run rows for a grouped experiment.

    Existing linked runs are never deleted or overwritten.  Calling this
    function repeatedly is therefore idempotent and preserves reproducibility.
    """
    existing = group_runs(db, group.id)
    if existing:
        return [run for _, run in existing]

    validation = validation_dict(group.validation)
    datasets = group_dataset_links(db, group.id)
    parameters = {**task_parameter_defaults(group.task_type), **(group.parameters or {})}
    base_seed = int(validation["random_state"])
    folds = validation["folds"] if validation["strategy"] == "kfold" else 1
    created: list[Experiment] = []

    for dataset_link in datasets:
        dataset = db.get(Dataset, dataset_link.dataset_id)
        if dataset is None:
            continue
        for repeat_index in range(max(int(group.runs_per_dataset), 1)):
            seed = base_seed + repeat_index
            for fold_index in range(folds):
                actual_fold = fold_index if validation["strategy"] == "kfold" else None
                split = {
                    **validation,
                    "random_state": seed,
                    "repeat_index": repeat_index,
                    "fold_index": actual_fold,
                }
                run_parameters = dict(parameters)
                # GenLab uses this nested value itself.  The public split values
                # are also kept at top level so _constructor_parameters() will
                # automatically forward them when future M5GP constructors
                # explicitly declare these arguments.
                run_parameters["_genlab_split"] = split
                run_parameters.update(
                    {
                        "train_size": validation["train_size"],
                        "test_size": validation["test_size"],
                        "random_state": seed,
                        "validation_strategy": validation["strategy"],
                        "cv_folds": validation["folds"],
                    }
                )
                run = Experiment(
                    owner_id=group.owner_id,
                    dataset_id=dataset.id,
                    name=_run_name(group, dataset, repeat_index, actual_fold),
                    task_type=group.task_type,
                    target_column=dataset_link.target_column,
                    parameters=run_parameters,
                    status="queued",
                    progress={
                        "stage": "queued",
                        "percent": 0,
                        "message": "Corrida en cola",
                    },
                )
                db.add(run)
                db.flush()
                db.add(
                    ExperimentRunLink(
                        group_id=group.id,
                        run_id=run.id,
                        repeat_index=repeat_index,
                        fold_index=actual_fold,
                        seed=seed,
                    )
                )
                created.append(run)

    group.status = "queued"
    db.commit()
    return created


def dispatch_queued(db: Session) -> list[str]:
    """Start queued runs until all currently available GPUs are occupied."""
    queued = list(
        db.scalars(
            select(Experiment)
            .where(Experiment.status == "queued")
            .order_by(Experiment.created_at.asc())
        )
    )
    started: list[str] = []
    for run in queued:
        if launch(db, run) is None:
            break
        started.append(run.id)
    return started


def status_counts(rows: list[tuple[ExperimentRunLink, Experiment]]) -> dict[str, int]:
    result: dict[str, int] = {}
    for _, run in rows:
        result[run.status] = result.get(run.status, 0) + 1
    return result


def resolved_group_status(group: ExperimentGroup, rows: list[tuple[ExperimentRunLink, Experiment]]) -> str:
    if not rows:
        return group.status
    statuses = [run.status for _, run in rows]
    if all(status == ExperimentStatus.completed.value for status in statuses):
        return "completed"
    if any(status in ACTIVE_STATUSES for status in statuses):
        return "running"
    if any(status == "queued" for status in statuses):
        return "queued"
    if all(
        status
        in {
            ExperimentStatus.failed.value,
            ExperimentStatus.cancelled.value,
            ExperimentStatus.rejected.value,
        }
        for status in statuses
    ):
        return "failed"
    return group.status


def _numeric_values(runs: list[Experiment], section: str, metric: str) -> list[float]:
    values: list[float] = []
    for run in runs:
        if not isinstance(run.metrics, dict):
            continue
        source = run.metrics.get(section, {})
        if not isinstance(source, dict):
            continue
        value = source.get(metric)
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            values.append(float(value))
    return values


def _top_level_numeric_values(runs: list[Experiment], metric: str) -> list[float]:
    values: list[float] = []
    for run in runs:
        if not isinstance(run.metrics, dict):
            continue
        value = run.metrics.get(metric)
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            values.append(float(value))
    return values


def _summary(values: list[float]) -> dict | None:
    if not values:
        return None
    return {
        "mean": mean(values),
        "std": pstdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
        "n": len(values),
    }


def summarize_runs(runs: list[Experiment], task_type: str) -> dict:
    metrics = (
        ["rmse", "mse", "mae", "r2"]
        if task_type == "regression"
        else ["accuracy", "f1_macro", "precision_macro", "recall_macro"]
    )
    result: dict[str, dict] = {"train": {}, "test": {}, "execution": {}}
    for section in ("train", "test"):
        for metric in metrics:
            item = _summary(_numeric_values(runs, section, metric))
            if item is not None:
                result[section][metric] = item
    for metric in ("model_size", "training_time"):
        item = _summary(_top_level_numeric_values(runs, metric))
        if item is not None:
            result["execution"][metric] = item
    if not result["execution"]:
        result.pop("execution")
    return result


def run_result_row(
    run: Experiment,
    link: ExperimentRunLink | None = None,
    dataset_name: str | None = None,
) -> dict:
    metrics = run.metrics if isinstance(run.metrics, dict) else {}
    train = metrics.get("train", {}) if isinstance(metrics.get("train"), dict) else {}
    test = metrics.get("test", {}) if isinstance(metrics.get("test"), dict) else {}
    progress = run.progress if isinstance(run.progress, dict) else {}
    return {
        "run_id": run.id,
        "run_name": run.name,
        "dataset_id": run.dataset_id,
        "dataset_name": dataset_name or run.dataset_id,
        "repeat_index": link.repeat_index if link is not None else None,
        "fold_index": link.fold_index if link is not None else None,
        "seed": link.seed if link is not None else None,
        "status": run.status,
        "progress_percent": progress.get("percent", 0),
        "generation": progress.get("generation"),
        "total_generations": progress.get("total_generations"),
        "r2_train": train.get("r2"),
        "r2_test": test.get("r2"),
        "rmse_train": train.get("rmse"),
        "rmse_test": test.get("rmse"),
        "mae_train": train.get("mae"),
        "mae_test": test.get("mae"),
        "accuracy_train": train.get("accuracy"),
        "accuracy_test": test.get("accuracy"),
        "f1_macro_train": train.get("f1_macro"),
        "f1_macro_test": test.get("f1_macro"),
        "model_size": metrics.get("model_size"),
        "training_time": metrics.get("training_time"),
        "process_time": metrics.get("process_time"),
        "created_at": run.created_at,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
    }


def benchmark_series(db: Session, group: ExperimentGroup) -> list[dict]:
    rows = group_runs(db, group.id)
    result: list[dict] = []
    for dataset_link in group_dataset_links(db, group.id):
        dataset = db.get(Dataset, dataset_link.dataset_id)
        dataset_rows = [
            (link, run)
            for link, run in rows
            if run.dataset_id == dataset_link.dataset_id
            and run.status == ExperimentStatus.completed.value
            and isinstance(run.metrics, dict)
        ]
        values = {
            "r2": [],
            "rmse": [],
            "model_size": [],
            "training_time": [],
        }
        run_values: list[dict] = []
        for link, run in dataset_rows:
            metrics = run.metrics or {}
            test = metrics.get("test", {}) if isinstance(metrics.get("test"), dict) else {}
            item = {
                "run_id": run.id,
                "repeat_index": link.repeat_index,
                "fold_index": link.fold_index,
                "r2": test.get("r2"),
                "rmse": test.get("rmse"),
                "model_size": metrics.get("model_size"),
                "training_time": metrics.get("training_time"),
            }
            for key in values:
                value = item.get(key)
                if isinstance(value, (int, float)) and math.isfinite(float(value)):
                    values[key].append(float(value))
            run_values.append(item)
        result.append(
            {
                "dataset_id": dataset_link.dataset_id,
                "dataset_name": dataset.name if dataset else dataset_link.dataset_id,
                "target_column": dataset_link.target_column,
                "values": values,
                "runs": run_values,
            }
        )
    return result


def aggregate_metrics(
    db: Session,
    group: ExperimentGroup,
    include_run_details: bool = True,
) -> dict:
    rows = group_runs(db, group.id)
    completed = [
        run
        for _, run in rows
        if run.status == ExperimentStatus.completed.value
        and isinstance(run.metrics, dict)
    ]
    by_dataset: dict[str, dict] = {}
    for dataset_link in group_dataset_links(db, group.id):
        dataset = db.get(Dataset, dataset_link.dataset_id)
        dataset_pairs = [
            (link, run)
            for link, run in rows
            if run.dataset_id == dataset_link.dataset_id
        ]
        dataset_runs = [run for _, run in dataset_pairs]
        completed_dataset = [
            run
            for run in dataset_runs
            if run.status == ExperimentStatus.completed.value
            and isinstance(run.metrics, dict)
        ]
        dataset_name = dataset.name if dataset else dataset_link.dataset_id
        by_dataset[dataset_link.dataset_id] = {
            "dataset_id": dataset_link.dataset_id,
            "dataset_name": dataset_name,
            "target_column": dataset_link.target_column,
            "total_runs": len(dataset_runs),
            "completed_runs": len(completed_dataset),
            "metrics": summarize_runs(completed_dataset, group.task_type),
            "runs": (
                [run_result_row(run, link, dataset_name) for link, run in dataset_pairs]
                if include_run_details
                else []
            ),
        }
    return {
        "experiment_id": group.id,
        "task_type": group.task_type,
        "total_runs": len(rows),
        "completed_runs": len(completed),
        "status_counts": status_counts(rows),
        "overall": summarize_runs(completed, group.task_type),
        "by_dataset": list(by_dataset.values()),
        "benchmark": benchmark_series(db, group) if include_run_details else [],
    }


def scatter_points(db: Session, group: ExperimentGroup, max_points: int = 1200) -> tuple[list[dict], float | None]:
    if group.task_type != "regression":
        return [], None
    settings = get_settings()
    points: list[dict] = []
    for _, run in group_runs(db, group.id):
        if run.status != ExperimentStatus.completed.value:
            continue
        artifact_dir = (
            Path(run.artifact_dir).expanduser()
            if run.artifact_dir
            else settings.artifact_dir / run.owner_id / run.id
        )
        path = artifact_dir / "test_results.json"
        if not path.is_file():
            continue
        try:
            import json

            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        dataset = db.get(Dataset, run.dataset_id)
        for actual, prediction in zip(
            payload.get("actual", []), payload.get("prediction", [])
        ):
            try:
                actual_value = float(actual)
                prediction_value = float(prediction)
            except (TypeError, ValueError):
                continue
            if not (math.isfinite(actual_value) and math.isfinite(prediction_value)):
                continue
            points.append(
                {
                    "actual": actual_value,
                    "prediction": prediction_value,
                    "run_id": run.id,
                    "dataset_id": run.dataset_id,
                    "dataset_name": dataset.name if dataset else run.dataset_id,
                }
            )
    # Compute correlation using all valid observations.  Sampling is applied
    # only to the SVG payload so large experiments do not distort the
    # reported Pearson coefficient.
    correlation = None
    if len(points) >= 2:
        xs = [item["actual"] for item in points]
        ys = [item["prediction"] for item in points]
        mx = sum(xs) / len(xs)
        my = sum(ys) / len(ys)
        numerator = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        denominator_x = sum((x - mx) ** 2 for x in xs)
        denominator_y = sum((y - my) ** 2 for y in ys)
        denominator = math.sqrt(denominator_x * denominator_y)
        correlation = numerator / denominator if denominator > 0 else None

    if len(points) > max_points:
        step = len(points) / max_points
        points = [points[min(int(i * step), len(points) - 1)] for i in range(max_points)]
    return points, correlation


def serialize_group(db: Session, group: ExperimentGroup, include_runs: bool = True) -> dict:
    dataset_items = []
    for link in group_dataset_links(db, group.id):
        dataset = db.get(Dataset, link.dataset_id)
        if dataset is None:
            continue
        dataset_items.append(
            {
                "dataset_id": dataset.id,
                "dataset_name": dataset.name,
                "original_name": dataset.original_name,
                "target_column": link.target_column,
            }
        )
    rows = group_runs(db, group.id)
    payload = {
        "id": group.id,
        "name": group.name,
        "task_type": group.task_type,
        "parameters": group.parameters or {},
        "validation": validation_dict(group.validation),
        "runs_per_dataset": group.runs_per_dataset,
        "preset_name": group.preset_name,
        "status": resolved_group_status(group, rows),
        "created_at": group.created_at,
        "datasets": dataset_items,
        "summary": aggregate_metrics(db, group, include_run_details=include_runs),
    }
    if include_runs:
        payload["runs"] = [
            {
                "id": run.id,
                "name": run.name,
                "dataset_id": run.dataset_id,
                "status": run.status,
                "repeat_index": link.repeat_index,
                "fold_index": link.fold_index,
                "seed": link.seed,
                "metrics": run.metrics,
                "progress": run.progress,
                "created_at": run.created_at,
                "started_at": run.started_at,
                "finished_at": run.finished_at,
            }
            for link, run in rows
        ]
    return payload


def delete_group(db: Session, group: ExperimentGroup) -> None:
    rows = group_runs(db, group.id)
    if any(run.status in ACTIVE_STATUSES for _, run in rows):
        raise ValueError("No se puede eliminar un experimento con corridas activas")
    for link, run in rows:
        cleanup_outputs(run)
        db.execute(delete(GPULease).where(GPULease.experiment_id == run.id))
        db.delete(link)
        db.delete(run)
    for link in group_dataset_links(db, group.id):
        db.delete(link)
    # SQLite deployments may not enforce ON DELETE CASCADE, so remove batch
    # associations explicitly before deleting the group.
    db.execute(
        delete(BatchExperimentLink).where(
            BatchExperimentLink.group_id == group.id
        )
    )
    db.delete(group)
    db.commit()


def serialize_batch(db: Session, batch: Batch) -> dict:
    groups: list[dict] = []
    links = db.scalars(
        select(BatchExperimentLink)
        .where(BatchExperimentLink.batch_id == batch.id)
        .order_by(BatchExperimentLink.position)
    )
    for link in links:
        group = db.get(ExperimentGroup, link.group_id)
        if group is not None:
            groups.append(serialize_group(db, group, include_runs=False))
    statuses = [item["status"] for item in groups]
    if groups and all(status == "completed" for status in statuses):
        status = "completed"
    elif any(status in {"queued", "running"} for status in statuses):
        status = "running"
    elif groups and all(status == "failed" for status in statuses):
        status = "failed"
    else:
        status = batch.status
    return {
        "id": batch.id,
        "name": batch.name,
        "status": status,
        "created_at": batch.created_at,
        "experiments": groups,
    }
