from __future__ import annotations
from datetime import datetime,timezone
from enum import Enum
from uuid import uuid4
from sqlalchemy import String,Integer,Boolean,DateTime,ForeignKey,JSON,Text,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from .db import Base

def uid(): return str(uuid4())
def now(): return datetime.now(timezone.utc)

class ExperimentStatus(str,Enum):
    created="created"; queued="queued"; reserved="reserved"; running="running"; cancelling="cancelling"; cancelled="cancelled"; completed="completed"; failed="failed"; rejected="rejected"

class User(Base):
    __tablename__="users"; id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); email:Mapped[str]=mapped_column(String(320),unique=True,index=True); full_name:Mapped[str]=mapped_column(String(200)); password_hash:Mapped[str]=mapped_column(String(500)); active:Mapped[bool]=mapped_column(Boolean,default=True); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class RefreshSession(Base):
    __tablename__="refresh_sessions"; id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); user_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True); token_hash:Mapped[str]=mapped_column(String(64),unique=True); expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True)); revoked:Mapped[bool]=mapped_column(Boolean,default=False); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class Dataset(Base):
    __tablename__="datasets"; id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); owner_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True); name:Mapped[str]=mapped_column(String(200)); original_name:Mapped[str]=mapped_column(String(255)); path:Mapped[str]=mapped_column(Text); sha256:Mapped[str]=mapped_column(String(64)); rows:Mapped[int]=mapped_column(Integer); columns:Mapped[int]=mapped_column(Integer); column_names:Mapped[list]=mapped_column(JSON); dtypes:Mapped[dict]=mapped_column(JSON); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

# Legacy/current execution row. In GenLab v2 this is exposed as an individual run.
class Experiment(Base):
    __tablename__="experiments"; id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); owner_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True); dataset_id:Mapped[str]=mapped_column(ForeignKey("datasets.id",ondelete="RESTRICT"),index=True); name:Mapped[str]=mapped_column(String(200)); task_type:Mapped[str]=mapped_column(String(20)); target_column:Mapped[str]=mapped_column(String(255)); parameters:Mapped[dict]=mapped_column(JSON,default=dict); status:Mapped[str]=mapped_column(String(30),default=ExperimentStatus.created.value,index=True); gpu_id:Mapped[int|None]=mapped_column(Integer,nullable=True); worker_pid:Mapped[int|None]=mapped_column(Integer,nullable=True); progress:Mapped[dict]=mapped_column(JSON,default=dict); metrics:Mapped[dict|None]=mapped_column(JSON,nullable=True); symbolic_model:Mapped[str|None]=mapped_column(Text,nullable=True); complexity:Mapped[str|None]=mapped_column(String(80),nullable=True); artifact_dir:Mapped[str|None]=mapped_column(Text,nullable=True); log_path:Mapped[str|None]=mapped_column(Text,nullable=True); error:Mapped[str|None]=mapped_column(Text,nullable=True); cancel_requested:Mapped[bool]=mapped_column(Boolean,default=False); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now); started_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True); finished_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class ExperimentGroup(Base):
    __tablename__="experiment_groups"; id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); owner_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True); name:Mapped[str]=mapped_column(String(200)); task_type:Mapped[str]=mapped_column(String(20)); parameters:Mapped[dict]=mapped_column(JSON,default=dict); validation:Mapped[dict]=mapped_column(JSON,default=dict); runs_per_dataset:Mapped[int]=mapped_column(Integer,default=1); preset_name:Mapped[str|None]=mapped_column(String(120),nullable=True); status:Mapped[str]=mapped_column(String(30),default="created",index=True); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class ExperimentDatasetLink(Base):
    __tablename__="experiment_group_datasets"; group_id:Mapped[str]=mapped_column(ForeignKey("experiment_groups.id",ondelete="CASCADE"),primary_key=True); dataset_id:Mapped[str]=mapped_column(ForeignKey("datasets.id",ondelete="RESTRICT"),primary_key=True); target_column:Mapped[str]=mapped_column(String(255)); position:Mapped[int]=mapped_column(Integer,default=0)

class ExperimentRunLink(Base):
    __tablename__="experiment_group_runs"; group_id:Mapped[str]=mapped_column(ForeignKey("experiment_groups.id",ondelete="CASCADE"),primary_key=True); run_id:Mapped[str]=mapped_column(ForeignKey("experiments.id",ondelete="CASCADE"),primary_key=True,unique=True); repeat_index:Mapped[int]=mapped_column(Integer,default=0); fold_index:Mapped[int|None]=mapped_column(Integer,nullable=True); seed:Mapped[int]=mapped_column(Integer,default=42); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class ParameterPreset(Base):
    __tablename__="parameter_presets"; __table_args__=(UniqueConstraint("owner_id","name",name="uq_preset_owner_name"),); id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); owner_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True); name:Mapped[str]=mapped_column(String(120)); description:Mapped[str]=mapped_column(String(300),default=""); task_type:Mapped[str]=mapped_column(String(20),default="regression"); parameters:Mapped[dict]=mapped_column(JSON,default=dict); is_default:Mapped[bool]=mapped_column(Boolean,default=False); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class Batch(Base):
    __tablename__="batches"; id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); owner_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True); name:Mapped[str]=mapped_column(String(200)); status:Mapped[str]=mapped_column(String(30),default="created",index=True); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class BatchExperimentLink(Base):
    __tablename__="batch_experiments"; batch_id:Mapped[str]=mapped_column(ForeignKey("batches.id",ondelete="CASCADE"),primary_key=True); group_id:Mapped[str]=mapped_column(ForeignKey("experiment_groups.id",ondelete="CASCADE"),primary_key=True); position:Mapped[int]=mapped_column(Integer,default=0)

class GPULease(Base):
    __tablename__="gpu_leases"; device_id:Mapped[int]=mapped_column(Integer,primary_key=True); experiment_id:Mapped[str]=mapped_column(String(36),unique=True,index=True); user_id:Mapped[str]=mapped_column(String(36),index=True); worker_pid:Mapped[int|None]=mapped_column(Integer,nullable=True); acquired_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now); heartbeat_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
