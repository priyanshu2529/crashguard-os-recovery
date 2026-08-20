import asyncio

from . import config
from .failure_detector import FailureDetector
from .logger import EventLogger
from .recovery import RecoveryEngine


class SystemMonitor:
    def __init__(self, detector: FailureDetector, recovery: RecoveryEngine, logger: EventLogger) -> None:
        self.detector = detector
        self.recovery = recovery
        self.logger = logger
        self._task: asyncio.Task | None = None
        self._last_failure_key: str | None = None

    def start(self) -> None:
        if not self._task:
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        while True:
            failure = self.detector.detect()
            if failure:
                key = f"{failure.failure_type}:{failure.details}"
                if key != self._last_failure_key:
                    self._last_failure_key = key
                    self.logger.event("ERROR", "FAILURE_DETECTED", f"{failure.failure_type} detected: {failure.details}", status=failure.severity)
                    if self.recovery.get_policy() != "manual":
                        self.recovery.recover(failure)
            else:
                self._last_failure_key = None
            await asyncio.sleep(config.MONITOR_INTERVAL_SECONDS)
