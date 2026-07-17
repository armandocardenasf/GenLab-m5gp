from fastapi import Depends,HTTPException
from sqlalchemy.orm import Session
from .db import get_db
from .models import User,Dataset,Experiment
from .security import current_user

def owned_dataset(dataset_id:str,db:Session=Depends(get_db),user:User=Depends(current_user)):
    obj=db.get(Dataset,dataset_id)
    if not obj or obj.owner_id!=user.id: raise HTTPException(404,"Dataset no encontrado")
    return obj
def owned_experiment(experiment_id:str,db:Session=Depends(get_db),user:User=Depends(current_user)):
    obj=db.get(Experiment,experiment_id)
    if not obj or obj.owner_id!=user.id: raise HTTPException(404,"Experimento no encontrado")
    return obj
