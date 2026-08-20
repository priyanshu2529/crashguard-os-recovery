import random

from . import config
from .logger import EventLogger
from .process_manager import ProcessManager


class FailureSimulator:
    def __init__(self, process_manager: ProcessManager, logger: EventLogger) -> None:
        self.process_manager = process_manager
        self.logger = logger

    def crash(self) -> dict[str, str]:
        self._require_process()
        self.process_manager.send_command("crash")
        self.logger.event("ERROR", "SIMULATED_CRASH", "Simulated process crash requested", status="TRIGGERED")
        return {"status": "triggered", "failure": "Process Crash"}

    def hang(self) -> dict[str, str]:
        self._require_process()
        self.process_manager.send_command("hang")
        self.logger.event("WARNING", "SIMULATED_HANG", "Simulated process hang requested", status="TRIGGERED")
        return {"status": "triggered", "failure": "Process Hang"}

    def corrupt(self) -> dict[str, str]:
        self._require_process()
        self.process_manager.send_command("corrupt")
        self.logger.event("ERROR", "SIMULATED_CORRUPTION", "Simulated state corruption requested", status="TRIGGERED")
        return {"status": "triggered", "failure": "State Corruption"}

    def memory_stress(self, megabytes: int = 60) -> dict[str, str | int]:
        self._require_process()
        mb = min(max(1, megabytes), config.MAX_MEMORY_STRESS_MB)
        self.process_manager.send_command("memory_stress", megabytes=mb)
        self.logger.event("WARNING", "SIMULATED_MEMORY_STRESS", f"Memory stress requested: {mb} MB", status="TRIGGERED")
        return {"status": "triggered", "failure": "Memory Stress", "megabytes": mb}

    def random(self) -> dict[str, str | int]:
        return random.choice([self.crash, self.hang, self.corrupt, self.memory_stress])()

    def _require_process(self) -> None:
        if not self.process_manager.is_running():
            raise RuntimeError("Demo process is not running")
