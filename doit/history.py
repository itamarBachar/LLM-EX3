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
from typing import Any, Dict, List


def get_history_dir() -> Path:
    """Return the hidden ~/.doit directory, creating it if needed."""
    history_dir = Path.home() / ".doit"
    history_dir.mkdir(parents=True, exist_ok=True)
    return history_dir


def _history_file() -> Path:
    """Return the single JSONL history file path."""
    return get_history_dir() / "history.jsonl"


def append_turn(
    instruction: str,
    response_type: str,
    command: str = "",
    explanation: str = "",
    answer: str = "",
) -> None:
    """
    Record a single completed turn to the history file.

    Args:
        instruction: The natural-language request the user gave.
        response_type: One of "command", "answer", "not_possible", etc.
        command: The shell command generated (if any).
        explanation: The model's explanation of the command (if any).
        answer: A direct textual answer (for non-command responses).
    """
    entry: Dict[str, Any] = {
        "instruction": instruction,
        "type": response_type,
        "command": command or "",
        "explanation": explanation or "",
        "answer": answer or "",
    }

    try:
        with open(_history_file(), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as e:
        # History is best-effort: never let a write failure break the command.
        print(f"[WARNING] Could not write history: {e}")


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

    Only the user's instruction and the produced command/answer are included —
    not command output (that is section 10's concern). Returns an empty string
    when there is no history, so callers can skip injecting an empty block.
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
        lines.append(f"Turn {i}:")
        lines.append(f"  User said: {turn.get('instruction', '').strip()}")

        turn_type = turn.get("type")
        if turn_type == "command" and turn.get("command"):
            lines.append(f"  Command produced: {turn['command'].strip()}")
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
