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


@app.post("/api/recovery/trigger")
def recovery_trigger(request: dict | None = None):
    try:
        cp_id = request.get("checkpoint_id") if request else None
        if cp_id is not None:
            cp_id = int(cp_id)
        return recovery_engine.trigger_manual(checkpoint_id=cp_id)
    except Exception as exc:
        raise api_error(exc)


@app.get("/api/config")
def get_config():
    rows = db.rows("SELECT key, value FROM configuration")
    conf = {row["key"]: row["value"] for row in rows}
    # Return formatted types with fallbacks
    return {
        "recovery_policy": conf.get("recovery_policy", config.DEFAULT_POLICY),
        "monitor_interval_seconds": float(conf.get("monitor_interval_seconds", config.MONITOR_INTERVAL_SECONDS)),
        "heartbeat_timeout_seconds": float(conf.get("heartbeat_timeout_seconds", config.HEARTBEAT_TIMEOUT_SECONDS)),
        "cpu_threshold_percent": float(conf.get("cpu_threshold_percent", config.CPU_THRESHOLD_PERCENT)),
        "memory_threshold_mb": float(conf.get("memory_threshold_mb", config.MEMORY_THRESHOLD_MB)),
        "app_version": "2.0.0-PROD",
        "storage_paths": {
            "database": str(config.DB_PATH),
            "snapshots": str(config.SNAPSHOT_DIR),
            "logs": str(config.LOG_DIR),
        },
    }


@app.post("/api/config")
def update_config(payload: dict):
    allowed_keys = {
        "recovery_policy": (str, lambda v: v in config.VALID_POLICIES),
        "monitor_interval_seconds": (float, lambda v: 0.5 <= float(v) <= 60.0),
        "heartbeat_timeout_seconds": (float, lambda v: 1.0 <= float(v) <= 120.0),
        "cpu_threshold_percent": (float, lambda v: 10.0 <= float(v) <= 100.0),
        "memory_threshold_mb": (float, lambda v: 50.0 <= float(v) <= 2048.0),
    }
    updated = {}
    for key, val in payload.items():
        if key in allowed_keys and val is not None:
            caster, validator = allowed_keys[key]
            try:
                cast_val = caster(val)
                if not validator(cast_val):
                    raise ValueError(f"Value '{val}' out of valid bounds for {key}")
                db.execute(
                    "INSERT INTO configuration(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, str(cast_val)),
                )
                updated[key] = cast_val
                if key == "recovery_policy":
                    recovery_engine.last_status["policy"] = str(cast_val)
                elif key == "monitor_interval_seconds":
                    config.MONITOR_INTERVAL_SECONDS = float(cast_val)
                elif key == "heartbeat_timeout_seconds":
                    config.HEARTBEAT_TIMEOUT_SECONDS = float(cast_val)
                elif key == "cpu_threshold_percent":
                    config.CPU_THRESHOLD_PERCENT = float(cast_val)
                elif key == "memory_threshold_mb":
                    config.MEMORY_THRESHOLD_MB = float(cast_val)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid configuration for {key}: {e}")
    logger.event("INFO", "CONFIG_UPDATED", f"Updated configuration: {list(updated.keys())}", status="SAVED")
    return {"status": "updated", "updated": updated}


@app.get("/api/analytics/summary")
def analytics_summary():
    # Real SQLite aggregations
    rec_count = db.row("SELECT COUNT(*) AS c FROM recovery_events")["c"]
    rec_success = db.row("SELECT COUNT(*) AS c FROM recovery_events WHERE recovery_status='SUCCESS'")["c"]
    rec_failed = db.row("SELECT COUNT(*) AS c FROM recovery_events WHERE recovery_status='FAILED'")["c"]
    rto_avg = db.row("SELECT AVG(rto) AS avg_rto FROM recovery_events WHERE recovery_status='SUCCESS'")["avg_rto"]
    rto_min = db.row("SELECT MIN(rto) AS min_rto FROM recovery_events WHERE recovery_status='SUCCESS'")["min_rto"]
    rto_max = db.row("SELECT MAX(rto) AS max_rto FROM recovery_events WHERE recovery_status='SUCCESS'")["max_rto"]
    
    cp_total = db.row("SELECT COUNT(*) AS c FROM checkpoints WHERE status != 'deleted'")["c"]
    cp_full = db.row("SELECT COUNT(*) AS c FROM checkpoints WHERE status != 'deleted' AND checkpoint_type='full'")["c"]
    cp_incremental = db.row("SELECT COUNT(*) AS c FROM checkpoints WHERE status != 'deleted' AND checkpoint_type='incremental'")["c"]
    avg_savings = db.row("SELECT AVG(storage_savings) AS s FROM checkpoints WHERE status != 'deleted' AND checkpoint_type='incremental'")["s"]
    
    failure_breakdown = db.rows("SELECT failure_type, COUNT(*) AS count FROM recovery_events GROUP BY failure_type")
    
    recent_rto_series = db.rows("SELECT id, failure_type, rto, recovery_status, recovery_end FROM recovery_events ORDER BY id DESC LIMIT 15")
    recent_cp_series = db.rows("SELECT id, checkpoint_id, checkpoint_type, state_size, storage_savings, timestamp FROM checkpoints WHERE status != 'deleted' ORDER BY id DESC LIMIT 15")
    
    return {
        "recoveries": {
            "total": rec_count,
            "success": rec_success,
            "failed": rec_failed,
            "success_rate": round((rec_success / rec_count * 100), 1) if rec_count > 0 else 0.0,
            "avg_rto": round(rto_avg, 3) if rto_avg is not None else 0.0,
            "min_rto": round(rto_min, 3) if rto_min is not None else 0.0,
            "max_rto": round(rto_max, 3) if rto_max is not None else 0.0,
        },
        "checkpoints": {
            "total": cp_total,
            "full": cp_full,
            "incremental": cp_incremental,
            "avg_savings_pct": round(avg_savings, 1) if avg_savings is not None else 0.0,
        },
        "failure_breakdown": failure_breakdown,
        "recent_rto_series": recent_rto_series,
        "recent_cp_series": recent_cp_series,
    }


@app.get("/api/events/export")
def export_events_csv():
    import csv
    import io
    from fastapi.responses import Response

    records = db.rows("SELECT id, timestamp, level, event_type, message, checkpoint_id, status FROM system_events ORDER BY id DESC")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "timestamp", "level", "event_type", "message", "checkpoint_id", "status"])
    for r in records:
        writer.writerow([r["id"], r["timestamp"], r["level"], r["event_type"], r["message"], r.get("checkpoint_id") or "", r.get("status") or ""])
    
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=crashguard_events.csv"},
    )


@app.get("/api/events")
def events(limit: int = 100, level: str | None = None, event_type: str | None = None, search: str | None = None):
    query = "SELECT * FROM system_events WHERE 1=1"
    params: list = []
    if level and level.upper() != "ALL":
        query += " AND level = ?"
        params.append(level.upper())
    if event_type and event_type.strip():
        query += " AND event_type LIKE ?"
        params.append(f"%{event_type.strip()}%")
    if search and search.strip():
        query += " AND (message LIKE ? OR checkpoint_id LIKE ?)"
        s = f"%{search.strip()}%"
        params.extend([s, s])
    query += " ORDER BY id DESC LIMIT ?"
    params.append(min(max(1, limit), 500))
    return db.rows(query, tuple(params))


if config.FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=config.FRONTEND_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(config.FRONTEND_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=config.PORT, reload=True)
