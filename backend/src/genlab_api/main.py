from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import Base, engine
from .routers import (
    about,
    auth,
    batches,
    comparison_reports,
    datasets,
    experiment_groups,
    experiments,
    gpus,
    presets,
    runs,
)

s = get_settings()


@asynccontextmanager
async def lifespan(app):
    # Importing the new routers above registers the incremental SQLAlchemy
    # tables defined in lab_models.py before create_all() is executed.
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title=s.app_name, version=s.app_version, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in s.cors_origins.split(",") if x.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(about.router, prefix=s.api_prefix)
app.include_router(auth.router, prefix=s.api_prefix)
app.include_router(datasets.router, prefix=s.api_prefix)

# Legacy endpoint kept for backwards compatibility.  Rows in this table are
# now individual runs/corridas in the scientific model.
app.include_router(experiments.router, prefix=s.api_prefix)

# New incremental API.
app.include_router(runs.router, prefix=s.api_prefix)
app.include_router(experiment_groups.router, prefix=s.api_prefix)
app.include_router(presets.router, prefix=s.api_prefix)
app.include_router(batches.router, prefix=s.api_prefix)
app.include_router(comparison_reports.router, prefix=s.api_prefix)
app.include_router(gpus.router, prefix=s.api_prefix)


@app.get("/health")
def health():
    return {"status": "ok", "service": s.app_name, "version": s.app_version}
