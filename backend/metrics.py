import shutil

import psutil

from .checkpoint import CheckpointManager
from .database import Database
from .process_manager import ProcessManager


class MetricsService:
    def __init__(self, db: Database, process_manager: ProcessManager, checkpoints: CheckpointManager) -> None:
        self.db = db
        self.process_manager = process_manager
        self.checkpoints = checkpoints

    def system_status(self) -> dict:
        process = self.process_manager.info()
        checkpoint_count = self.db.row("SELECT COUNT(*) AS count FROM checkpoints WHERE status != 'deleted'")["count"]
        recovery_count = self.db.row("SELECT COUNT(*) AS count FROM recovery_events")["count"]
        last_checkpoint = self.db.row("SELECT checkpoint_id, timestamp FROM checkpoints WHERE status != 'deleted' ORDER BY id DESC LIMIT 1")
        last_recovery = self.db.row("SELECT recovery_end, recovery_status FROM recovery_events ORDER BY id DESC LIMIT 1")
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory().percent
        health = "HEALTHY"
        if process["status"] in {"STOPPED", "HUNG"} or cpu > 90 or ram > 90:
            health = "CRITICAL"
        elif cpu > 75 or ram > 75:
            health = "WARNING"
        return {
            "cpu": cpu,
            "memory": ram,
            "disk": shutil.disk_usage(".").used / shutil.disk_usage(".").total * 100,
            "process": process,
            "checkpoint_count": checkpoint_count,
            "recovery_count": recovery_count,
            "last_checkpoint": last_checkpoint,
            "last_recovery": last_recovery,
            "system_health": health,
        }

    def metrics(self) -> dict:
        virtual = psutil.virtual_memory()
        return {
            "cpu_percent": psutil.cpu_percent(interval=None),
            "ram_percent": virtual.percent,
            "ram_used_mb": round(virtual.used / (1024 * 1024), 2),
            "process_memory_mb": round(self.process_manager.memory_mb(), 2),
            "disk_percent": round(shutil.disk_usage(".").used / shutil.disk_usage(".").total * 100, 2),
        }
