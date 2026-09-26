import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401  (registers all models on Base before create_all)
from app.database import Base, engine
from app.mqtt_client import start_mqtt_listener, stop_mqtt_listener
from app.routers import auth, dashboard, devices, employees, events, projects, tracking

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="WorkTrack RFID API",
    description="RFID-based time log, project time tracking and workforce utilization platform (MVP).",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    start_mqtt_listener()


@app.on_event("shutdown")
def on_shutdown() -> None:
    stop_mqtt_listener()


@app.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(employees.router)
app.include_router(projects.router)
app.include_router(devices.router)
app.include_router(events.router)
app.include_router(tracking.router)
app.include_router(dashboard.router)
