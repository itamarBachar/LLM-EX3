"""
Persistent memory module for DoIt (assignment section 8).

Memories are facts about the user or their system that persist across
terminal windows, directories, and sessions. They are stored in
`~/.doit/memories.json` as a JSON array of strings.
"""

import json
from pathlib import Path
from typing import List


def get_memory_file() -> Path:
    """Return the path to the memories file."""
    memory_dir = Path.home() / ".doit"
    memory_dir.mkdir(parents=True, exist_ok=True)
    return memory_dir / "memories.json"


def load_memories() -> List[str]:
    """Load the persistent memories as a list of strings."""
    path = get_memory_file()
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return [str(item).strip() for item in data if str(item).strip()]
    except Exception as e:
        print(f"[WARNING] Could not read memories: {e}")
    return []


def save_memories(memories: List[str]) -> None:
    """Save the list of memories to the persistent file."""
    path = get_memory_file()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(memories, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"[WARNING] Could not write memories: {e}")


def update_memories(new_memories: List[str], forget_memories: List[str]) -> None:
    """Add new memories and remove old ones."""
    memories = load_memories()
    
    # 1. Forget memories
    if forget_memories:
        normalized_forget = [f.strip().lower().rstrip('.') for f in forget_memories]
        updated = []
        for m in memories:
            m_norm = m.strip().lower().rstrip('.')
            should_forget = False
            for f in normalized_forget:
                if f == m_norm or f in m_norm or m_norm in f:
                    should_forget = True
                    break
            if not should_forget:
                updated.append(m)
        memories = updated

    # 2. Add new memories
    if new_memories:
        for new_m in new_memories:
            new_m_clean = new_m.strip()
            if not new_m_clean:
                continue
            new_m_norm = new_m_clean.lower().rstrip('.')
            duplicate = False
            for m in memories:
                if m.lower().rstrip('.') == new_m_norm:
                    duplicate = True
                    break
            if not duplicate:
                memories.append(new_m_clean)
                
    save_memories(memories)


def clear_memories() -> bool:
    """Delete the memories file."""
    path = get_memory_file()
    if path.exists():
        try:
            path.unlink()
            return True
        except OSError as e:
            print(f"[WARNING] Could not clear memories: {e}")
    return False


def format_memories_for_prompt(memories: List[str]) -> str:
    """Format the list of memories for inclusion in the system prompt."""
    if not memories:
        return ""
    
    lines = [
        "Persistent memories about the user/system (loaded from memory file):",
    ]
    for m in memories:
        lines.append(f"- {m}")
    return "\n".join(lines)
