"""
File Manager — Find and open any file or folder on the SSD by voice.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

log = logging.getLogger("jarvis.files")

# High-priority search locations (fast, checked first)
_USER = os.environ.get("USERPROFILE", Path.home())
QUICK_LOCATIONS: list[Path] = [
    Path(_USER) / "Desktop",
    Path(_USER) / "Downloads",
    Path(_USER) / "Documents",
    Path(_USER) / "Pictures",
    Path(_USER) / "Videos",
    Path(_USER) / "Music",
    Path(_USER) / "OneDrive",
    Path(_USER),
]

# Named folder shortcuts
FOLDER_SHORTCUTS: dict[str, Path] = {
    "desktop":   Path(_USER) / "Desktop",
    "downloads": Path(_USER) / "Downloads",
    "documents": Path(_USER) / "Documents",
    "pictures":  Path(_USER) / "Pictures",
    "photos":    Path(_USER) / "Pictures",
    "videos":    Path(_USER) / "Videos",
    "music":     Path(_USER) / "Music",
    "onedrive":  Path(_USER) / "OneDrive",
    "home":      Path(_USER),
    "c drive":   Path("C:\\"),
    "ssd":       Path("C:\\"),
    "this pc":   Path("C:\\"),
    "recycle bin": Path("shell:RecycleBinFolder"),
}


def open_folder(folder_name: str) -> tuple[bool, str]:
    """Open a well-known folder by name, or search for it on the SSD."""
    key = folder_name.lower().strip()
    if key.endswith(" folder"):
        key = key[:-7].strip()
        
    path = FOLDER_SHORTCUTS.get(key)
    if path is None:
        # Try partial match in shortcuts
        for k, v in FOLDER_SHORTCUTS.items():
            if key in k or k in key:
                path = v
                break

    if path is not None:
        try:
            subprocess.Popen(["explorer.exe", str(path)])
            return True, f"Opening {folder_name}."
        except Exception as e:
            return False, f"Could not open {folder_name}: {e}"

    # Custom folder search
    log.info("Folder shortcut not found, searching SSD for directory: %s", key)
    matches = _quick_search(key)
    folder_matches = [m for m in matches if os.path.isdir(m)]
    
    if not folder_matches:
        full_matches = _win_search(key)
        folder_matches = [m for m in full_matches if os.path.isdir(m)]
        
    if folder_matches:
        target = folder_matches[0]
        try:
            subprocess.Popen(["explorer.exe", target])
            display = Path(target).name
            return True, f"Opening folder {display}."
        except Exception as e:
            return False, f"Found folder {target} but couldn't open it: {e}"

    return False, f"I couldn't find any folder named '{folder_name}' on your computer."


def _win_search(query: str, root: str = "C:\\", timeout: int = 8) -> list[str]:
    """Use Windows 'dir /s /b' to find files. Returns list of matching paths."""
    try:
        result = subprocess.run(
            ["cmd", "/c", f'dir /s /b "{root}\\*{query}*" 2>nul'],
            capture_output=True, text=True, timeout=timeout
        )
        lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        return lines[:20]  # cap results
    except subprocess.TimeoutExpired:
        return []
    except Exception:
        return []


def _quick_search(name: str) -> list[str]:
    """Fast search in common user folders only."""
    results = []
    name_lower = name.lower()
    for loc in QUICK_LOCATIONS:
        if not loc.exists():
            continue
        try:
            for item in loc.rglob(f"*{name}*"):
                results.append(str(item))
                if len(results) >= 10:
                    return results
        except (PermissionError, OSError):
            continue
    return results


def find_and_open(name: str) -> tuple[bool, str]:
    """
    Find a file or folder by name and open it.
    Searches quick locations first, then the whole drive.
    """
    # 1. Quick search in common folders
    matches = _quick_search(name)

    # 2. If nothing found, search whole C:\
    if not matches:
        log.info("Quick search failed, searching full drive for: %s", name)
        matches = _win_search(name)

    if not matches:
        return False, f"I couldn't find any file or folder named '{name}'."

    target = matches[0]
    try:
        os.startfile(target)
        display = Path(target).name
        return True, f"Opening {display}."
    except Exception as e:
        log.warning("Could not open %s: %s", target, e)
        return False, f"Found {target} but couldn't open it: {e}"


def list_folder_contents(folder: str) -> tuple[bool, str]:
    """Tell Jarvis to verbally list what's in a folder."""
    path = FOLDER_SHORTCUTS.get(folder.lower(), Path(_USER) / "Desktop")
    if not path.exists():
        return False, f"Folder {folder} not found."
    try:
        items = list(path.iterdir())
        names = [i.name for i in items[:8]]  # max 8 items spoken
        if not names:
            return True, f"{folder} is empty."
        return True, f"In {folder}: " + ", ".join(names) + (". And more." if len(items) > 8 else ".")
    except Exception as e:
        return False, f"Could not read {folder}: {e}"
