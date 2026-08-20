import logging
from logging.handlers import RotatingFileHandler

from . import config
from .database import Database
from .models import utc_now


class EventLogger:
    def __init__(self, db: Database) -> None:
        config.ensure_directories()
        self.db = db
        self.logger = logging.getLogger("crashguard")
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = RotatingFileHandler(
                config.LOG_DIR / "crashguard.log",
                maxBytes=750_000,
                backupCount=3,
                encoding="utf-8",
            )
            handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)-5s %(message)s", "%H:%M:%S"))
            self.logger.addHandler(handler)

    def event(
        self,
        level: str,
        event_type: str,
        message: str,
        checkpoint_id: str | None = None,
        status: str | None = None,
    ) -> None:
        level_name = level.upper()
        getattr(self.logger, level_name.lower(), self.logger.info)(message)
        try:
            self.db.execute(
                """
                INSERT INTO system_events(timestamp, level, event_type, message, checkpoint_id, status)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (utc_now(), level_name, event_type, message, checkpoint_id, status),
            )
        except Exception:
            self.logger.exception("Failed to write event to SQLite")
