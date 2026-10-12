import time
from typing import Any

from . import config
from .checkpoint import CheckpointManager
from .database import Database
from .logger import EventLogger
from .models import FailureEvent, utc_now


class RecoveryEngine:
    def __init__(self, db: Database, checkpoints: CheckpointManager, logger: EventLogger) -> None:
        self.db = db
        self.checkpoints = checkpoints
        self.logger = logger
        self.last_status: dict[str, Any] = {"status": "IDLE", "policy": self.get_policy()}
        self._recovering = False

    def get_policy(self) -> str:
        row = self.db.row("SELECT value FROM configuration WHERE key='recovery_policy'")
        return row["value"] if row else config.DEFAULT_POLICY

    def set_policy(self, policy: str) -> dict[str, str]:
        if policy not in config.VALID_POLICIES:
            raise ValueError(f"Invalid policy. Use one of: {', '.join(sorted(config.VALID_POLICIES))}")
        self.db.execute(
            "INSERT INTO configuration(key, value) VALUES('recovery_policy', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (policy,),
        )
        self.last_status["policy"] = policy
        self.logger.event("INFO", "POLICY_CHANGED", f"Recovery policy changed to {policy}", status="UPDATED")
        return {"policy": policy}

    def recover(self, failure: FailureEvent, checkpoint_id: int | None = None) -> dict[str, Any]:
        if self._recovering:
            return {"status": "ALREADY_RECOVERING"}
        self._recovering = True
        failure_time = failure.detected_at
        detection_time = utc_now()
        start_monotonic = time.perf_counter()
        recovery_start = utc_now()
        selected = None
        status = "FAILED"
        try:
            selected = self._select_checkpoint(checkpoint_id)
            if not selected:
                raise RuntimeError("No valid checkpoint is available for recovery")
            self.logger.event("INFO", "RECOVERY_STARTED", f"Recovery initiated using {selected['checkpoint_id']}", selected["checkpoint_id"], "STARTED")
            result = self.checkpoints.restore(int(selected["id"]))
            status = "SUCCESS"
            return {"status": status, "checkpoint": selected, "result": result}
        except Exception as exc:
            self.logger.event("ERROR", "RECOVERY_FAILED", f"Recovery failed: {exc}", status="FAILED")
            return {"status": status, "error": str(exc)}
        finally:
            duration = round(time.perf_counter() - start_monotonic, 3)
            recovery_end = utc_now()
            checkpoint_label = selected["checkpoint_id"] if selected else None
            self.db.execute(
                """
                INSERT INTO recovery_events(
                    failure_type, failure_time, detection_time, recovery_start, recovery_end,
                    recovery_duration, rto, checkpoint_used, recovery_status
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (failure.failure_type, failure_time, detection_time, recovery_start, recovery_end, duration, duration, checkpoint_label, status),
            )
            self.last_status = {
                "status": "RECOVERED" if status == "SUCCESS" else "FAILED",
                "last_failure": failure.failure_type,
                "checkpoint_used": checkpoint_label,
                "recovery_duration": duration,
                "rto": duration,
                "policy": self.get_policy(),
            }
            if status == "SUCCESS":
                self.logger.event("INFO", "RECOVERY_SUCCESSFUL", f"Recovery successful | RTO={duration}s", checkpoint_label, "RECOVERED")
            self._recovering = False

    def history(self) -> list[dict[str, Any]]:
        return self.db.rows("SELECT * FROM recovery_events ORDER BY id DESC LIMIT 50")

    def status(self) -> dict[str, Any]:
        return self.last_status | {"policy": self.get_policy()}

    def trigger_manual(self, checkpoint_id: int | None = None) -> dict[str, Any]:
        failure = FailureEvent(
            failure_type="Manual Operator Trigger",
            severity="OPERATIONAL",
            detected_at=utc_now(),
            recovery_action="Manual rollback requested via recovery console",
            details=f"Operator requested recovery to checkpoint ID: {checkpoint_id or 'policy default'}",
        )
        return self.recover(failure, checkpoint_id=checkpoint_id)

    def _select_checkpoint(self, checkpoint_id: int | None) -> dict[str, Any] | None:
        policy = self.get_policy()
        if checkpoint_id is not None or policy == "manual":
            if checkpoint_id is None:
                raise ValueError("Manual recovery requires a checkpoint ID")
            row = self.checkpoints.get(checkpoint_id)
            if not row["validation"]["valid"]:
                raise ValueError(row["validation"]["reason"])
            return row
        if policy in {"safest", "automatic"}:
            return self.checkpoints.safest()
        return self.checkpoints.latest()
