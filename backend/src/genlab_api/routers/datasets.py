from pathlib import Path
import pandas as pd
from fastapi import APIRouter,Depends,File,Form,HTTPException,UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import User,Dataset,Experiment
from ..schemas import DatasetOut,DatasetPreview
from ..security import current_user
from ..deps import owned_dataset
from ..services.files import read_dataset, resolve_dataset_path, save_dataset
router=APIRouter(prefix="/datasets",tags=["datasets"])
@router.post("",response_model=DatasetOut,status_code=201)
def upload(name:str=Form(...),file:UploadFile=File(...),user:User=Depends(current_user),db:Session=Depends(get_db)):
    path,frame,digest=save_dataset(file,user.id); obj=Dataset(owner_id=user.id,name=name.strip(),original_name=file.filename or path.name,path=str(path),sha256=digest,rows=len(frame),columns=len(frame.columns),column_names=[str(x) for x in frame.columns],dtypes={str(k):str(v) for k,v in frame.dtypes.items()}); db.add(obj); db.commit(); db.refresh(obj); return obj
@router.get("",response_model=list[DatasetOut])
def list_all(user:User=Depends(current_user),db:Session=Depends(get_db)): return list(db.scalars(select(Dataset).where(Dataset.owner_id==user.id).order_by(Dataset.created_at.desc())))
@router.get("/{dataset_id}",response_model=DatasetOut)
def get_one(dataset:Dataset=Depends(owned_dataset)): return dataset
@router.get("/{dataset_id}/preview",response_model=DatasetPreview)
def preview(dataset:Dataset=Depends(owned_dataset)):
    frame=read_dataset(dataset.path,user_id=dataset.owner_id,nrows=20); return DatasetPreview(columns=[str(x) for x in frame.columns],rows=frame.where(pd.notna(frame),None).to_dict(orient="records"))
@router.delete("/{dataset_id}",status_code=204)
def remove(dataset:Dataset=Depends(owned_dataset),db:Session=Depends(get_db)):
    if db.scalar(select(Experiment.id).where(Experiment.dataset_id==dataset.id).limit(1)): raise HTTPException(409,"El dataset tiene experimentos asociados")
    resolve_dataset_path(dataset.path,user_id=dataset.owner_id).unlink(missing_ok=True); db.delete(dataset); db.commit()
