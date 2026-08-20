import hashlib
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Any


TASKS = ["Data Processing", "Index Rebuild", "Batch Encoding", "Transaction Replay"]


def hash_state(state: dict[str, Any]) -> str:
    payload = json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


def read_command(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        command = json.loads(path.read_text(encoding="utf-8"))
        path.unlink(missing_ok=True)
        return command
    except Exception:
        return None


def load_initial_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "counter": 0,
            "current_task": TASKS[0],
            "progress": 0,
            "current_item": 1000,
            "memory_state": {"working_set": [], "notes": "clean"},
            "process_status": "RUNNING",
            "timestamp": "",
            "heartbeat": time.time(),
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload.get("state", payload)
    except Exception:
        return load_initial_state(Path("__missing__"))


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: demo_worker.py STATE_PATH COMMAND_PATH", file=sys.stderr)
        return 2

    state_path = Path(sys.argv[1])
    command_path = Path(sys.argv[2])
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state = load_initial_state(state_path)
    memory_stress: list[bytes] = []
    hung = False

    while True:
        command = read_command(command_path)
        if command:
            action = command.get("action")
            if action == "crash":
                os._exit(7)
            if action == "hang":
                hung = True
                state["process_status"] = "HUNG"
            if action == "corrupt":
                write_json_atomic(state_path, {"state": {"counter": "CORRUPTED", "progress": 999}, "state_hash": "bad"})
                continue
            if action == "memory_stress":
                mb = int(command.get("megabytes", 40))
                memory_stress = [b"x" * 1024 * 1024 for _ in range(max(1, mb))]
                state["memory_state"]["stress_mb"] = mb
            if action == "restore":
                state = command.get("state", state)
                hung = False
                memory_stress = []

        if hung:
            time.sleep(1)
            continue

        state["counter"] = int(state.get("counter", 0)) + random.randint(1, 7)
        state["progress"] = (int(state.get("progress", 0)) + random.randint(1, 4)) % 101
        state["current_item"] = int(state.get("current_item", 1000)) + 1
        if state["progress"] < 5:
            state["current_task"] = random.choice(TASKS)
        state["memory_state"]["working_set"] = list(range(state["counter"] % 12))
        state["process_status"] = "RUNNING"
        state["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        state["heartbeat"] = time.time()
        payload = {"state": state, "state_hash": hash_state(state)}
        write_json_atomic(state_path, payload)
        time.sleep(1)


if __name__ == "__main__":
    raise SystemExit(main())
