import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import psutil

from . import config
from .logger import EventLogger


class ProcessManager:
    def __init__(self, logger: EventLogger) -> None:
        self.logger = logger
        self.process: subprocess.Popen[str] | None = None
        self.started_at: float | None = None
        self.supervised = False

    def start(self, initial_state: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.is_running():
            return self.info()
        config.ensure_directories()
        self._cleanup_stale_demo_workers()
        if initial_state:
            self._write_state(initial_state)
        script = Path(__file__).resolve().parent / "demo_worker.py"
        self.process = subprocess.Popen(
            [sys.executable, str(script), str(config.PROCESS_STATE_PATH), str(config.PROCESS_COMMAND_PATH)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        self.started_at = time.time()
        self.supervised = True
        self.logger.event("INFO", "PROCESS_STARTED", f"Demo process started with PID {self.process.pid}", status="RUNNING")
        return self.info()

    def stop(self, manual: bool = True) -> dict[str, Any]:
        if manual:
            self.supervised = False
        if not self.process or self.process.poll() is not None:
            self.logger.event("WARNING", "PROCESS_STOP", "Stop requested but demo process is already stopped", status="STOPPED")
            return self.info()
        self.process.terminate()
        try:
            self.process.wait(timeout=4)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=2)
        self.logger.event("INFO", "PROCESS_STOPPED", "Demo process stopped", status="STOPPED")
        return self.info()

    def restart(self, state: dict[str, Any] | None = None) -> dict[str, Any]:
        self.stop(manual=False)
        return self.start(state)

    def send_command(self, action: str, **payload: Any) -> None:
        config.PROCESS_COMMAND_PATH.write_text(json.dumps({"action": action, **payload}), encoding="utf-8")

    def is_running(self) -> bool:
        return bool(self.process and self.process.poll() is None)

    def pid(self) -> int | None:
        return self.process.pid if self.is_running() and self.process else None

    def info(self) -> dict[str, Any]:
        status = "STOPPED"
        if self.is_running():
            status = "RUNNING"
        state = self.read_state(safe=True)
        if state and state.get("process_status") == "HUNG":
            status = "HUNG"
        return {
            "name": "crashguard-demo",
            "pid": self.pid(),
            "status": status,
            "uptime": round(time.time() - self.started_at, 2) if self.started_at else 0,
            "state": state,
        }

    def memory_mb(self) -> float:
        pid = self.pid()
        if not pid:
            return 0.0
        try:
            return psutil.Process(pid).memory_info().rss / (1024 * 1024)
        except psutil.Error:
            return 0.0

    def read_state(self, safe: bool = False) -> dict[str, Any] | None:
        try:
            payload = json.loads(config.PROCESS_STATE_PATH.read_text(encoding="utf-8"))
            return payload.get("state")
        except Exception:
            if safe:
                return None
            raise

    def _write_state(self, state: dict[str, Any]) -> None:
        from .checkpoint import state_hash

        payload = {"state": state, "state_hash": state_hash(state)}
        config.PROCESS_STATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _cleanup_stale_demo_workers(self) -> None:
        state_path = str(config.PROCESS_STATE_PATH)
        current_pid = self.pid()
        for proc in psutil.process_iter(["pid", "cmdline"]):
            try:
                if proc.info["pid"] == current_pid:
                    continue
                cmdline = proc.info.get("cmdline") or []
                joined = " ".join(cmdline)
                if "demo_worker.py" in joined and state_path in joined:
                    proc.terminate()
                    try:
                        proc.wait(timeout=2)
                    except psutil.TimeoutExpired:
                        proc.kill()
                    self.logger.event("WARNING", "STALE_PROCESS_CLEANUP", f"Terminated stale demo worker PID {proc.info['pid']}", status="CLEANED")
            except (psutil.Error, OSError):
                continue
