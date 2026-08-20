import hashlib
import json
from pathlib import Path
from typing import Any

from . import config
from .database import Database
from .logger import EventLogger
from .models import DemoState, utc_now
from .process_manager import ProcessManager


def state_hash(state: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(state, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def snapshot_checksum(payload: dict[str, Any]) -> str:
    clone = dict(payload)
    clone.pop("checksum", None)
    return hashlib.sha256(json.dumps(clone, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def diff_states(base: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in current.items() if base.get(key) != value}


class CheckpointManager:
    def __init__(self, db: Database, process_manager: ProcessManager, logger: EventLogger) -> None:
        self.db = db
        self.process_manager = process_manager
        self.logger = logger

    def create(self) -> dict[str, Any]:
        state = self.process_manager.read_state(safe=True)
        if not state:
            raise ValueError("Demo process has no checkpointable state. Start the process first.")
        DemoState.model_validate(state)

        latest = self.latest()
        base_state = self.reconstruct(latest["id"]) if latest else None
        checkpoint_type = "incremental" if base_state else "full"
        stored_state = diff_states(base_state, state) if base_state else state
        full_size = len(json.dumps(state).encode())
        stored_size = len(json.dumps(stored_state).encode())
        savings = round(max(0, 1 - (stored_size / max(full_size, 1))) * 100, 2)

        next_number = (self.db.row("SELECT MAX(id) AS max_id FROM checkpoints") or {}).get("max_id") or 0
        label = f"CP-{next_number + 1:03d}"
        snapshot = {
            "checkpoint_id": label,
            "checkpoint_type": checkpoint_type,
            "base_checkpoint_id": latest["id"] if latest else None,
            "timestamp": utc_now(),
            "state": stored_state,
            "full_state_hash": state_hash(state),
        }
        snapshot["checksum"] = snapshot_checksum(snapshot)
        path = config.SNAPSHOT_DIR / f"{label}.json"
        path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

        row_id = self.db.execute(
            """
            INSERT INTO checkpoints(
                checkpoint_id, timestamp, state_size, checkpoint_type, process_id, status,
                checksum, snapshot_path, base_checkpoint_id, storage_savings, validation_reason
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                label,
                snapshot["timestamp"],
                stored_size,
                checkpoint_type,
                self.process_manager.pid(),
                "valid",
                snapshot["checksum"],
                str(path),
                latest["id"] if latest else None,
                savings,
                "OK",
            ),
        )
        self.logger.event("INFO", "CHECKPOINT_CREATED", f"Checkpoint {label} created", label, "SUCCESS")
        return self.get(row_id)

    def list(self) -> list[dict[str, Any]]:
        return self.db.rows("SELECT * FROM checkpoints WHERE status != 'deleted' ORDER BY id DESC")

    def latest(self) -> dict[str, Any] | None:
        return self.db.row("SELECT * FROM checkpoints WHERE status='valid' ORDER BY id DESC LIMIT 1")

    def get(self, checkpoint_id: int | str) -> dict[str, Any]:
        field = "id" if isinstance(checkpoint_id, int) or str(checkpoint_id).isdigit() else "checkpoint_id"
        row = self.db.row(f"SELECT * FROM checkpoints WHERE {field}=?", (checkpoint_id,))
        if not row or row["status"] == "deleted":
            raise KeyError(f"Checkpoint {checkpoint_id} not found")
        validation = self.validate(row["id"])
        row["validation"] = validation
        return row

    def delete(self, checkpoint_id: int) -> None:
        row = self.get(checkpoint_id)
        self.db.execute("UPDATE checkpoints SET status='deleted' WHERE id=?", (checkpoint_id,))
        self.logger.event("INFO", "CHECKPOINT_DELETED", f"Checkpoint {row['checkpoint_id']} deleted", row["checkpoint_id"], "DELETED")

    def validate(self, checkpoint_id: int) -> dict[str, Any]:
        row = self.db.row("SELECT * FROM checkpoints WHERE id=?", (checkpoint_id,))
        if not row:
            return {"valid": False, "reason": "METADATA MISSING"}
        path = Path(row["snapshot_path"])
        if not path.exists():
            self._mark_invalid(checkpoint_id, "SNAPSHOT FILE MISSING")
            return {"valid": False, "reason": "SNAPSHOT FILE MISSING"}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            self._mark_invalid(checkpoint_id, "SNAPSHOT JSON INVALID")
            return {"valid": False, "reason": "SNAPSHOT JSON INVALID"}
        if payload.get("checksum") != snapshot_checksum(payload):
            self._mark_invalid(checkpoint_id, "CHECKSUM MISMATCH")
            return {"valid": False, "reason": "CHECKSUM MISMATCH"}
        try:
            full_state = self.reconstruct(checkpoint_id, validate_chain=False)
            DemoState.model_validate(full_state)
            if state_hash(full_state) != payload.get("full_state_hash"):
                self._mark_invalid(checkpoint_id, "STATE HASH MISMATCH")
                return {"valid": False, "reason": "STATE HASH MISMATCH"}
        except Exception as exc:
            self._mark_invalid(checkpoint_id, f"STATE INVALID: {exc}")
            return {"valid": False, "reason": f"STATE INVALID: {exc}"}
        if row["status"] != "valid":
            self.db.execute("UPDATE checkpoints SET status='valid', validation_reason='OK' WHERE id=?", (checkpoint_id,))
        return {"valid": True, "reason": "OK"}

    def reconstruct(self, checkpoint_id: int, validate_chain: bool = True) -> dict[str, Any]:
        row = self.db.row("SELECT * FROM checkpoints WHERE id=?", (checkpoint_id,))
        if not row or row["status"] == "deleted":
            raise KeyError("Checkpoint metadata missing")
        if validate_chain and not self.validate(checkpoint_id)["valid"]:
            raise ValueError("Checkpoint failed validation")
        payload = json.loads(Path(row["snapshot_path"]).read_text(encoding="utf-8"))
        if row["checkpoint_type"] == "full":
            return payload["state"]
        if not row["base_checkpoint_id"]:
            raise ValueError("Incremental checkpoint has no base")
        state = self.reconstruct(int(row["base_checkpoint_id"]), validate_chain=False)
        state.update(payload["state"])
        return state

    def restore(self, checkpoint_id: int) -> dict[str, Any]:
        if not self.db.row("SELECT id FROM checkpoints WHERE id=? AND status != 'deleted'", (checkpoint_id,)):
            raise KeyError(f"Checkpoint {checkpoint_id} not found")
        validation = self.validate(checkpoint_id)
        if not validation["valid"]:
            raise ValueError(f"Invalid checkpoint: {validation['reason']}")
        state = self.reconstruct(checkpoint_id)
        info = self.process_manager.restart(state)
        row = self.get(checkpoint_id)
        self.logger.event("INFO", "CHECKPOINT_RESTORED", f"Restored {row['checkpoint_id']}", row["checkpoint_id"], "RESTORED")
        return {"checkpoint": row, "process": info, "restored_state": state}

    def safest(self) -> dict[str, Any] | None:
        for row in self.list():
            if self.validate(int(row["id"]))["valid"]:
                return self.db.row("SELECT * FROM checkpoints WHERE id=?", (row["id"],))
        return None

    def _mark_invalid(self, checkpoint_id: int, reason: str) -> None:
        self.db.execute("UPDATE checkpoints SET status='invalid', validation_reason=? WHERE id=?", (reason, checkpoint_id))
