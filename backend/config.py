import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CHECKPOINT_DIR = BASE_DIR / "checkpoints"
SNAPSHOT_DIR = CHECKPOINT_DIR / "snapshots"
METADATA_DIR = CHECKPOINT_DIR / "metadata"
LOG_DIR = BASE_DIR / "logs"
FRONTEND_DIR = BASE_DIR / "frontend"

DB_PATH = DATA_DIR / "crashguard.db"
PROCESS_STATE_PATH = DATA_DIR / "demo_state.json"
PROCESS_COMMAND_PATH = DATA_DIR / "demo_command.json"

MONITOR_INTERVAL_SECONDS = 2.0
HEARTBEAT_TIMEOUT_SECONDS = 6.0
CPU_THRESHOLD_PERCENT = 90.0
MEMORY_THRESHOLD_MB = 350.0
MAX_MEMORY_STRESS_MB = 120

DEFAULT_POLICY = "latest"
VALID_POLICIES = {"latest", "safest", "manual", "automatic"}
PORT = int(os.environ.get("PORT", 8080))


def ensure_directories() -> None:
    for path in [DATA_DIR, SNAPSHOT_DIR, METADATA_DIR, LOG_DIR]:
        path.mkdir(parents=True, exist_ok=True)
