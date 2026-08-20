from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config
from .checkpoint import CheckpointManager
from .database import Database
from .failure_detector import FailureDetector
from .failure_simulator import FailureSimulator
from .logger import EventLogger
from .metrics import MetricsService
from .monitor import SystemMonitor
from .process_manager import ProcessManager
from .recovery import RecoveryEngine


db = Database()
config.ensure_directories()
db.init()
logger = EventLogger(db)
process_manager = ProcessManager(logger)
checkpoint_manager = CheckpointManager(db, process_manager, logger)
recovery_engine = RecoveryEngine(db, checkpoint_manager, logger)
failure_detector = FailureDetector(process_manager)
failure_simulator = FailureSimulator(process_manager, logger)
metrics_service = MetricsService(db, process_manager, checkpoint_manager)
monitor = SystemMonitor(failure_detector, recovery_engine, logger)


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.ensure_directories()
    db.init()
    logger.event("INFO", "SYSTEM_START", "CrashGuard backend started", status="ONLINE")
    monitor.start()
    yield
    await monitor.stop()
    process_manager.stop()


app = FastAPI(title="CrashGuard", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class PolicyRequest(BaseModel):
    policy: str


def api_error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, (ValueError, RuntimeError)):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


@app.get("/api/system/status")
def system_status():
    return metrics_service.system_status()


@app.get("/api/system/metrics")
def system_metrics():
    return metrics_service.metrics()


@app.get("/api/process")
def process_info():
    return process_manager.info()


@app.post("/api/process/start")
def process_start():
    try:
        return process_manager.start()
    except Exception as exc:
        raise api_error(exc)


@app.post("/api/process/stop")
def process_stop():
    return process_manager.stop()


@app.post("/api/checkpoints/create")
def checkpoint_create():
    try:
        return checkpoint_manager.create()
    except Exception as exc:
        raise api_error(exc)


@app.get("/api/checkpoints")
def checkpoints():
    return checkpoint_manager.list()


@app.get("/api/checkpoints/{checkpoint_id}")
def checkpoint_detail(checkpoint_id: int):
    try:
        return checkpoint_manager.get(checkpoint_id)
    except Exception as exc:
        raise api_error(exc)


@app.delete("/api/checkpoints/{checkpoint_id}")
def checkpoint_delete(checkpoint_id: int):
    try:
        checkpoint_manager.delete(checkpoint_id)
        return {"status": "deleted"}
    except Exception as exc:
        raise api_error(exc)


@app.post("/api/checkpoints/{checkpoint_id}/restore")
def checkpoint_restore(checkpoint_id: int):
    try:
        return checkpoint_manager.restore(checkpoint_id)
    except Exception as exc:
        raise api_error(exc)


@app.post("/api/failure/crash")
def failure_crash():
    try:
        return failure_simulator.crash()
    except Exception as exc:
        raise api_error(exc)


@app.post("/api/failure/hang")
def failure_hang():
    try:
        return failure_simulator.hang()
    except Exception as exc:
        raise api_error(exc)


@app.post("/api/failure/corrupt")
def failure_corrupt():
    try:
        return failure_simulator.corrupt()
    except Exception as exc:
        raise api_error(exc)


@app.post("/api/failure/memory")
def failure_memory():
    try:
        return failure_simulator.memory_stress()
    except Exception as exc:
        raise api_error(exc)


@app.post("/api/failure/random")
def failure_random():
    try:
        return failure_simulator.random()
    except Exception as exc:
        raise api_error(exc)


@app.get("/api/recovery/history")
def recovery_history():
    return recovery_engine.history()


@app.get("/api/recovery/status")
def recovery_status():
    return recovery_engine.status()


@app.post("/api/recovery/policy")
def set_policy(request: PolicyRequest):
    try:
        return recovery_engine.set_policy(request.policy)
    except Exception as exc:
        raise api_error(exc)


@app.get("/api/events")
def events(limit: int = 80):
    return db.rows("SELECT * FROM system_events ORDER BY id DESC LIMIT ?", (limit,))


if config.FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=config.FRONTEND_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(config.FRONTEND_DIR / "index.html")
