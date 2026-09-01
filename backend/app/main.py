"""FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import Base, engine
from app.models import *  # noqa: F401, F403 — ensures all models are registered
from app.routers import auth, jira, github, analysis, indexing, code_gen, discovery, runner, settings, root_cause

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting QualityAI backend...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    logger.info("Shutting down — disposing DB engine.")
    await engine.dispose()


app_settings = get_settings()

app = FastAPI(
    title=app_settings.APP_NAME,
    version=app_settings.APP_VERSION,
    description="AI-Assisted Requirements & Test Management Platform API",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ---- CORS ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Routers ----
app.include_router(auth.router, prefix="/api")
app.include_router(jira.router, prefix="/api")
app.include_router(github.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")
app.include_router(indexing.router, prefix="/api")
app.include_router(code_gen.router, prefix="/api")
app.include_router(discovery.router, prefix="/api")
app.include_router(runner.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(root_cause.router, prefix="/api")


# ---- Health check ----
@app.get("/api/health", tags=["Health"])
async def health():
    return {"status": "ok", "version": app_settings.APP_VERSION}


# ---- WebSocket for job status / run logs ----
class ConnectionManager:
    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {}

    async def connect(self, job_id: str, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(job_id, []).append(ws)

    def disconnect(self, job_id: str, ws: WebSocket):
        if job_id in self.active:
            self.active[job_id].remove(ws)

    async def broadcast(self, job_id: str, message: dict):
        for ws in self.active.get(job_id, []):
            try:
                await ws.send_json(message)
            except Exception:
                pass


manager = ConnectionManager()
app.state.ws_manager = manager


@app.websocket("/ws/jobs/{job_id}")
async def job_status_ws(job_id: str, websocket: WebSocket):
    await manager.connect(job_id, websocket)
    try:
        while True:
            await websocket.receive_text()  # keep-alive
    except WebSocketDisconnect:
        manager.disconnect(job_id, websocket)
