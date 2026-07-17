from __future__ import annotations
from datetime import datetime,timedelta,timezone
import hashlib,secrets
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends,HTTPException,status
from fastapi.security import HTTPAuthorizationCredentials,HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import get_settings
from .db import get_db
from .models import User,RefreshSession
s=get_settings(); password_hash=PasswordHasher(); bearer=HTTPBearer(auto_error=False)
def hash_password(p): return password_hash.hash(p)
def verify_password(p,h):
    try: return bool(password_hash.verify(h,p))
    except VerifyMismatchError: return False
    except Exception: return False
def _encode(sub,typ,minutes=None,days=None,jti=None):
    now=datetime.now(timezone.utc); exp=now+(timedelta(minutes=minutes) if minutes else timedelta(days=days))
    return jwt.encode({"sub":sub,"type":typ,"iat":now,"exp":exp,"jti":jti or secrets.token_urlsafe(18)},s.secret_key,algorithm="HS256"),exp
def token_hash(token): return hashlib.sha256(token.encode()).hexdigest()
def create_pair(db:Session,user_id:str):
    access,_=_encode(user_id,"access",minutes=s.access_token_minutes)
    refresh,exp=_encode(user_id,"refresh",days=s.refresh_token_days)
    db.add(RefreshSession(user_id=user_id,token_hash=token_hash(refresh),expires_at=exp)); db.commit()
    return access,refresh
def decode_token(token,expected):
    try:
        p=jwt.decode(token,s.secret_key,algorithms=["HS256"])
        if p.get("type")!=expected: raise ValueError
        return p
    except Exception as exc: raise HTTPException(status.HTTP_401_UNAUTHORIZED,"Token inválido o vencido") from exc
def current_user(credentials:HTTPAuthorizationCredentials|None=Depends(bearer),db:Session=Depends(get_db)):
    if not credentials: raise HTTPException(401,"Autenticación requerida")
    uid=decode_token(credentials.credentials,"access")["sub"]; u=db.get(User,uid)
    if not u or not u.active: raise HTTPException(401,"Usuario inactivo o inexistente")
    return u
