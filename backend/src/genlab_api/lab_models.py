from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def uid() -> str:
    return str(uuid4())


def now() -> datetime:
    return datetime.now(timezone.utc)


class ExperimentGroup(Base):
    """Scientific experiment that groups one or more individual M5GP runs."""

    __tablename__ = "experiment_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    task_type: Mapped[str] = mapped_column(String(20))
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    validation: Mapped[dict] = mapped_column(JSON, default=dict)
    runs_per_dataset: Mapped[int] = mapped_column(Integer, default=1)
    preset_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="created", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now
    )


class ExperimentDatasetLink(Base):
    """Datasets included in a grouped experiment."""

    __tablename__ = "experiment_group_datasets"

    group_id: Mapped[str] = mapped_column(
        ForeignKey("experiment_groups.id", ondelete="CASCADE"), primary_key=True
    )
    dataset_id: Mapped[str] = mapped_column(
        ForeignKey("datasets.id", ondelete="RESTRICT"), primary_key=True
    )
    target_column: Mapped[str] = mapped_column(String(255))
    position: Mapped[int] = mapped_column(Integer, default=0)


class ExperimentRunLink(Base):
    """Association between a grouped experiment and a legacy execution row.

    The existing ``experiments`` table is deliberately preserved for backwards
    compatibility.  In the new model each row in that table is an individual
    run/corrida, and this table links it to its scientific experiment.
    """

    __tablename__ = "experiment_group_runs"

    group_id: Mapped[str] = mapped_column(
        ForeignKey("experiment_groups.id", ondelete="CASCADE"), primary_key=True
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"),
        primary_key=True,
        unique=True,
    )
    repeat_index: Mapped[int] = mapped_column(Integer, default=0)
    fold_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seed: Mapped[int] = mapped_column(Integer, default=42)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now
    )


class ParameterPreset(Base):
    """User-defined advanced M5GP parameter preset."""

    __tablename__ = "parameter_presets"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_parameter_preset_owner_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(400), default="")
    task_type: Mapped[str] = mapped_column(String(20), default="both")
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now
    )


class Batch(Base):
    """Batch/lote that launches several grouped experiments."""

    __tablename__ = "batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30), default="created", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now
    )


class BatchExperimentLink(Base):
    __tablename__ = "batch_experiments"

    batch_id: Mapped[str] = mapped_column(
        ForeignKey("batches.id", ondelete="CASCADE"), primary_key=True
    )
    group_id: Mapped[str] = mapped_column(
        ForeignKey("experiment_groups.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0)

class ComparisonReport(Base):
    """Saved comparative analysis across experiment groups of the same task type."""

    __tablename__ = "comparison_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(1000), default="")
    task_type: Mapped[str] = mapped_column(String(20), index=True)
    experiment_ids: Mapped[list] = mapped_column(JSON, default=list)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
