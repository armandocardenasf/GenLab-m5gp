from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..lab_models import Batch, BatchExperimentLink, ExperimentGroup
from ..lab_schemas import BatchCreate
from ..models import User
from ..security import current_user
from ..services.lab import create_runs, dispatch_queued, serialize_batch

router = APIRouter(prefix="/batches", tags=["batches"])


def owned_batch(batch_id: str, user: User, db: Session) -> Batch:
    batch = db.get(Batch, batch_id)
    if batch is None or batch.owner_id != user.id:
        raise HTTPException(404, "Lote no encontrado")
    return batch


@router.post("", status_code=201)
def create(
    data: BatchCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    batch = Batch(owner_id=user.id, name=data.name.strip())
    db.add(batch)
    db.flush()
    seen: set[str] = set()
    for position, group_id in enumerate(data.experiment_ids):
        if group_id in seen:
            continue
        seen.add(group_id)
        group = db.get(ExperimentGroup, group_id)
        if group is None or group.owner_id != user.id:
            raise HTTPException(404, "Experimento no encontrado")
        db.add(
            BatchExperimentLink(
                batch_id=batch.id,
                group_id=group.id,
                position=position,
            )
        )
    db.commit()
    db.refresh(batch)
    return serialize_batch(db, batch)


@router.get("")
def list_all(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    batches = db.scalars(
        select(Batch)
        .where(Batch.owner_id == user.id)
        .order_by(Batch.created_at.desc())
    )
    return [serialize_batch(db, batch) for batch in batches]


@router.get("/{batch_id}")
def get_one(
    batch_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return serialize_batch(db, owned_batch(batch_id, user, db))


@router.post("/{batch_id}/run", status_code=202)
def run_batch(
    batch_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    batch = owned_batch(batch_id, user, db)
    batch.status = "queued"
    links = db.scalars(
        select(BatchExperimentLink)
        .where(BatchExperimentLink.batch_id == batch.id)
        .order_by(BatchExperimentLink.position)
    )
    for link in links:
        group = db.get(ExperimentGroup, link.group_id)
        if group is not None:
            create_runs(db, group)
    db.commit()
    dispatch_queued(db)
    return serialize_batch(db, batch)
