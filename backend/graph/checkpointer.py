"""File-based checkpointer for persisting LangGraph state to local JSON files."""

import json
import logging
from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver

from config import SESSIONS_DIR

logger = logging.getLogger(__name__)

# For MVP, use MemorySaver (in-memory) for the LangGraph checkpointer,
# and separately persist snapshots to JSON for frontend polling / page refresh survival.

_checkpointer: MemorySaver | None = None


def get_checkpointer() -> MemorySaver:
    """Return a singleton MemorySaver checkpointer for the LangGraph graph."""
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = MemorySaver()
    return _checkpointer


def save_session_snapshot(session_id: str, state: dict) -> None:
    """Persist a state snapshot to disk for frontend polling and page-refresh survival."""
    session_dir = Path(SESSIONS_DIR) / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    state_file = session_dir / "state.json"

    # Serialise — strip non-serialisable objects
    serialisable = {}
    for key, value in state.items():
        try:
            json.dumps(value)
            serialisable[key] = value
        except (TypeError, ValueError):
            serialisable[key] = str(value)

    state_file.write_text(json.dumps(serialisable, indent=2, default=str), encoding="utf-8")
    logger.debug(f"Saved session snapshot: {state_file}")


def load_session_state(session_id: str) -> dict | None:
    """Load the last persisted state snapshot for a session."""
    state_file = Path(SESSIONS_DIR) / session_id / "state.json"
    if not state_file.exists():
        return None
    return json.loads(state_file.read_text(encoding="utf-8"))
