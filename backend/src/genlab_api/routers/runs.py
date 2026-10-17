from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..lab_models import ExperimentRunLink
from ..models import Experiment, User
from ..schemas import ExperimentOut
from ..security import current_user
from ..services.experiments import ACTIVE_STATUSES, cancel, cleanup_outputs
from ..services.gpu import release
from . import experiments as legacy

router = APIRouter(prefix="/runs", tags=["runs"])


def owned_run(
    run_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Experiment:
    run = db.get(Experiment, run_id)
    if run is None or run.owner_id != user.id:
        raise HTTPException(404, "Corrida no encontrada")
    return run


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


@router.get("/{run_id}", response_model=ExperimentOut)
def get_one(run: Experiment = Depends(owned_run)):
    return run


@router.get("/{run_id}/context")
def context(
    run: Experiment = Depends(owned_run),
    db: Session = Depends(get_db),
):
    link = db.scalar(
        select(ExperimentRunLink).where(ExperimentRunLink.run_id == run.id)
    )
    return {
        "run_id": run.id,
        "experiment_id": link.group_id if link else None,
        "repeat_index": link.repeat_index if link else None,
        "fold_index": link.fold_index if link else None,
        "seed": link.seed if link else None,
    }


@router.post("/{run_id}/run", response_model=ExperimentOut, status_code=202)
def run_now(
    run: Experiment = Depends(owned_run),
    db: Session = Depends(get_db),
):
    return legacy._start_experiment(run, db)


@router.post("/{run_id}/rerun", response_model=ExperimentOut, status_code=202)
def rerun(
    run: Experiment = Depends(owned_run),
    db: Session = Depends(get_db),
):
    return legacy._start_experiment(run, db)


@router.post("/{run_id}/cancel", response_model=ExperimentOut)
def stop(
    run: Experiment = Depends(owned_run),
    db: Session = Depends(get_db),
):
    if run.status not in ACTIVE_STATUSES:
        raise HTTPException(409, "La corrida no está activa")
    cancel(db, run)
    db.refresh(run)
    return run


@router.delete("/{run_id}", status_code=204)
def remove(
    run: Experiment = Depends(owned_run),
    db: Session = Depends(get_db),
):
    if run.status in ACTIVE_STATUSES:
        raise HTTPException(409, "No se puede eliminar una corrida activa")
    cleanup_outputs(run)
    release(db, run.id)
    db.execute(delete(ExperimentRunLink).where(ExperimentRunLink.run_id == run.id))
    db.delete(run)
    db.commit()
    return Response(status_code=204)


@router.get("/{run_id}/generation-history")
def generation_history(run: Experiment = Depends(owned_run)):
    return legacy.generation_history(run)


@router.get("/{run_id}/test-results")
def test_results(
    max_points: int | None = Query(default=None, ge=2, le=10000),
    run: Experiment = Depends(owned_run),
):
    return legacy.test_results(max_points=max_points, experiment=run)


@router.get("/{run_id}/visualization")
def visualization(run: Experiment = Depends(owned_run)):
    return legacy.visualization(run)


@router.get("/{run_id}/artifacts/{filename}")
def artifact(filename: str, run: Experiment = Depends(owned_run)):
    return legacy.artifact(filename=filename, experiment=run)


@router.get("/{run_id}/log")
def log(run: Experiment = Depends(owned_run)):
    return legacy.log(run)
