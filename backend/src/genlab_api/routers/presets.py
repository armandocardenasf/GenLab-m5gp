from fastapi import APIRouter,Depends,HTTPException,Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import ParameterPreset,User
from ..security import current_user
from ..services.grouping import SYSTEM_PRESETS

router=APIRouter(prefix="/parameter-presets",tags=["parameter-presets"])

def row(p): return {"id":p.id,"name":p.name,"description":p.description,"task_type":p.task_type,"parameters":p.parameters or {},"is_default":p.is_default,"system":False}

@router.get("")
def list_all(user:User=Depends(current_user),db:Session=Depends(get_db)):
    custom=[row(p) for p in db.scalars(select(ParameterPreset).where(ParameterPreset.owner_id==user.id).order_by(ParameterPreset.name))]
    return SYSTEM_PRESETS+custom

@router.post("",status_code=201)
def create(data:dict,user:User=Depends(current_user),db:Session=Depends(get_db)):
    name=str(data.get("name","")).strip()
    if len(name)<2: raise HTTPException(422,"Nombre inválido")
    if data.get("is_default"):
        for item in db.scalars(select(ParameterPreset).where(ParameterPreset.owner_id==user.id)): item.is_default=False
    p=ParameterPreset(owner_id=user.id,name=name,description=str(data.get("description","")),task_type=str(data.get("task_type","regression")),parameters=dict(data.get("parameters") or {}),is_default=bool(data.get("is_default",False)))
    db.add(p); db.commit(); db.refresh(p); return row(p)

@router.put("/{preset_id}")
def update(preset_id:str,data:dict,user:User=Depends(current_user),db:Session=Depends(get_db)):
    p=db.get(ParameterPreset,preset_id)
    if not p or p.owner_id!=user.id: raise HTTPException(404,"Predefinido no encontrado")
    for field in ("name","description","task_type"):
        if field in data: setattr(p,field,str(data[field]))
    if "parameters" in data: p.parameters=dict(data["parameters"] or {})
    if "is_default" in data:
        if data["is_default"]:
            for item in db.scalars(select(ParameterPreset).where(ParameterPreset.owner_id==user.id)): item.is_default=False
        p.is_default=bool(data["is_default"])
    db.commit(); db.refresh(p); return row(p)

@router.delete("/{preset_id}",status_code=204)
def remove(preset_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    p=db.get(ParameterPreset,preset_id)
    if not p or p.owner_id!=user.id: raise HTTPException(404,"Predefinido no encontrado")
    db.delete(p); db.commit(); return Response(status_code=204)
