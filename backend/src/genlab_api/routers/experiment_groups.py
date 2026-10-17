from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..lab_models import ExperimentDatasetLink, ExperimentGroup
from ..lab_schemas import ExperimentGroupCreate
from ..models import Dataset, User
from ..security import current_user
from ..services.exports import (
    experiment_export_payload,
    export_json_bytes,
    export_xlsx_bytes,
    safe_filename,
)
from ..services.lab import (
    aggregate_metrics,
    create_runs,
    delete_group,
    dispatch_queued,
    scatter_points,
    serialize_group,
)

router = APIRouter(prefix="/experiment-groups", tags=["experiment-groups"])


def owned_group(group_id: str, user: User, db: Session) -> ExperimentGroup:
    group = db.get(ExperimentGroup, group_id)
    if group is None or group.owner_id != user.id:
        raise HTTPException(404, "Experimento no encontrado")
    return group


@router.post("", status_code=201)
def create(
    data: ExperimentGroupCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    group = ExperimentGroup(
        owner_id=user.id,
        name=data.name.strip(),
        task_type=data.task_type,
        parameters=dict(data.parameters or {}),
        validation=data.validation.model_dump(),
        runs_per_dataset=data.runs_per_dataset,
        preset_name=data.preset_name,
    )
    db.add(group)
    db.flush()

    seen: set[str] = set()
    for position, binding in enumerate(data.datasets):
        if binding.dataset_id in seen:
            raise HTTPException(422, "Un dataset no puede repetirse en el mismo experimento")
        seen.add(binding.dataset_id)
        dataset = db.get(Dataset, binding.dataset_id)
        if dataset is None or dataset.owner_id != user.id:
            raise HTTPException(404, "Dataset no encontrado")
        if binding.target_column not in dataset.column_names:
            raise HTTPException(
                422,
                f"Variable objetivo inválida para el dataset {dataset.name}",
            )
        db.add(
            ExperimentDatasetLink(
                group_id=group.id,
                dataset_id=dataset.id,
                target_column=binding.target_column,
                position=position,
            )
        )
    db.commit()
    db.refresh(group)
    return serialize_group(db, group)


@router.get("")
def list_all(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    groups = db.scalars(
        select(ExperimentGroup)
        .where(ExperimentGroup.owner_id == user.id)
        .order_by(ExperimentGroup.created_at.desc())
    )
    return [serialize_group(db, group, include_runs=False) for group in groups]


@router.get("/{group_id}")
def get_one(
    group_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return serialize_group(db, owned_group(group_id, user, db))


@router.post("/{group_id}/run", status_code=202)
def run_group(
    group_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    group = owned_group(group_id, user, db)
    create_runs(db, group)
    dispatch_queued(db)
    db.refresh(group)
    return serialize_group(db, group)


@router.post("/{group_id}/dispatch", status_code=202)
def dispatch_group(
    group_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    group = owned_group(group_id, user, db)
    dispatch_queued(db)
    return serialize_group(db, group)


@router.get("/{group_id}/results")
def results(
    group_id: str,
    max_points: int = Query(default=1200, ge=20, le=10000),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    group = owned_group(group_id, user, db)
    payload = aggregate_metrics(db, group)
    points, correlation = scatter_points(db, group, max_points=max_points)
    payload["scatter"] = points
    payload["correlation"] = correlation
    return payload


@router.get("/{group_id}/export/json")
def export_json(
    group_id: str,
    dataset_id: str | None = Query(default=None),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    group = owned_group(group_id, user, db)
    try:
        payload = experiment_export_payload(db, group, dataset_id=dataset_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    suffix = f"_{dataset_id}" if dataset_id else ""
    filename = safe_filename(f"{group.name}{suffix}_resultados") + ".json"
    return Response(
        content=export_json_bytes(payload),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{group_id}/export/xlsx")
def export_xlsx(
    group_id: str,
    dataset_id: str | None = Query(default=None),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    group = owned_group(group_id, user, db)
    try:
        payload = experiment_export_payload(db, group, dataset_id=dataset_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    suffix = f"_{dataset_id}" if dataset_id else ""
    filename = safe_filename(f"{group.name}{suffix}_resultados") + ".xlsx"
    return Response(
        content=export_xlsx_bytes(payload),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/{group_id}", status_code=204)
def remove(
    group_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    group = owned_group(group_id, user, db)
    try:
        delete_group(db, group)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return Response(status_code=204)
