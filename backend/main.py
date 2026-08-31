from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from . import models  # noqa: F401 (registers models with Base)
from .routers import eta, trains, simulate

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


@app.get("/")
def root():
    return {"status": "ok", "message": "Dynamic ETA Prediction API is running"}
