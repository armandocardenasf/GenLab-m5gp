from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Batch,BatchExperimentLink,ExperimentGroup,User
from ..security import current_user
from ..services.experiments import dispatch_queued
from ..services.grouping import create_runs,serialize_group

router=APIRouter(prefix="/batches",tags=["batches"])

def owned(batch_id,user,db):
    b=db.get(Batch,batch_id)
    if not b or b.owner_id!=user.id: raise HTTPException(404,"Lote no encontrado")
    return b

def serialize(db,b):
    groups=[]
    for link in db.scalars(select(BatchExperimentLink).where(BatchExperimentLink.batch_id==b.id).order_by(BatchExperimentLink.position)):
        g=db.get(ExperimentGroup,link.group_id)
        if g: groups.append(serialize_group(db,g,include_runs=False))
    statuses=[g["status"] for g in groups]
    status="completed" if groups and all(s=="completed" for s in statuses) else ("running" if any(s in {"running","queued"} for s in statuses) else b.status)
    return {"id":b.id,"name":b.name,"status":status,"created_at":b.created_at,"experiments":groups}

@router.post("",status_code=201)
def create(data:dict,user:User=Depends(current_user),db:Session=Depends(get_db)):
    ids=list(data.get("experiment_ids") or [])
    if not ids: raise HTTPException(422,"Seleccione al menos un experimento")
    b=Batch(owner_id=user.id,name=str(data.get("name") or "Lote de experimentos")); db.add(b); db.flush()
    for position,gid in enumerate(ids):
        g=db.get(ExperimentGroup,str(gid))
        if not g or g.owner_id!=user.id: raise HTTPException(404,"Experimento no encontrado")
        db.add(BatchExperimentLink(batch_id=b.id,group_id=g.id,position=position))
    db.commit(); db.refresh(b); return serialize(db,b)

@router.get("")
def list_all(user:User=Depends(current_user),db:Session=Depends(get_db)):
    return [serialize(db,b) for b in db.scalars(select(Batch).where(Batch.owner_id==user.id).order_by(Batch.created_at.desc()))]

@router.get("/{batch_id}")
def get_one(batch_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)): return serialize(db,owned(batch_id,user,db))

@router.post("/{batch_id}/run",status_code=202)
def run(batch_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    b=owned(batch_id,user,db); b.status="queued"
    for link in db.scalars(select(BatchExperimentLink).where(BatchExperimentLink.batch_id==b.id)):
        g=db.get(ExperimentGroup,link.group_id)
        if g: create_runs(db,g)
    db.commit(); dispatch_queued(db); return serialize(db,b)
