"""
Multi-turn history module for DoIt (assignment section 5).

Every invocation of `doit` is its own process, so to support follow-up
instructions that depend on earlier ones (e.g. "now sort them by date",
"no, i meant latest first") we persist a short conversation history to disk
and feed the most recent turns back to the model on the next invocation.

Scope note: this module intentionally covers *only* section 5. It deliberately
does NOT implement features described later in the assignment:
- per-terminal session separation (section 11, Multi-Tasking) — history is a
  single shared stream here;
- access to a previous command's stdout/stderr (section 10, Output Awareness) —
  only the instruction and the produced command/answer are stored, not output.

Design:
- History lives in a hidden ``~/.doit`` folder, in ``~/.doit/history.jsonl``.
- Each turn is one JSON object on its own line (JSONL), which makes appending
  cheap and reading robust to a partially written/corrupted last line.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from doit.session import get_session_id
from doit.config import get_config
from doit.llm import call_llm_for_history_summary


def get_history_dir() -> Path:
    """Return the hidden ~/.doit directory, creating it if needed."""
    history_dir = Path.home() / ".doit"
    history_dir.mkdir(parents=True, exist_ok=True)
    return history_dir


def _history_file() -> Path:
    """Return the JSONL history file path, using session-specific path under the sessions/ directory if session ID is present."""
    session_id = get_session_id()
    if session_id:
        sessions_dir = get_history_dir() / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        return sessions_dir / f"history_{session_id}.jsonl"
    return get_history_dir() / "history.jsonl"



def _truncate_output(text: str, max_chars: int = 2000) -> str:
    """Safely truncate large outputs to avoid bloating the history file."""
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return f"{text[:half]}\n... [TRUNCATED] ...\n{text[-half:]}"


def append_turn(
    instruction: str,
    response_type: str,
    command: str = "",
    explanation: str = "",
    answer: str = "",
    stdout: str = "",
    stderr: str = "",
    returncode: Optional[int] = None,
) -> None:
    """
    Record a single completed turn to the history file.

    Args:
        instruction: The natural-language request the user gave.
        response_type: One of "command", "answer", "not_possible", etc.
        command: The shell command generated (if any).
        explanation: The model's explanation of the command (if any).
        answer: A direct textual answer (for non-command responses).
        stdout: The captured stdout of the executed command (if any).
        stderr: The captured stderr of the executed command (if any).
        returncode: The return code of the executed command (if any).
    """
    entry: Dict[str, Any] = {
        "instruction": instruction,
        "type": response_type,
        "command": command or "",
        "explanation": explanation or "",
        "answer": answer or "",
        "stdout": _truncate_output(stdout) if stdout else "",
        "stderr": _truncate_output(stderr) if stderr else "",
        "returncode": returncode if returncode is not None else None,
    }

    try:
        with open(_history_file(), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            
        # Trigger compaction check
        compact_history_if_needed()
    except OSError as e:
        # History is best-effort: never let a write failure break the command.
        print(f"[WARNING] Could not write history: {e}")


def compact_history_if_needed() -> None:
    """
    Check if the history length exceeds the compaction threshold, and if so,
    summarize the older turns into a single summary block using the LLM.
    """
    try:
        config = get_config()
        if not config.is_history_enabled():
            return
        threshold = config.get_history_compaction_threshold()
        keep = config.get_history_compaction_keep()
    except Exception:
        # If we can't load config or it's missing the attributes, do nothing
        return

    turns = load_recent_turns(limit=10000)
    if len(turns) <= threshold:
        return

    to_summarize = turns[:-keep]
    to_keep = turns[-keep:]

    text_to_summarize = format_history_for_prompt(to_summarize)
    if not text_to_summarize:
        return

    try:
        summary_text = call_llm_for_history_summary(text_to_summarize)
    except Exception as e:
        print(f"[WARNING] Could not compact history: {e}")
        return

    new_summary_turn = {
        "type": "summary",
        "summary": summary_text
    }

    try:
        path = _history_file()
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(new_summary_turn, ensure_ascii=False) + "\n")
            for t in to_keep:
                f.write(json.dumps(t, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"[WARNING] Could not write compacted history: {e}")


def load_recent_turns(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Load the most recent turns, oldest first.

    Args:
        limit: Maximum number of recent turns to return.

    Returns:
        A list of turn dicts (possibly empty). Corrupted lines are skipped.
    """
    if limit <= 0:
        return []

    path = _history_file()
    if not path.exists():
        return []

    turns: List[Dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    turns.append(json.loads(line))
                except json.JSONDecodeError:
                    # Skip a partially written / corrupted line.
                    continue
    except OSError as e:
        print(f"[WARNING] Could not read history: {e}")
        return []

    return turns[-limit:]


def format_history_for_prompt(turns: List[Dict[str, Any]]) -> str:
    """
    Render recent turns as a compact text block to prepend to the system prompt.
    Returns an empty string when there is no history, so callers can skip
    injecting an empty block.
    """
    if not turns:
        return ""

    lines = [
        "Recent conversation history (oldest first, most recent last). The "
        "user's new instruction may be a follow-up that refers to a previous "
        "turn (e.g. \"now sort them\", \"no, latest first\", \"undo that\"). "
        "Use this context to resolve such references. If the new instruction "
        "is unrelated, ignore the history.",
        "",
    ]

    for i, turn in enumerate(turns, start=1):
        turn_type = turn.get("type")
        
        if turn_type == "summary":
            lines.append(f"Turn {i} (Compacted History):")
            lines.append(f"  Summary of earlier conversation: {turn.get('summary', '').strip()}")
        else:
            lines.append(f"Turn {i}:")
            lines.append(f"  User said: {turn.get('instruction', '').strip()}")

            if turn_type == "command" and turn.get("command"):
                lines.append(f"  Command produced: {turn['command'].strip()}")
                
                # Include return code if available
                if turn.get("returncode") is not None:
                    lines.append(f"  Return code: {turn['returncode']}")
                
                # Include stdout and stderr if available
                stdout = turn.get("stdout", "").strip()
                if stdout:
                    lines.append("  Standard Output:")
                    # Indent stdout for readability
                    lines.extend([f"    {line}" for line in stdout.split('\n')])
                    
                stderr = turn.get("stderr", "").strip()
                if stderr:
                    lines.append("  Standard Error:")
                    lines.extend([f"    {line}" for line in stderr.split('\n')])

            elif turn.get("answer"):
                lines.append(f"  Assistant answered: {turn['answer'].strip()}")
            elif turn.get("explanation"):
                lines.append(f"  Assistant said: {turn['explanation'].strip()}")

        lines.append("")

    return "\n".join(lines).strip()


def clear_history() -> bool:
    """
    Delete the history file.

    Returns True if a file was removed, False if there was nothing to clear.
    """
    path = _history_file()
    if path.exists():
        try:
            path.unlink()
            return True
        except OSError as e:
            print(f"[WARNING] Could not clear history: {e}")
    return False
