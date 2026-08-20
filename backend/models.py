from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


CheckpointType = Literal["full", "incremental"]
CheckpointStatus = Literal["valid", "invalid", "deleted"]
RecoveryPolicy = Literal["latest", "safest", "manual", "automatic"]


class DemoState(BaseModel):
    counter: int
    current_task: str
    progress: int = Field(ge=0, le=100)
    current_item: int
    memory_state: dict[str, Any]
    process_status: str
    timestamp: str
    heartbeat: float


class CheckpointRecord(BaseModel):
    id: int
    checkpoint_id: str
    timestamp: str
    state_size: int
    checkpoint_type: CheckpointType
    process_id: int | None
    status: CheckpointStatus
    checksum: str
    snapshot_path: str
    base_checkpoint_id: int | None = None
    storage_savings: float = 0.0
    validation_reason: str | None = None


class FailureEvent(BaseModel):
    failure_type: str
    severity: str
    detected_at: str
    recovery_action: str
    details: str


class RecoveryEvent(BaseModel):
    id: int
    failure_type: str
    failure_time: str
    detection_time: str
    recovery_start: str
    recovery_end: str
    recovery_duration: float
    rto: float
    checkpoint_used: str | None
    recovery_status: str


class ProcessInfo(BaseModel):
    name: str
    pid: int | None
    status: str
    uptime: float
    state: dict[str, Any] | None = None


def utc_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"
