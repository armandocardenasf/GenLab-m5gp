from __future__ import annotations
import json
from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..config import get_settings
from ..db import get_db
from ..models import Dataset,Experiment,ExperimentGroup,ExperimentDatasetLink,ExperimentRunLink,ExperimentStatus,User
from ..security import current_user
from ..services.experiments import dispatch_queued
from ..services.grouping import aggregate_metrics,create_runs,serialize_group,validation_defaults

router=APIRouter(prefix="/experiment-groups",tags=["experiment-groups"])

def owned_group(group_id:str,user:User,db:Session)->ExperimentGroup:
    group=db.get(ExperimentGroup,group_id)
    if not group or group.owner_id!=user.id: raise HTTPException(404,"Experimento no encontrado")
    return group

@router.post("",status_code=201)
def create(data:dict,user:User=Depends(current_user),db:Session=Depends(get_db)):
    name=str(data.get("name","")).strip()
    if len(name)<2: raise HTTPException(422,"Nombre inválido")
    task=str(data.get("task_type","regression"))
    if task not in {"regression","classification"}: raise HTTPException(422,"Tipo de tarea inválido")
    datasets=data.get("datasets") or []
    if not datasets: raise HTTPException(422,"Seleccione al menos un dataset")
    try: validation=validation_defaults(data.get("validation"))
    except ValueError as exc: raise HTTPException(422,str(exc))
    runs=max(1,min(int(data.get("runs_per_dataset",1)),100))
    group=ExperimentGroup(owner_id=user.id,name=name,task_type=task,parameters=dict(data.get("parameters") or {}),validation=validation,runs_per_dataset=runs,preset_name=data.get("preset_name"))
    db.add(group); db.flush()
    for position,item in enumerate(datasets):
        ds=db.get(Dataset,str(item.get("dataset_id")))
        target=str(item.get("target_column",""))
        if not ds or ds.owner_id!=user.id: raise HTTPException(404,"Dataset no encontrado")
        if target not in ds.column_names: raise HTTPException(422,f"Variable objetivo inválida para {ds.name}")
        db.add(ExperimentDatasetLink(group_id=group.id,dataset_id=ds.id,target_column=target,position=position))
    db.commit(); db.refresh(group)
    return serialize_group(db,group)

@router.get("")
def list_all(user:User=Depends(current_user),db:Session=Depends(get_db)):
    groups=db.scalars(select(ExperimentGroup).where(ExperimentGroup.owner_id==user.id).order_by(ExperimentGroup.created_at.desc()))
    return [serialize_group(db,g,include_runs=False) for g in groups]

@router.get("/{group_id}")
def get_one(group_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    return serialize_group(db,owned_group(group_id,user,db))

@router.post("/{group_id}/run",status_code=202)
def run_group(group_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    group=owned_group(group_id,user,db)
    create_runs(db,group)
    dispatch_queued(db)
    db.refresh(group)
    return serialize_group(db,group)

@router.get("/{group_id}/results")
def results(group_id:str,max_points:int=Query(default=1000,ge=20,le=10000),user:User=Depends(current_user),db:Session=Depends(get_db)):
    group=owned_group(group_id,user,db)
    result=aggregate_metrics(db,group)
    points=[]
    if group.task_type=="regression":
        settings=get_settings()
        for link in db.scalars(select(ExperimentRunLink).where(ExperimentRunLink.group_id==group.id)):
            run=db.get(Experiment,link.run_id)
            if not run or run.status!=ExperimentStatus.completed.value: continue
            artifact=Path(run.artifact_dir) if run.artifact_dir else settings.artifact_dir/run.owner_id/run.id
            path=artifact/"test_results.json"
            if not path.is_file(): continue
            try: payload=json.loads(path.read_text(encoding="utf-8"))
            except Exception: continue
            for actual,prediction in zip(payload.get("actual",[]),payload.get("prediction",[])):
                try: points.append({"actual":float(actual),"prediction":float(prediction),"run_id":run.id})
                except (TypeError,ValueError): pass
        if len(points)>max_points:
            step=len(points)/max_points
            points=[points[min(int(i*step),len(points)-1)] for i in range(max_points)]
        if len(points)>=2:
            import math
            xs=[p["actual"] for p in points]; ys=[p["prediction"] for p in points]
            mx=sum(xs)/len(xs); my=sum(ys)/len(ys)
            num=sum((x-mx)*(y-my) for x,y in zip(xs,ys)); dx=sum((x-mx)**2 for x in xs); dy=sum((y-my)**2 for y in ys)
            result["correlation"]=num/math.sqrt(dx*dy) if dx>0 and dy>0 else None
        else: result["correlation"]=None
    result["scatter"]=points
    return result
