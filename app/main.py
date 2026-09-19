from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

from .routes.auth import router as auth_router
from .routes.station import router as station_router
from .routes.routing import router as routing_router
from .routes.traffic import router as traffic_router
from .routes.websocket import router as websocket_router
from .db import init_db

app = FastAPI(title="EVisionAI Backend", version="0.1.0")

# CORS (adjust origins as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple cookie-based session
app.add_middleware(SessionMiddleware, secret_key="change-this-secret-key")

@app.on_event("startup")
async def on_startup():
    init_db()

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(station_router, prefix="/stations", tags=["stations"])
app.include_router(routing_router, prefix="/routing", tags=["routing"])
app.include_router(traffic_router, prefix="/traffic", tags=["traffic"])
app.include_router(websocket_router, prefix="/ws", tags=["websocket"])
