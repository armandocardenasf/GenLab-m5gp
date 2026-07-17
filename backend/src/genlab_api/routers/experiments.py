import json
import re
from pathlib import Path

import pandas as pd

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..deps import owned_experiment
from ..models import Dataset, Experiment, ExperimentStatus, User
from ..schemas import ExperimentCreate, ExperimentOut
from ..security import current_user
from ..services.experiments import (
    ACTIVE_STATUSES,
    cancel,
    cleanup_outputs,
    launch,
)
from ..services.gpu import release

router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.post("", response_model=ExperimentOut, status_code=201)
def create(
    data: ExperimentCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    dataset = db.get(Dataset, data.dataset_id)
    if not dataset or dataset.owner_id != user.id:
        raise HTTPException(404, "Dataset no encontrado")
    if data.target_column not in dataset.column_names:
        raise HTTPException(422, "Columna objetivo inválida")
    experiment = Experiment(owner_id=user.id, **data.model_dump())
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    return experiment


@router.get("", response_model=list[ExperimentOut])
def list_all(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return list(
        db.scalars(
            select(Experiment)
            .where(Experiment.owner_id == user.id)
            .order_by(Experiment.created_at.desc())
        )
    )


@router.get("/{experiment_id}", response_model=ExperimentOut)
def get_one(experiment: Experiment = Depends(owned_experiment)):
    return experiment


def _start_experiment(experiment: Experiment, db: Session) -> Experiment:
    if experiment.status in ACTIVE_STATUSES:
        raise HTTPException(409, "El experimento ya está activo")
    if launch(db, experiment) is None:
        raise HTTPException(
            409,
            "Todas las GPUs están ocupadas o no existe una GPU CUDA disponible",
        )
    db.refresh(experiment)
    return experiment


@router.post("/{experiment_id}/run", response_model=ExperimentOut, status_code=202)
def run(
    experiment: Experiment = Depends(owned_experiment),
    db: Session = Depends(get_db),
):
    return _start_experiment(experiment, db)


@router.post(
    "/{experiment_id}/rerun",
    response_model=ExperimentOut,
    status_code=202,
)
def rerun(
    experiment: Experiment = Depends(owned_experiment),
    db: Session = Depends(get_db),
):
    """Execute again using the stored dataset, target and parameters."""
    return _start_experiment(experiment, db)


@router.post("/{experiment_id}/cancel", response_model=ExperimentOut)
def stop(
    experiment: Experiment = Depends(owned_experiment),
    db: Session = Depends(get_db),
):
    if experiment.status not in ACTIVE_STATUSES:
        raise HTTPException(409, "El experimento no está activo")
    cancel(db, experiment)
    db.refresh(experiment)
    return experiment


@router.delete("/{experiment_id}", status_code=204)
def remove(
    experiment: Experiment = Depends(owned_experiment),
    db: Session = Depends(get_db),
):
    if experiment.status in ACTIVE_STATUSES:
        raise HTTPException(
            409,
            "No se puede eliminar un experimento mientras está activo",
        )
    cleanup_outputs(experiment)
    release(db, experiment.id)
    db.delete(experiment)
    db.commit()
    return Response(status_code=204)


_GENERATION_ARTIFACT_PATTERN = re.compile(
    r"\bGeneration:\s*(\d+).*?Train Fit:\s*"
    r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)"
)


def _artifact_directory(experiment: Experiment) -> Path:
    """Resolve the experiment artifact directory, including legacy rows.

    Older experiments may have ``artifact_dir`` unset or stored as a relative
    path.  The worker has always used the deterministic directory
    ``<data>/artifacts/<owner>/<experiment>``; use it as the final fallback so
    derived JSON files can still be reconstructed and downloaded.
    """
    settings = get_settings()
    default_directory = (
        settings.artifact_dir / experiment.owner_id / experiment.id
    ).expanduser().resolve()

    candidates: list[Path] = []
    if experiment.artifact_dir:
        directory = Path(experiment.artifact_dir).expanduser()
        if directory.is_absolute():
            candidates.append(directory.resolve())
        else:
            candidates.extend(
                [
                    directory.resolve(),
                    (settings.data_dir.parent / directory).resolve(),
                ]
            )
    candidates.append(default_directory)

    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return default_directory


def _write_json_artifact(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    return path


def _generation_history_payload(experiment: Experiment) -> dict:
    history = []
    progress = experiment.progress if isinstance(experiment.progress, dict) else {}
    progress_history = progress.get("history", [])
    if isinstance(progress_history, list):
        for point in progress_history:
            if not isinstance(point, dict):
                continue
            try:
                history.append(
                    {
                        "generation": int(point["generation"]),
                        "fit": float(point["fit"]),
                    }
                )
            except (KeyError, TypeError, ValueError):
                continue

    if not history and experiment.log_path:
        log_path = Path(experiment.log_path).expanduser()
        if log_path.is_file():
            for match in _GENERATION_ARTIFACT_PATTERN.finditer(
                log_path.read_text(encoding="utf-8", errors="replace")
            ):
                history.append(
                    {
                        "generation": int(match.group(1)),
                        "fit": float(match.group(2)),
                    }
                )

    deduplicated = {point["generation"]: point for point in history}
    return {
        "task_type": experiment.task_type,
        "fit_label": "Train Fit",
        "history": [deduplicated[key] for key in sorted(deduplicated)],
    }


def _test_results_payload(experiment: Experiment, artifact_dir: Path) -> dict:
    predictions_path = artifact_dir / "predictions.csv"
    if not predictions_path.is_file():
        raise HTTPException(404, "Predicciones no disponibles")
    frame = pd.read_csv(predictions_path)
    required = {"actual", "prediction"}
    if not required.issubset(frame.columns):
        raise HTTPException(422, "El archivo de predicciones no tiene el formato esperado")
    sample = (
        frame["sample"].tolist()
        if "sample" in frame.columns
        else list(range(len(frame)))
    )
    return {
        "task_type": experiment.task_type,
        "sample": sample,
        "actual": frame["actual"].tolist(),
        "prediction": frame["prediction"].tolist(),
    }


def _ensure_derived_artifact(
    filename: str, experiment: Experiment, artifact_dir: Path
) -> Path:
    path = artifact_dir / filename
    if path.is_file():
        return path
    if filename == "generation_history.json":
        return _write_json_artifact(path, _generation_history_payload(experiment))
    if filename == "test_results.json":
        return _write_json_artifact(
            path, _test_results_payload(experiment, artifact_dir)
        )
    return path


@router.get("/{experiment_id}/artifacts/{filename}")
def artifact(
    filename: str,
    experiment: Experiment = Depends(owned_experiment),
):
    allowed = {
        "model.joblib",
        "predictions.csv",
        "metrics.json",
        "model.txt",
        "experiment.json",
        "generation_history.json",
        "test_results.json",
        "classification_report.json",
        "confusion_matrix.json",
    }
    if filename not in allowed:
        raise HTTPException(404, "Artefacto no disponible")
    artifact_dir = _artifact_directory(experiment)
    path = _ensure_derived_artifact(filename, experiment, artifact_dir)
    if not path.is_file():
        raise HTTPException(404, "Artefacto no disponible")
    media_type = "application/json" if path.suffix.lower() == ".json" else None
    return FileResponse(path, media_type=media_type, filename=filename)


def _sample_test_results(payload: dict, max_points: int = 300) -> dict:
    samples = list(payload.get("sample", []))
    actual = list(payload.get("actual", []))
    prediction = list(payload.get("prediction", []))
    count = min(len(samples), len(actual), len(prediction))
    if count <= max_points:
        indices = list(range(count))
    else:
        step = (count - 1) / (max_points - 1)
        indices = sorted({round(position * step) for position in range(max_points)})
    return {
        "task_type": payload.get("task_type"),
        "sample": [samples[index] for index in indices],
        "actual": [actual[index] for index in indices],
        "prediction": [prediction[index] for index in indices],
        "total_points": count,
        "displayed_points": len(indices),
    }


@router.get("/{experiment_id}/generation-history")
def generation_history(experiment: Experiment = Depends(owned_experiment)):
    """Return the complete generation history as JSON.

    The payload is rebuilt from the persisted progress or execution log when
    generation_history.json was not created by an older worker version.
    """
    if experiment.status != ExperimentStatus.completed.value:
        raise HTTPException(409, "El experimento todavía no ha finalizado")
    artifact_dir = _artifact_directory(experiment)
    path = _ensure_derived_artifact(
        "generation_history.json", experiment, artifact_dir
    )
    if not path.is_file():
        raise HTTPException(404, "Historial por generación no disponible")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/{experiment_id}/test-results")
def test_results(
    max_points: int | None = Query(default=None, ge=2, le=10000),
    experiment: Experiment = Depends(owned_experiment),
):
    """Return test actual/prediction values as JSON.

    ``max_points`` is intended for chart rendering. Omitting it returns the
    complete result set used by the downloadable JSON button.
    """
    if experiment.status != ExperimentStatus.completed.value:
        raise HTTPException(409, "El experimento todavía no ha finalizado")
    artifact_dir = _artifact_directory(experiment)
    path = _ensure_derived_artifact("test_results.json", experiment, artifact_dir)
    if not path.is_file():
        raise HTTPException(404, "Resultados de prueba no disponibles")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if max_points is None:
        count = min(
            len(payload.get("sample", [])),
            len(payload.get("actual", [])),
            len(payload.get("prediction", [])),
        )
        payload["total_points"] = count
        payload["displayed_points"] = count
        return payload
    return _sample_test_results(payload, max_points=max_points)


@router.get("/{experiment_id}/visualization")
def visualization(experiment: Experiment = Depends(owned_experiment)):
    if experiment.status != ExperimentStatus.completed.value:
        raise HTTPException(409, "El experimento todavía no ha finalizado")
    artifact_dir = _artifact_directory(experiment)
    history_path = _ensure_derived_artifact(
        "generation_history.json", experiment, artifact_dir
    )
    test_path = _ensure_derived_artifact(
        "test_results.json", experiment, artifact_dir
    )
    if not history_path.is_file() or not test_path.is_file():
        raise HTTPException(404, "Resultados de visualización no disponibles")
    history = json.loads(history_path.read_text(encoding="utf-8"))
    test_results = json.loads(test_path.read_text(encoding="utf-8"))
    response = {
        "task_type": experiment.task_type,
        "generation_history": history.get("history", []),
        "fit_label": history.get("fit_label", "Train Fit"),
        "test_results": _sample_test_results(test_results),
    }
    if experiment.task_type == "classification":
        matrix_path = artifact_dir / "confusion_matrix.json"
        if matrix_path.is_file():
            response["confusion_matrix"] = json.loads(
                matrix_path.read_text(encoding="utf-8")
            )
    return response


@router.get("/{experiment_id}/log")
def log(experiment: Experiment = Depends(owned_experiment)):
    if not experiment.log_path or not Path(experiment.log_path).is_file():
        raise HTTPException(404, "Log no disponible")
    return FileResponse(
        experiment.log_path,
        media_type="text/plain",
        filename=f"{experiment.id}.log",
    )
