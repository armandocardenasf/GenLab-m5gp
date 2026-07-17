from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import get_settings
from .db import Base,engine
from .routers import about,auth,datasets,experiments,gpus
s=get_settings()
@asynccontextmanager
async def lifespan(app): Base.metadata.create_all(engine); yield
app=FastAPI(title=s.app_name,version=s.app_version,lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=[x.strip() for x in s.cors_origins.split(',') if x.strip()],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
app.include_router(about.router,prefix=s.api_prefix); app.include_router(auth.router,prefix=s.api_prefix); app.include_router(datasets.router,prefix=s.api_prefix); app.include_router(experiments.router,prefix=s.api_prefix); app.include_router(gpus.router,prefix=s.api_prefix)
@app.get("/health")
def health(): return {"status":"ok","service":s.app_name,"version":s.app_version}
