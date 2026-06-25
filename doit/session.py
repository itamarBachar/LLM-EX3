"""
Session management module for Bash session isolation (assignment section 11).
"""

import os
from pathlib import Path
from typing import Optional


def get_session_id() -> Optional[str]:
    """Get the active DOIT_SESSION_ID if set."""
    return os.environ.get("DOIT_SESSION_ID")


def get_session_log_path(session_id: str) -> Path:
    """Return the path to the log file for the given session ID."""
    session_dir = Path.home() / ".doit" / "sessions"
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir / f"{session_id}.log"


def clear_session_history(session_id: str) -> bool:
    """Delete the session log file."""
    path = get_session_log_path(session_id)
    if path.exists():
        path.unlink()
        return True
    return False
