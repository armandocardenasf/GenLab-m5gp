from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..lab_models import ComparisonReport, ExperimentGroup
from ..lab_schemas import ComparisonReportCreate, ComparisonRequest
from ..models import User
from ..security import current_user
from ..services.comparison_exports import comparison_json_bytes, comparison_xlsx_bytes
from ..services.comparisons import build_comparison_snapshot
from ..services.exports import safe_filename

router = APIRouter(prefix="/comparison-reports", tags=["comparison-reports"])


def _groups_for_request(
    db: Session,
    user: User,
    experiment_ids: list[str],
    task_type: str,
) -> list[ExperimentGroup]:
    groups: list[ExperimentGroup] = []
    for experiment_id in experiment_ids:
        group = db.get(ExperimentGroup, experiment_id)
        if group is None or group.owner_id != user.id:
            raise HTTPException(404, f"Experimento no encontrado: {experiment_id}")
        if group.task_type != task_type:
            raise HTTPException(422, "Todos los experimentos deben ser del mismo tipo")
        groups.append(group)
    return groups


def _owned_report(report_id: str, user: User, db: Session) -> ComparisonReport:
    report = db.get(ComparisonReport, report_id)
    if report is None or report.owner_id != user.id:
        raise HTTPException(404, "Reporte comparativo no encontrado")
    return report


def _serialize(report: ComparisonReport, include_snapshot: bool = True) -> dict:
    payload = {
        "id": report.id,
        "name": report.name,
        "description": report.description,
        "task_type": report.task_type,
        "experiment_ids": report.experiment_ids or [],
        "config": report.config or {},
        "created_at": report.created_at,
        "updated_at": report.updated_at,
    }
    if include_snapshot:
        payload["analysis"] = report.snapshot or {}
    else:
        snapshot = report.snapshot or {}
        payload["summary"] = {
            "primary_metric": snapshot.get("primary_metric"),
            "generated_at": snapshot.get("generated_at"),
            "experiment_count": len(snapshot.get("experiments") or []),
            "dataset_count": len(snapshot.get("datasets") or []),
        }
    return payload


@router.post("/preview")
def preview(
    data: ComparisonRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    groups = _groups_for_request(db, user, data.experiment_ids, data.task_type)
    try:
        return build_comparison_snapshot(
            db,
            groups,
            data.task_type,
            data.primary_metric or ("r2_test" if data.task_type == "regression" else "f1_macro_test"),
            data.alpha,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("", status_code=201)
def create(
    data: ComparisonReportCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    groups = _groups_for_request(db, user, data.experiment_ids, data.task_type)
    try:
        snapshot = build_comparison_snapshot(
            db,
            groups,
            data.task_type,
            data.primary_metric or ("r2_test" if data.task_type == "regression" else "f1_macro_test"),
            data.alpha,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    report = ComparisonReport(
        owner_id=user.id,
        name=data.name.strip(),
        description=data.description.strip(),
        task_type=data.task_type,
        experiment_ids=list(data.experiment_ids),
        config={
            "primary_metric": data.primary_metric,
            "alpha": data.alpha,
        },
        snapshot=snapshot,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return _serialize(report)


@router.get("")
def list_all(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    reports = db.scalars(
        select(ComparisonReport)
        .where(ComparisonReport.owner_id == user.id)
        .order_by(ComparisonReport.updated_at.desc(), ComparisonReport.created_at.desc())
    )
    return [_serialize(report, include_snapshot=False) for report in reports]


@router.get("/{report_id}")
def get_one(
    report_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return _serialize(_owned_report(report_id, user, db))


@router.post("/{report_id}/refresh")
def refresh_report(
    report_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    report = _owned_report(report_id, user, db)
    groups = _groups_for_request(db, user, list(report.experiment_ids or []), report.task_type)
    config = report.config or {}
    primary_metric = config.get("primary_metric") or (
        "r2_test" if report.task_type == "regression" else "f1_macro_test"
    )
    alpha = float(config.get("alpha", 0.05))
    try:
        report.snapshot = build_comparison_snapshot(
            db, groups, report.task_type, primary_metric, alpha
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    report.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(report)
    return _serialize(report)


@router.get("/{report_id}/export/json")
def export_json(
    report_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    report = _owned_report(report_id, user, db)
    payload = _serialize(report)
    filename = safe_filename(f"{report.name}_comparativo") + ".json"
    return Response(
        content=comparison_json_bytes(payload),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{report_id}/export/xlsx")
def export_xlsx(
    report_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    report = _owned_report(report_id, user, db)
    payload = _serialize(report)
    filename = safe_filename(f"{report.name}_comparativo") + ".xlsx"
    return Response(
        content=comparison_xlsx_bytes(payload),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/{report_id}", status_code=204)
def remove(
    report_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    report = _owned_report(report_id, user, db)
    db.delete(report)
    db.commit()
    return Response(status_code=204)
