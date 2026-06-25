"""
History tracker module for DoIt (assignment section 9 & 11).
"""

import os
from collections import deque
from pathlib import Path
from typing import List


def get_history_file_path(shell: str) -> Path:
    """Return the history file path for the given shell, with environment and tilde expansion."""
    histfile = os.environ.get("HISTFILE")
    if histfile:
        expanded = os.path.expandvars(os.path.expanduser(histfile.strip()))
        return Path(expanded)
        
    return Path.home() / ".bash_history"


def load_recent_shell_history(limit: int = 15) -> List[str]:
    """
    Load the most recent manual shell commands.
    In Bash, if a DOIT_SESSION_ID is active, it reads from the session log.
    Otherwise, it falls back to the global shell history file.
    """
    shell = "bash"
    session_id = os.environ.get("DOIT_SESSION_ID")
    
    commands: List[str] = []
    
    # 1. Bash Session History
    if session_id:
        session_file = Path.home() / ".doit" / "sessions" / f"{session_id}.log"
        if session_file.exists():
            with open(session_file, "r", encoding="utf-8", errors="ignore") as f:
                # Keep at most 500 lines to preserve memory
                lines = deque(f, maxlen=500)
                for line in lines:
                    cmd = line.strip()
                    if cmd:
                        commands.append(cmd)
                
    # 2. General Shell History Fallback
    if not commands:
        hist_path = get_history_file_path(shell)
        if hist_path.exists():
            try:
                with open(hist_path, "r", encoding="utf-8", errors="ignore") as f:
                    # Keep at most 500 lines to preserve memory on large history files
                    lines = deque(f, maxlen=500)
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith("#") and not line.startswith("#!"):
                            continue
                            
                        cmd = line
                            
                        if cmd:
                            commands.append(cmd)
            except OSError:
                pass
                
    # Filter out empty commands and doit invocations
    filtered_cmds: List[str] = []
    for cmd in commands:
        cmd_clean = cmd.strip()
        if not cmd_clean:
            continue
        # Filter out doit commands
        if cmd_clean.startswith("doit ") or cmd_clean == "doit":
            continue
        filtered_cmds.append(cmd_clean)
        
    return filtered_cmds[-limit:]


def format_shell_history_for_prompt(commands: List[str]) -> str:
    """Format the list of manual shell commands for inclusion in the prompt."""
    if not commands:
        return ""
        
    lines = [
        "Recent manual shell commands executed by the user in this session (oldest first):",
    ]
    for cmd in commands:
        lines.append(f"  $ {cmd}")
    return "\n".join(lines)
