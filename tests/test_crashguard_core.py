import json
import time
from pathlib import Path

import pytest

from backend import config
from backend.checkpoint import CheckpointManager
from backend.database import Database
from backend.failure_detector import FailureDetector
from backend.logger import EventLogger
from backend.process_manager import ProcessManager
from backend.recovery import RecoveryEngine
from backend.models import FailureEvent, utc_now


@pytest.fixture()
def rig(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "CHECKPOINT_DIR", tmp_path / "checkpoints")
    monkeypatch.setattr(config, "SNAPSHOT_DIR", tmp_path / "checkpoints" / "snapshots")
    monkeypatch.setattr(config, "METADATA_DIR", tmp_path / "checkpoints" / "metadata")
    monkeypatch.setattr(config, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "data" / "crashguard.db")
    monkeypatch.setattr(config, "PROCESS_STATE_PATH", tmp_path / "data" / "demo_state.json")
    monkeypatch.setattr(config, "PROCESS_COMMAND_PATH", tmp_path / "data" / "demo_command.json")
    monkeypatch.setattr(config, "HEARTBEAT_TIMEOUT_SECONDS", 1.0)
    config.ensure_directories()
    db = Database(config.DB_PATH)
    db.init()
    logger = EventLogger(db)
    process = ProcessManager(logger)
    checkpoints = CheckpointManager(db, process, logger)
    recovery = RecoveryEngine(db, checkpoints, logger)
    yield db, process, checkpoints, recovery
    process.stop()


def wait_for_state(process: ProcessManager, timeout: float = 5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = process.read_state(safe=True)
        if state:
            return state
        time.sleep(0.1)
    raise AssertionError("Demo process did not produce state")


def test_checkpoint_creation_and_incremental_restore(rig):
    _, process, checkpoints, _ = rig
    process.start()
    state_one = wait_for_state(process)
    cp1 = checkpoints.create()
    time.sleep(1.4)
    cp2 = checkpoints.create()

    assert cp1["checkpoint_type"] == "full"
    assert cp2["checkpoint_type"] == "incremental"
    assert cp2["storage_savings"] >= 0

    restored = checkpoints.restore(cp1["id"])
    assert restored["restored_state"]["counter"] == state_one["counter"]


def test_checkpoint_validation_rejects_corruption(rig):
    _, process, checkpoints, _ = rig
    process.start()
    wait_for_state(process)
    cp = checkpoints.create()
    path = Path(cp["snapshot_path"])
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["state"]["counter"] = 999999
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = checkpoints.validate(cp["id"])
    assert result["valid"] is False
    assert "MISMATCH" in result["reason"]


def test_invalid_checkpoint_restore_fails(rig):
    _, _, checkpoints, _ = rig
    with pytest.raises(KeyError):
        checkpoints.restore(999)


def test_failure_detection_for_stopped_process(rig):
    _, process, _, _ = rig
    process.start()
    wait_for_state(process)
    process.stop(manual=False)
    failure = FailureDetector(process).detect()
    assert failure is not None
    assert failure.failure_type == "Process Crash"


def test_recovery_records_rto_and_restarts_process(rig):
    db, process, checkpoints, recovery = rig
    process.start()
    wait_for_state(process)
    cp = checkpoints.create()
    process.stop()
    failure = FailureEvent(
        failure_type="Process Crash",
        severity="CRITICAL",
        detected_at=utc_now(),
        recovery_action=f"Rollback to {cp['checkpoint_id']}",
        details="test crash",
    )
    result = recovery.recover(failure)
    history = db.rows("SELECT * FROM recovery_events")

    assert result["status"] == "SUCCESS"
    assert process.is_running()
    assert history[0]["rto"] >= 0
    assert history[0]["checkpoint_used"] == cp["checkpoint_id"]


def test_end_to_end_crash_restore_flow(rig):
    _, process, checkpoints, recovery = rig
    process.start()
    checkpoint_state = wait_for_state(process)
    cp = checkpoints.create()
    time.sleep(1.3)
    changed_state = process.read_state(safe=True)
    assert changed_state["counter"] != checkpoint_state["counter"]

    process.send_command("crash")
    time.sleep(0.8)
    failure = FailureDetector(process).detect()
    assert failure is not None

    result = recovery.recover(failure)
    restored = wait_for_state(process)
    assert result["status"] == "SUCCESS"
    assert restored["counter"] >= checkpoint_state["counter"]
    assert restored["counter"] < changed_state["counter"] + 20
