"""
Memory — Long-term persistent memory for JARVIS.
Stores facts in ~/.jarvis_memory.json and recalls them across sessions.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path

log = logging.getLogger("jarvis.memory")

MEMORY_FILE = Path(os.environ.get("USERPROFILE", Path.home())) / ".jarvis_memory.json"

# ─── Core persistence ─────────────────────────────────────────────────────────

def _load() -> dict:
    if MEMORY_FILE.exists():
        try:
            return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("Memory load error: %s", e)
    return {}


def _save(data: dict) -> None:
    try:
        MEMORY_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        log.warning("Memory save error: %s", e)


# ─── Public API ───────────────────────────────────────────────────────────────

def remember(key: str, value: str) -> str:
    """Store a fact. Returns confirmation string."""
    data = _load()
    key = key.strip().lower()
    data[key] = {
        "value": value.strip(),
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }
    _save(data)
    log.info("Remembered: %r = %r", key, value)
    return f"Got it, sir. I'll remember that {key} is {value}."


def recall(query: str) -> str:
    """Look up a memory. Returns the spoken answer."""
    data = _load()
    query_lower = query.strip().lower()

    # Exact match
    if query_lower in data:
        return f"{query_lower} is {data[query_lower]['value']}."

    # Fuzzy: any key that contains the query words
    words = [w for w in re.split(r"\W+", query_lower) if len(w) > 2]
    for key, entry in data.items():
        if any(w in key for w in words):
            return f"I remember that {key} is {entry['value']}."

    # Search values too
    for key, entry in data.items():
        if any(w in entry["value"].lower() for w in words):
            return f"About {key}: {entry['value']}."

    return "I don't have anything stored about that, sir."


def recall_all() -> str:
    """List everything remembered."""
    data = _load()
    if not data:
        return "My memory is empty, sir. Tell me things to remember."
    parts = [f"{k}: {v['value']}" for k, v in data.items()]
    if len(parts) <= 5:
        return "Here's what I remember: " + "; ".join(parts) + "."
    return (
        f"I have {len(parts)} memories. Here are the most recent: "
        + "; ".join(parts[-5:]) + "."
    )


def forget(key: str) -> str:
    """Remove a specific memory."""
    data = _load()
    key = key.strip().lower()
    if key in data:
        del data[key]
        _save(data)
        return f"Done, I've forgotten about {key}."
    # Fuzzy
    for k in list(data.keys()):
        if key in k:
            del data[k]
            _save(data)
            return f"Done, I've forgotten about {k}."
    return f"I didn't have anything stored for {key}."


def forget_all() -> str:
    """Wipe all memories."""
    _save({})
    return "Memory cleared, sir."


def get_projects_root() -> Path:
    """Return the user's preferred projects root directory."""
    data = _load()
    for key in ["projects folder", "projects directory", "project root", "projects path"]:
        if key in data:
            p = Path(data[key]["value"])
            if p.exists():
                return p
    # Default
    default = Path(os.environ.get("USERPROFILE", Path.home())) / "Projects"
    default.mkdir(exist_ok=True)
    return default
