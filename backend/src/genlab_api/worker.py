from __future__ import annotations

import inspect
import json
import math
import os
import re
import threading
import time
import traceback
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

_FLOAT_PATTERN = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
_GENERATION_PATTERN = re.compile(
    rf"\bGeneration:\s*(\d+).*?Train Fit:\s*({_FLOAT_PATTERN})"
)
_INITIAL_FIT_PATTERN = re.compile(
    rf"\bInitial Index:.*?Initial Fit:\s*({_FLOAT_PATTERN})"
)


def now() -> datetime:
    return datetime.now(timezone.utc)


def _json_value(value):
    """Convert estimator values to strict JSON-compatible values."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_value(item) for item in value]
    if hasattr(value, "item"):
        try:
            return _json_value(value.item())
        except (TypeError, ValueError):
            pass
    return str(value)


def _effective_parameters(model) -> dict:
    """Return all effective estimator parameters using scikit-learn's API."""
    try:
        values = model.get_params(deep=False)
    except Exception:
        values = {}
    return _json_value(values)


def _int_or_default(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _float_or_default(value, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if math.isfinite(number) else float(default)


def _model_size(value):
    """Preserve a numeric model size when the original method returns one."""
    value = _json_value(value)
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            number = float(value)
            return int(number) if number.is_integer() else number
        except ValueError:
            return value
    return value


def build_experiment_json(
    *,
    dataset_name: str,
    algorithm: str,
    params: dict,
    random_state: int,
    process_time: float,
    wall_time: float,
    model_size,
    symbolic_model: str,
    task_type: str,
    train_metrics: dict,
    test_metrics: dict,
    target_noise: float = 0.0,
    feature_noise: float = 0.0,
) -> dict:
    """Build the downloadable result document used by SRBench-style runs."""
    document = {
        "dataset": dataset_name,
        "algorithm": algorithm,
        "params": _json_value(params),
        "random_state": int(random_state),
        "process_time": _json_value(float(process_time)),
        "time_time": _json_value(float(wall_time)),
        "target_noise": _json_value(float(target_noise)),
        "feature_noise": _json_value(float(feature_noise)),
        "model_size": _model_size(model_size),
        "symbolic_model": str(symbolic_model),
    }
    if task_type == "regression":
        document.update(
            {
                "mse_train": _json_value(train_metrics.get("mse")),
                "mae_train": _json_value(train_metrics.get("mae")),
                "r2_train": _json_value(train_metrics.get("r2")),
                "mse_test": _json_value(test_metrics.get("mse")),
                "mae_test": _json_value(test_metrics.get("mae")),
                "r2_test": _json_value(test_metrics.get("r2")),
            }
        )
    else:
        # Keep the regression fields present for a stable artifact schema and
        # add the metrics that are meaningful for classification.
        document.update(
            {
                "mse_train": None,
                "mae_train": None,
                "r2_train": None,
                "mse_test": None,
                "mae_test": None,
                "r2_test": None,
                "accuracy_train": _json_value(
                    train_metrics.get("accuracy")
                ),
                "f1_macro_train": _json_value(
                    train_metrics.get("f1_macro")
                ),
                "accuracy_test": _json_value(
                    test_metrics.get("accuracy")
                ),
                "f1_macro_test": _json_value(
                    test_metrics.get("f1_macro")
                ),
                "precision_macro_train": _json_value(
                    train_metrics.get("precision_macro")
                ),
                "recall_macro_train": _json_value(
                    train_metrics.get("recall_macro")
                ),
                "precision_macro_test": _json_value(
                    test_metrics.get("precision_macro")
                ),
                "recall_macro_test": _json_value(
                    test_metrics.get("recall_macro")
                ),
            }
        )
    return document


def _constructor_parameters(cls: type, values: dict) -> dict:
    """Keep only parameters declared by the original estimator constructor."""
    signature = inspect.signature(cls.__init__)
    accepted = {
        name
        for name, parameter in signature.parameters.items()
        if name != "self"
        and parameter.kind
        not in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        )
    }
    return {name: value for name, value in values.items() if name in accepted}


def generation_percent(generation: int, total_generations: int) -> int:
    """Map the original M5GP generation cycle to the training progress range."""
    total = max(int(total_generations), 1)
    current = min(max(int(generation), 0), total)
    return min(90, 8 + round(82 * current / total))


def _persist_progress(experiment_id: str, progress: dict) -> None:
    from .db import SessionLocal
    from .models import Experiment

    progress_db = SessionLocal()
    try:
        experiment = progress_db.get(Experiment, experiment_id)
        if experiment is not None:
            experiment.progress = progress
            progress_db.commit()
    except Exception:
        progress_db.rollback()
    finally:
        progress_db.close()


def _monitor_generation_progress(
    experiment_id: str,
    log_path: Path,
    total_generations: int,
    stop_event: threading.Event,
) -> None:
    """Read generation and fitness messages printed by the original engine."""
    position = 0
    last_generation = -1
    history: list[dict] = []

    def publish(generation: int, fit: float) -> None:
        nonlocal last_generation
        if generation <= last_generation:
            return
        last_generation = generation
        history.append({"generation": generation, "fit": float(fit)})
        _persist_progress(
            experiment_id,
            {
                "stage": "training",
                "percent": generation_percent(
                    generation, total_generations
                ),
                "generation": generation,
                "total_generations": total_generations,
                "history": list(history),
                "message": (
                    f"Generación {generation} de "
                    f"{total_generations} completada"
                    if generation > 0
                    else "Evaluación inicial completada"
                ),
            },
        )

    def scan() -> None:
        nonlocal position
        if not log_path.is_file():
            return
        with log_path.open("r", encoding="utf-8", errors="replace") as stream:
            stream.seek(position)
            for line in stream:
                initial_match = _INITIAL_FIT_PATTERN.search(line)
                if initial_match and last_generation < 0:
                    publish(0, float(initial_match.group(1)))
                    continue
                match = _GENERATION_PATTERN.search(line)
                if match:
                    publish(int(match.group(1)), float(match.group(2)))
            position = stream.tell()

    while not stop_event.wait(0.5):
        scan()
    scan()


def run_experiment(experiment_id: str, physical_gpu_id: int) -> None:
    # The original engine always calls cudaSetup(0). Restricting visibility
    # makes the reserved physical GPU appear as logical device 0.
    os.environ["CUDA_VISIBLE_DEVICES"] = str(physical_gpu_id)
    os.environ.setdefault("CUDA_DEVICE_ORDER", "PCI_BUS_ID")

    from .config import get_settings
    from .db import SessionLocal
    from .models import Dataset, Experiment, ExperimentStatus
    from .services.gpu import release

    db = SessionLocal()
    settings = get_settings()
    experiment = db.get(Experiment, experiment_id)
    if experiment is None:
        db.close()
        return

    artifact_dir = (
        settings.artifact_dir / experiment.owner_id / experiment.id
    ).resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    log_path = (settings.log_dir / f"{experiment.id}.log").resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    experiment.log_path = str(log_path)
    experiment.artifact_dir = str(artifact_dir)
    experiment.status = ExperimentStatus.running.value
    experiment.started_at = now()
    experiment.progress = {
        "stage": "loading_data",
        "percent": 3,
        "message": "Cargando dataset",
    }
    db.commit()

    dataset = db.get(Dataset, experiment.dataset_id)
    if dataset is None:
        experiment.status = ExperimentStatus.failed.value
        experiment.error = "Dataset not found"
        experiment.progress = {
            "stage": "failed",
            "percent": 3,
            "message": "Dataset no encontrado",
        }
        experiment.finished_at = now()
        db.commit()
        release(db, experiment_id)
        db.close()
        return

    from .services.files import resolve_dataset_path

    dataset_path = resolve_dataset_path(
        dataset.path,
        user_id=dataset.owner_id,
    )
    if not dataset_path.is_file():
        experiment.status = ExperimentStatus.failed.value
        experiment.error = f"Dataset file not found: {dataset_path}"
        experiment.progress = {
            "stage": "failed",
            "percent": 3,
            "message": "Archivo del dataset no encontrado",
        }
        experiment.finished_at = now()
        db.commit()
        release(db, experiment_id)
        db.close()
        return

    if dataset.path != str(dataset_path):
        dataset.path = str(dataset_path)
        db.commit()

    previous_directory = os.getcwd()
    try:
        os.chdir(artifact_dir)
        with log_path.open(
            "w", encoding="utf-8", buffering=1
        ) as log_file, redirect_stdout(log_file), redirect_stderr(log_file):
            import joblib
            import numpy as np
            import pandas as pd
            from sklearn.metrics import (
                accuracy_score,
                classification_report,
                confusion_matrix,
                f1_score,
                mean_absolute_error,
                mean_squared_error,
                precision_score,
                r2_score,
                recall_score,
            )
            from sklearn.model_selection import train_test_split

            from m5gp import m5gpClassifier, m5gpRegressor

            from .services.files import read_dataset

            frame = read_dataset(dataset_path)
            if experiment.target_column not in frame.columns:
                raise ValueError("La columna objetivo no existe")

            x_frame = frame.drop(columns=[experiment.target_column])
            if not all(
                np.issubdtype(dtype, np.number) for dtype in x_frame.dtypes
            ):
                raise ValueError(
                    "Todas las variables predictoras deben ser numéricas"
                )

            X = x_frame.to_numpy().astype(np.float32)
            y = frame[experiment.target_column].to_numpy().astype(np.float32)
            stratify = (
                y if experiment.task_type == "classification" else None
            )
            X_train, X_test, y_train, y_test = train_test_split(
                X,
                y,
                test_size=settings.test_size,
                random_state=settings.random_state,
                stratify=stratify,
            )

            experiment.progress = {
                "stage": "preparing",
                "percent": 5,
                "message": "Preparando datos y estimador M5GP",
            }
            db.commit()

            estimator_class = (
                m5gpRegressor
                if experiment.task_type == "regression"
                else m5gpClassifier
            )
            parameters = _constructor_parameters(
                estimator_class, dict(experiment.parameters or {})
            )
            parameters.setdefault(
                "logPath", str(artifact_dir / "log") + os.sep
            )

            model = estimator_class(**parameters)
            total_generations = max(
                int(getattr(model, "generations", 1) or 1), 1
            )
            experiment.progress = {
                "stage": "training",
                "percent": 8,
                "generation": 0,
                "total_generations": total_generations,
                "message": "Inicializando la población y evaluación inicial",
            }
            db.commit()

            stop_monitor = threading.Event()
            monitor = threading.Thread(
                target=_monitor_generation_progress,
                args=(
                    experiment.id,
                    log_path,
                    total_generations,
                    stop_monitor,
                ),
                daemon=True,
            )
            monitor.start()
            process_started = time.process_time()
            wall_started = time.time()
            try:
                model.fit(X_train, y_train)
            finally:
                stop_monitor.set()
                monitor.join(timeout=2)
            process_elapsed = time.process_time() - process_started
            wall_elapsed = time.time() - wall_started

            db.refresh(experiment)
            last_generation = int(
                (experiment.progress or {}).get("generation", 0)
            )
            generation_history = list(
                (experiment.progress or {}).get("history", [])
            )
            experiment.progress = {
                "stage": "evaluating",
                "percent": 92,
                "generation": last_generation,
                "total_generations": total_generations,
                "history": generation_history,
                "message": "Evaluando el mejor modelo con los datos de prueba",
            }
            db.commit()

            train_prediction = np.asarray(model.predict(X_train)).reshape(-1)
            prediction = np.asarray(model.predict(X_test)).reshape(-1)
            classification_details = None
            if experiment.task_type == "regression":
                train_metrics = {
                    "mse": float(mean_squared_error(y_train, train_prediction)),
                    "rmse": float(
                        mean_squared_error(y_train, train_prediction) ** 0.5
                    ),
                    "mae": float(mean_absolute_error(y_train, train_prediction)),
                    "r2": float(r2_score(y_train, train_prediction)),
                }
                test_metrics = {
                    "mse": float(mean_squared_error(y_test, prediction)),
                    "rmse": float(
                        mean_squared_error(y_test, prediction) ** 0.5
                    ),
                    "mae": float(mean_absolute_error(y_test, prediction)),
                    "r2": float(r2_score(y_test, prediction)),
                }
                metrics = {
                    "rmse": test_metrics["rmse"],
                    "r2": test_metrics["r2"],
                    "train": train_metrics,
                    "test": test_metrics,
                }
            else:
                train_metrics = {
                    "accuracy": float(
                        accuracy_score(y_train, train_prediction)
                    ),
                    "f1_macro": float(
                        f1_score(
                            y_train,
                            train_prediction,
                            average="macro",
                            zero_division=0,
                        )
                    ),
                    "precision_macro": float(
                        precision_score(
                            y_train,
                            train_prediction,
                            average="macro",
                            zero_division=0,
                        )
                    ),
                    "recall_macro": float(
                        recall_score(
                            y_train,
                            train_prediction,
                            average="macro",
                            zero_division=0,
                        )
                    ),
                }
                test_metrics = {
                    "accuracy": float(accuracy_score(y_test, prediction)),
                    "f1_macro": float(
                        f1_score(
                            y_test,
                            prediction,
                            average="macro",
                            zero_division=0,
                        )
                    ),
                    "precision_macro": float(
                        precision_score(
                            y_test,
                            prediction,
                            average="macro",
                            zero_division=0,
                        )
                    ),
                    "recall_macro": float(
                        recall_score(
                            y_test,
                            prediction,
                            average="macro",
                            zero_division=0,
                        )
                    ),
                }
                classes = np.unique(np.concatenate([y_test, prediction]))
                matrix = confusion_matrix(
                    y_test, prediction, labels=classes
                ).tolist()
                report = classification_report(
                    y_test,
                    prediction,
                    labels=classes,
                    output_dict=True,
                    zero_division=0,
                )
                classification_details = {
                    "classes": _json_value(classes.tolist()),
                    "confusion_matrix": _json_value(matrix),
                    "classification_report": _json_value(report),
                }
                metrics = {
                    "accuracy": test_metrics["accuracy"],
                    "f1_macro": test_metrics["f1_macro"],
                    "train": train_metrics,
                    "test": test_metrics,
                    **classification_details,
                }

            experiment.progress = {
                "stage": "saving",
                "percent": 97,
                "generation": last_generation,
                "total_generations": total_generations,
                "history": generation_history,
                "message": "Guardando modelo, métricas y predicciones",
            }
            db.commit()

            symbolic_model = model.get_model()
            model_complexity = model.complexity()
            joblib.dump(model, artifact_dir / "model.joblib")
            prediction_frame = pd.DataFrame(
                {
                    "sample": np.arange(len(y_test), dtype=int),
                    "actual": y_test,
                    "prediction": prediction,
                }
            )
            prediction_frame.to_csv(
                artifact_dir / "predictions.csv", index=False
            )
            (artifact_dir / "model.txt").write_text(
                str(symbolic_model), encoding="utf-8"
            )
            (artifact_dir / "metrics.json").write_text(
                json.dumps(
                    _json_value(metrics),
                    indent=2,
                    ensure_ascii=False,
                    allow_nan=False,
                ),
                encoding="utf-8",
            )
            (artifact_dir / "generation_history.json").write_text(
                json.dumps(
                    {
                        "task_type": experiment.task_type,
                        "fit_label": "Train Fit",
                        "history": _json_value(generation_history),
                    },
                    indent=2,
                    ensure_ascii=False,
                    allow_nan=False,
                ),
                encoding="utf-8",
            )
            (artifact_dir / "test_results.json").write_text(
                json.dumps(
                    {
                        "task_type": experiment.task_type,
                        "sample": _json_value(
                            prediction_frame["sample"].tolist()
                        ),
                        "actual": _json_value(
                            prediction_frame["actual"].tolist()
                        ),
                        "prediction": _json_value(
                            prediction_frame["prediction"].tolist()
                        ),
                    },
                    indent=2,
                    ensure_ascii=False,
                    allow_nan=False,
                ),
                encoding="utf-8",
            )
            if classification_details is not None:
                (artifact_dir / "confusion_matrix.json").write_text(
                    json.dumps(
                        {
                            "classes": classification_details["classes"],
                            "matrix": classification_details[
                                "confusion_matrix"
                            ],
                        },
                        indent=2,
                        ensure_ascii=False,
                        allow_nan=False,
                    ),
                    encoding="utf-8",
                )
                (artifact_dir / "classification_report.json").write_text(
                    json.dumps(
                        classification_details["classification_report"],
                        indent=2,
                        ensure_ascii=False,
                        allow_nan=False,
                    ),
                    encoding="utf-8",
                )
            result_document = build_experiment_json(
                dataset_name=Path(dataset.original_name).stem,
                algorithm=estimator_class.__name__,
                params=_effective_parameters(model),
                random_state=_int_or_default(
                    (experiment.parameters or {}).get("random_state"),
                    settings.random_state,
                ),
                process_time=process_elapsed,
                wall_time=wall_elapsed,
                target_noise=_float_or_default(
                    (experiment.parameters or {}).get("target_noise"), 0.0
                ),
                feature_noise=_float_or_default(
                    (experiment.parameters or {}).get("feature_noise"), 0.0
                ),
                model_size=model_complexity,
                symbolic_model=str(symbolic_model),
                task_type=experiment.task_type,
                train_metrics=train_metrics,
                test_metrics=test_metrics,
            )
            (artifact_dir / "experiment.json").write_text(
                json.dumps(
                    result_document,
                    indent=4,
                    ensure_ascii=False,
                    allow_nan=False,
                ),
                encoding="utf-8",
            )

            experiment.metrics = metrics
            experiment.symbolic_model = str(symbolic_model)
            experiment.complexity = str(model_complexity)
            experiment.status = ExperimentStatus.completed.value
            experiment.progress = {
                "stage": "completed",
                "percent": 100,
                "generation": last_generation,
                "total_generations": total_generations,
                "history": generation_history,
                "message": "Experimento finalizado correctamente",
            }
            experiment.finished_at = now()
            db.commit()
    except Exception:
        current_percent = int((experiment.progress or {}).get("percent", 0))
        experiment.status = ExperimentStatus.failed.value
        experiment.error = traceback.format_exc()
        experiment.progress = {
            **dict(experiment.progress or {}),
            "stage": "failed",
            "percent": current_percent,
            "message": "El experimento terminó con error",
        }
        experiment.finished_at = now()
        db.commit()
    finally:
        os.chdir(previous_directory)
        try:
            release(db, experiment_id)
        finally:
            db.close()
