from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine, SessionLocal
from . import models  # noqa: F401 (registers models with Base)
from .routers import eta, trains, simulate, anomalies, historical, auth, alerts
from .seed import seed_demo_users

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Dynamic ETA Prediction API",
    description="Real-time ETA forecasting for Indian Railways coaching trains (SIH 26028)",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(eta.router)
app.include_router(trains.router)
app.include_router(simulate.router)
app.include_router(anomalies.router)
app.include_router(historical.router)
app.include_router(auth.router)
app.include_router(alerts.router)


@app.on_event("startup")
def _seed_demo_users_on_startup():
    """Seeds admin/operator/viewer demo accounts (item 9) — idempotent,
    safe to run on every startup. See backend/seed.py for credentials."""
    db = SessionLocal()
    try:
        seed_demo_users(db)
    finally:
        db.close()


@app.on_event("startup")
def _warm_caches_on_startup():
    """
    Pre-computes the feature table, /trains summaries, and /anomalies
    Isolation Forest scores once at process startup rather than on the
    first live request. scripts/load_test.py showed this cold-cache cost
    was severe (~9-12s) for both endpoints under concurrent load even
    after adding module-level caching + a lock, since the lock only stops
    duplicate work -- it doesn't stop the first unlucky request(s) from
    still paying the full cost. Warming here means no real user or judge
    request ever hits a cold cache at all.
    """
    from .routers.eta import get_feature_table
    from .routers.trains import get_cached_summaries
    from .routers.anomalies import _get_scored

    df = get_feature_table()
    get_cached_summaries(df)
    _get_scored(df)


@app.get("/")
def root():
    return {"status": "ok", "message": "Dynamic ETA Prediction API is running"}
