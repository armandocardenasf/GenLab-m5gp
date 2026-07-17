from __future__ import annotations

import multiprocessing as mp
import os
import shutil
import signal
from pathlib import Path

from sqlalchemy.orm import Session

from ..models import Experiment, ExperimentStatus
from .gpu import release, reserve

ACTIVE_STATUSES = {
    ExperimentStatus.reserved.value,
    ExperimentStatus.running.value,
    ExperimentStatus.cancelling.value,
}


def cleanup_outputs(experiment: Experiment) -> None:
    """Remove artifacts from a previous execution of the same experiment."""
    if experiment.artifact_dir:
        artifact_dir = Path(experiment.artifact_dir)
        if artifact_dir.exists() and artifact_dir.is_dir():
            shutil.rmtree(artifact_dir, ignore_errors=True)
    if experiment.log_path:
        Path(experiment.log_path).unlink(missing_ok=True)


def reset_for_run(experiment: Experiment) -> None:
    """Reset runtime fields while preserving the original configuration."""
    cleanup_outputs(experiment)
    experiment.status = ExperimentStatus.created.value
    experiment.gpu_id = None
    experiment.worker_pid = None
    experiment.progress = {}
    experiment.metrics = None
    experiment.symbolic_model = None
    experiment.complexity = None
    experiment.artifact_dir = None
    experiment.log_path = None
    experiment.error = None
    experiment.cancel_requested = False
    experiment.started_at = None
    experiment.finished_at = None


def launch(db: Session, experiment: Experiment):
    device, lease = reserve(db, experiment.id, experiment.owner_id)
    if not device:
        return None

    reset_for_run(experiment)
    experiment.status = ExperimentStatus.reserved.value
    experiment.gpu_id = device.id
    experiment.progress = {
        "stage": "reserved",
        "percent": 1,
        "message": f"GPU {device.id} reservada",
    }
    db.commit()

    from ..worker import run_experiment

    try:
        process = mp.get_context("spawn").Process(
            target=run_experiment,
            args=(experiment.id, device.id),
            daemon=False,
        )
        process.start()
    except Exception:
        release(db, experiment.id)
        experiment.status = ExperimentStatus.failed.value
        experiment.error = "No fue posible iniciar el proceso del experimento"
        db.commit()
        raise

    experiment.worker_pid = process.pid
    lease.worker_pid = process.pid
    db.commit()
    return process.pid


def cancel(db: Session, experiment: Experiment):
    experiment.cancel_requested = True
    experiment.status = ExperimentStatus.cancelling.value
    db.commit()
    if experiment.worker_pid:
        try:
            os.kill(experiment.worker_pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    experiment.status = ExperimentStatus.cancelled.value
    experiment.progress = {
        **dict(experiment.progress or {}),
        "stage": "cancelled",
        "message": "Ejecución cancelada por el usuario",
    }
    release(db, experiment.id)
    db.commit()
