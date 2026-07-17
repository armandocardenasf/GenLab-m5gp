from fastapi import APIRouter,Depends
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import User
from ..security import current_user
from ..schemas import GPUOut
from ..services.gpu import status
router=APIRouter(prefix="/gpus",tags=["gpus"])
@router.get("",response_model=list[GPUOut])
def resources(user:User=Depends(current_user),db:Session=Depends(get_db)): return status(db)
