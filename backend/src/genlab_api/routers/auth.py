from datetime import datetime,timezone
from fastapi import APIRouter,Depends,HTTPException,status
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import User,RefreshSession
from ..schemas import UserCreate,Login,RefreshRequest,LogoutRequest,UserOut,TokenPair
from ..security import hash_password,verify_password,create_pair,decode_token,token_hash,current_user
from ..config import get_settings
router=APIRouter(prefix="/auth",tags=["auth"]); s=get_settings()
@router.post("/register",response_model=UserOut,status_code=201)
def register(data:UserCreate,db:Session=Depends(get_db)):
    email=data.email.lower()
    if db.scalar(select(User).where(User.email==email)): raise HTTPException(409,"El correo ya está registrado")
    u=User(email=email,full_name=data.full_name.strip(),password_hash=hash_password(data.password)); db.add(u); db.commit(); db.refresh(u); return u
@router.post("/login",response_model=TokenPair)
def login(data:Login,db:Session=Depends(get_db)):
    u=db.scalar(select(User).where(User.email==data.email.lower()))
    if not u or not u.active or not verify_password(data.password,u.password_hash): raise HTTPException(401,"Credenciales incorrectas")
    a,r=create_pair(db,u.id); return TokenPair(access_token=a,refresh_token=r,expires_in=s.access_token_minutes*60)
@router.post("/refresh",response_model=TokenPair)
def refresh(data:RefreshRequest,db:Session=Depends(get_db)):
    payload=decode_token(data.refresh_token,"refresh"); row=db.scalar(select(RefreshSession).where(RefreshSession.token_hash==token_hash(data.refresh_token),RefreshSession.revoked==False))
    if not row: raise HTTPException(401,"Sesión de actualización inválida")
    expiry=row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
    if expiry<datetime.now(timezone.utc): raise HTTPException(401,"Sesión de actualización inválida")
    row.revoked=True; db.commit(); a,r=create_pair(db,payload["sub"]); return TokenPair(access_token=a,refresh_token=r,expires_in=s.access_token_minutes*60)
@router.post("/logout",status_code=204)
def logout(data:LogoutRequest,db:Session=Depends(get_db)):
    row=db.scalar(select(RefreshSession).where(RefreshSession.token_hash==token_hash(data.refresh_token)))
    if row: row.revoked=True; db.commit()
@router.get("/me",response_model=UserOut)
def me(user:User=Depends(current_user)): return user
