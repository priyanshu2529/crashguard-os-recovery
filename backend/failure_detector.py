import time
from typing import Any

from . import config
from .models import FailureEvent, utc_now
from .process_manager import ProcessManager


class FailureDetector:
    def __init__(self, process_manager: ProcessManager) -> None:
        self.process_manager = process_manager

    def detect(self) -> FailureEvent | None:
        info = self.process_manager.info()
        now = time.time()
        state = info.get("state")

        if info["status"] == "STOPPED" and self.process_manager.supervised:
            return self._event("Process Crash", "CRITICAL", "Rollback to latest valid checkpoint", "Demo process terminated")
        if not self.process_manager.supervised and info["status"] == "STOPPED":
            return None
        if not state:
            return self._event("State Corruption", "CRITICAL", "Restore checkpoint", "State file is missing or unreadable")
        if not isinstance(state.get("counter"), int) or not 0 <= int(state.get("progress", -1)) <= 100:
            return self._event("State Corruption", "CRITICAL", "Restore checkpoint", "State schema validation failed")
        heartbeat = float(state.get("heartbeat", 0))
        if now - heartbeat > config.HEARTBEAT_TIMEOUT_SECONDS:
            return self._event("Process Hang", "HIGH", "Restart and restore checkpoint", "Heartbeat timeout exceeded")
        if self.process_manager.memory_mb() > config.MEMORY_THRESHOLD_MB:
            return self._event("Memory Threshold Exceeded", "MEDIUM", "Restore checkpoint if pressure persists", "Process RSS exceeded configured limit")
        return None

    def _event(self, failure_type: str, severity: str, action: str, details: str) -> FailureEvent:
        return FailureEvent(
            failure_type=failure_type,
            severity=severity,
            detected_at=utc_now(),
            recovery_action=action,
            details=details,
        )
