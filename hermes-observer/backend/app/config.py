"""Observer configuration — paths and constants."""
from pathlib import Path
import os

HERMES_HOME = Path(
    os.environ.get("HERMES_HOME", str(Path.home() / ".hermes" / "profiles" / "wx"))
).expanduser()

# Data files produced by the Hermes runtime.
INTERNAL_STATE_PATH = HERMES_HOME / "linjiang-internal-state.json"
STATE_EVENTS_PATH = HERMES_HOME / "linjiang-state-events.jsonl"
DECISION_EVENTS_PATH = HERMES_HOME / "decision-events.jsonl"
HEARTBEAT_STATE_PATH = HERMES_HOME / "proactive_heartbeat_state.json"
PROXY_REQUESTS_PATH = HERMES_HOME / "proxy-requests.jsonl"
STATE_DB_PATH = HERMES_HOME / "state.db"
STATE_TICK_LOG_PATH = HERMES_HOME / "linjiang-state-tick.log"
SOUL_PATH = HERMES_HOME / "SOUL.md"
USER_PATH = HERMES_HOME / "USER.md"
MEMORY_PATH = HERMES_HOME / "MEMORY.md"
PROACTIVE_CONTROL_PATH = HERMES_HOME / "proactive-control.json"
OBSERVER_EVENTS_PATH = HERMES_HOME / "observer-control-events.jsonl"
PROACTIVE_PROMPT_PATH = HERMES_HOME / "wx-proactive-decision-prompt.md"
PROMPT_BACKUPS_DIR = HERMES_HOME / "prompt-backups"
PRESENCE_HOME = HERMES_HOME / "presence"
PRESENCE_PROFILES_DIR = PRESENCE_HOME / "profiles"
PRESENCE_RUNTIME_DIR = PRESENCE_HOME / "runtime"
PRESENCE_EVENTS_DIR = PRESENCE_HOME / "events"
PRESENCE_KERNEL_DIR = PRESENCE_HOME / "kernel"
PRESENCE_CONFIG_BACKUPS_DIR = PRESENCE_HOME / "backups" / "config"

# Frontend build output directory (served by FastAPI as static files).
FRONTEND_DIST = Path(
    os.environ.get("OBSERVER_FRONTEND_DIST",
                   str(Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"))
)

LISTEN_HOST = os.environ.get("OBSERVER_HOST", "127.0.0.1")
LISTEN_PORT = int(os.environ.get("OBSERVER_PORT", "8790"))

# Security Configuration
ENABLE_WRITES = os.environ.get("OBSERVER_ENABLE_WRITES", "0") == "1"
ENABLE_HUMAN_FEEDBACK = os.environ.get("OBSERVER_ENABLE_HUMAN_FEEDBACK", "1") == "1"
ENABLE_PROMPT_EDIT = os.environ.get("OBSERVER_ENABLE_PROMPT_EDIT", "0") == "1"
CONTROL_TOKEN = os.environ.get("OBSERVER_CONTROL_TOKEN", "default-dev-token")
MAX_FEEDBACK_CHARS = int(os.environ.get("OBSERVER_MAX_FEEDBACK_CHARS", "300"))
MAX_PROMPT_BYTES = int(os.environ.get("OBSERVER_MAX_PROMPT_BYTES", "30000"))
