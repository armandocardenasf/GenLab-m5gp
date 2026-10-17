from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..lab_models import ParameterPreset
from ..lab_schemas import ParameterPresetCreate, ParameterPresetUpdate
from ..models import User
from ..security import current_user
from ..services.lab import effective_preset_list

router = APIRouter(prefix="/parameter-presets", tags=["parameter-presets"])


def owned_preset(preset_id: str, user: User, db: Session) -> ParameterPreset:
    preset = db.get(ParameterPreset, preset_id)
    if preset is None or preset.owner_id != user.id:
        raise HTTPException(404, "Predefinido no encontrado")
    return preset


def clear_default(db: Session, owner_id: str) -> None:
    for item in db.scalars(
        select(ParameterPreset).where(ParameterPreset.owner_id == owner_id)
    ):
        item.is_default = False


@router.get("")
def list_all(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return effective_preset_list(db, user.id)


@router.post("", status_code=201)
def create(
    data: ParameterPresetCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if data.is_default:
        clear_default(db, user.id)
    preset = ParameterPreset(
        owner_id=user.id,
        name=data.name.strip(),
        description=data.description.strip(),
        task_type=data.task_type,
        parameters=dict(data.parameters or {}),
        is_default=data.is_default,
    )
    db.add(preset)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Ya existe un predefinido con ese nombre") from exc
    db.refresh(preset)
    return {
        "id": preset.id,
        "name": preset.name,
        "description": preset.description,
        "task_type": preset.task_type,
        "parameters": preset.parameters,
        "is_default": preset.is_default,
        "system": False,
    }


@router.put("/{preset_id}")
def update(
    preset_id: str,
    data: ParameterPresetUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    preset = owned_preset(preset_id, user, db)
    values = data.model_dump(exclude_unset=True)
    if values.get("is_default") is True:
        clear_default(db, user.id)
    for key, value in values.items():
        if key in {"name", "description"} and value is not None:
            value = value.strip()
        setattr(preset, key, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Ya existe un predefinido con ese nombre") from exc
    db.refresh(preset)
    return {
        "id": preset.id,
        "name": preset.name,
        "description": preset.description,
        "task_type": preset.task_type,
        "parameters": preset.parameters,
        "is_default": preset.is_default,
        "system": False,
    }


@router.delete("/{preset_id}", status_code=204)
def remove(
    preset_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    preset = owned_preset(preset_id, user, db)
    db.delete(preset)
    db.commit()
    return Response(status_code=204)
