from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from m5gp.runtime import list_cuda_devices

from ..config import get_settings
from ..models import Experiment, ExperimentStatus, GPULease


def _process_is_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def cleanup_stale(db: Session) -> None:
    limit = datetime.now(timezone.utc) - timedelta(
        seconds=get_settings().lease_ttl_seconds
    )
    stale: list[GPULease] = []
    for lease in db.scalars(select(GPULease)):
        # A dead worker releases its GPU immediately; no algorithm callback is
        # required. A live worker is the authoritative indication that the
        # original M5GP process still owns the device.
        if lease.worker_pid:
            if _process_is_alive(lease.worker_pid):
                lease.heartbeat_at = datetime.now(timezone.utc)
                continue
            stale.append(lease)
            continue

        heartbeat = lease.heartbeat_at
        if heartbeat.tzinfo is None:
            heartbeat = heartbeat.replace(tzinfo=timezone.utc)
        if heartbeat < limit:
            stale.append(lease)

    for lease in stale:
        experiment = db.get(Experiment, lease.experiment_id)
        if experiment and experiment.status in (
            ExperimentStatus.reserved.value,
            ExperimentStatus.running.value,
        ):
            experiment.status = ExperimentStatus.failed.value
            experiment.error = "La reserva GPU expiró"
            experiment.finished_at = datetime.now(timezone.utc)
        db.delete(lease)
    if stale:
        db.commit()
    else:
        db.flush()


def reserve(db: Session, experiment_id: str, user_id: str):
    cleanup_stale(db)
    for device in list_cuda_devices():
        try:
            lease = GPULease(
                device_id=device.id,
                experiment_id=experiment_id,
                user_id=user_id,
            )
            db.add(lease)
            db.commit()
            db.refresh(lease)
            return device, lease
        except IntegrityError:
            db.rollback()
    return None, None


def release(db: Session, experiment_id: str) -> None:
    db.execute(
        delete(GPULease).where(GPULease.experiment_id == experiment_id)
    )
    db.commit()


def status(db: Session) -> list[dict]:
    cleanup_stale(db)
    leases = {
        lease.device_id: lease
        for lease in db.scalars(select(GPULease))
    }
    result: list[dict] = []
    for device in list_cuda_devices():
        lease = leases.get(device.id)
        result.append(
            {
                "id": device.id,
                "name": device.name,
                "memory_total_mb": device.memory_total_mb,
                "busy": lease is not None,
                "experiment_id": lease.experiment_id if lease else None,
                "user_id": lease.user_id if lease else None,
                "acquired_at": lease.acquired_at if lease else None,
            }
        )
    return result
