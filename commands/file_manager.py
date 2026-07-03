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


def create_folder(folder_name: str, location: str = "") -> tuple[bool, str]:
    """Create a folder at the resolved location."""
    fn_lower = folder_name.strip().lower()
    if not location and (fn_lower.startswith("in ") or fn_lower.startswith("at ")):
        parts = folder_name.strip().split(None, 1)
        if len(parts) == 2:
            location = parts[1]
            folder_name = "New Folder"

    target_dir = _resolve_location(location)
    folder_path = target_dir / folder_name
    try:
        folder_path.mkdir(parents=True, exist_ok=True)
        return True, f"Folder '{folder_name}' has been created at {target_dir}."
    except Exception as e:
        return False, f"Could not create folder {folder_name}: {e}"



def delete_file_with_confirmation(filename: str, update_hud_fn=None) -> tuple[bool, str]:
    """Delete a file from Desktop/Downloads with GUI confirmation dialog."""
    q = filename.lower().strip()
    desktop = Path(os.environ.get("USERPROFILE", Path.home())) / "Desktop"
    downloads = Path(os.environ.get("USERPROFILE", Path.home())) / "Downloads"
    
    candidates = [desktop / filename, downloads / filename]
    
    target_path = None
    for cand in candidates:
        if cand.exists() and cand.is_file():
            target_path = cand
            break
            
    if target_path is None:
        matches = _quick_search(filename)
        if matches:
            target_path = Path(matches[0])
            
    if target_path is None or not target_path.exists():
        return False, f"I couldn't find any file named '{filename}' to delete."
        
    confirmed = True
    if update_hud_fn:
        import queue
        res_queue = queue.Queue()
        update_hud_fn("ASK_CONFIRMATION", (f"Are you sure you want to delete {target_path.name}?", res_queue))
        try:
            confirmed = res_queue.get(timeout=10.0)
        except queue.Empty:
            confirmed = False
    else:
        import tkinter.messagebox as mbox
        confirmed = mbox.askyesno("Confirm Delete", f"Delete file {target_path.name}?")
        
    if confirmed:
        try:
            target_path.unlink()
            return True, f"File {target_path.name} has been deleted."
        except Exception as e:
            return False, f"Failed to delete file: {e}"
    else:
        return True, "Deletion cancelled."


def rename_file(old_name: str, new_name: str) -> tuple[bool, str]:
    """Rename a file in Desktop or Downloads."""
    desktop = Path(os.environ.get("USERPROFILE", Path.home())) / "Desktop"
    downloads = Path(os.environ.get("USERPROFILE", Path.home())) / "Downloads"
    
    target_path = None
    for folder in [desktop, downloads]:
        path = folder / old_name
        if path.exists():
            target_path = path
            break
            
    if target_path is None:
        matches = _quick_search(old_name)
        if matches:
            target_path = Path(matches[0])
            
    if target_path is None or not target_path.exists():
        return False, f"Could not find the file '{old_name}' to rename."
        
    try:
        new_path = target_path.parent / new_name
        target_path.rename(new_path)
        return True, f"Renamed {target_path.name} to {new_name}."
    except Exception as e:
        return False, f"Failed to rename file: {e}"


def move_file(file_name: str, target_folder: str) -> tuple[bool, str]:
    """Move a file to a folder."""
    desktop = Path(os.environ.get("USERPROFILE", Path.home())) / "Desktop"
    downloads = Path(os.environ.get("USERPROFILE", Path.home())) / "Downloads"
    
    src_path = None
    for folder in [desktop, downloads]:
        path = folder / file_name
        if path.exists():
            src_path = path
            break
    if src_path is None:
        matches = _quick_search(file_name)
        if matches:
            src_path = Path(matches[0])
            
    if src_path is None or not src_path.exists():
        return False, f"Could not find file '{file_name}' to move."
        
    dest_path = None
    folder_key = target_folder.lower().strip()
    if folder_key in FOLDER_SHORTCUTS:
        dest_path = FOLDER_SHORTCUTS[folder_key]
    else:
        path = desktop / target_folder
        if path.exists() and path.is_dir():
            dest_path = path
        else:
            try:
                path.mkdir(parents=True, exist_ok=True)
                dest_path = path
            except Exception:
                pass
                
    if dest_path is None:
        return False, f"Could not resolve destination folder '{target_folder}'."
        
    try:
        import shutil
        shutil.move(str(src_path), str(dest_path / src_path.name))
        return True, f"Moved {src_path.name} to {target_folder}."
    except Exception as e:
        return False, f"Failed to move file: {e}"


# ─── Persistent last-created file path ────────────────────────────────────────

_last_created_file: Path | None = None


def _resolve_location(location: str) -> Path:
    """Resolve a user-provided location string to an absolute Path."""
    if not location:
        # Default to Desktop
        return Path(os.environ.get("USERPROFILE", Path.home())) / "Desktop"

    loc = location.strip()

    # Check if it's already an absolute Windows path (e.g. C:\Users\...)
    try:
        p = Path(loc)
        if p.is_absolute():
            p.mkdir(parents=True, exist_ok=True)
            return p
    except Exception:
        pass

    # Map friendly names
    shortcuts_extended = dict(FOLDER_SHORTCUTS)
    shortcuts_extended.update({
        "here": Path(os.environ.get("USERPROFILE", Path.home())) / "Desktop",
        "projects": Path(os.environ.get("USERPROFILE", Path.home())) / "Projects",
        "temp": Path(os.environ.get("TEMP", "C:\\Temp")),
        "c drive": Path("C:\\"),
        "d drive": Path("D:\\"),
        "e drive": Path("E:\\"),
    })

    key = loc.lower()
    for short, path in shortcuts_extended.items():
        if key == short or key in short or short in key:
            path.mkdir(parents=True, exist_ok=True)
            return path

    # Try to resolve as a sub-path under USERPROFILE
    fallback = Path(os.environ.get("USERPROFILE", Path.home())) / loc
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def create_file(filename: str, location: str = "", content: str = "") -> tuple[bool, str]:
    """
    Create a file at the given location.
    Saves the path in memory for subsequent 'write code' commands.
    """
    global _last_created_file

    # Clean up filename — strip surrounding quotes if any
    filename = filename.strip().strip("'\"")
    if not filename:
        return False, "No filename provided."

    target_dir = _resolve_location(location)
    file_path = target_dir / filename

    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        _last_created_file = file_path
        # Also save to long-term memory for this session
        try:
            from commands.memory import remember
            remember("last created file", str(file_path))
        except Exception:
            pass
        log.info("Created file: %s", file_path)
        return True, f"Created file {filename} at {target_dir}."
    except Exception as e:
        log.error("Failed to create file %s: %s", filename, e)
        return False, f"Could not create file {filename}: {e}"


def write_code_to_last_file(description: str) -> tuple[bool, str]:
    """
    Generate code using the AI brain and write it to the last created file.
    Then open the file in VS Code.
    """
    global _last_created_file

    # Resolve last created file
    if _last_created_file is None:
        try:
            from commands.memory import recall
            mem = recall("last created file")
            if mem and "is" in mem and "don't" not in mem:
                val = mem.split(" is ", 1)[-1].rstrip(".")
                p = Path(val)
                if p.exists() and p.is_file():
                    _last_created_file = p
        except Exception:
            pass

    # Fallback to main.py in current workspace or Desktop if no valid file is active
    if _last_created_file is None or not _last_created_file.suffix or _last_created_file.is_dir():
        default_dir = Path("c:/Users/likith/Downloads/jarvis-main/jarvis-main")
        if not default_dir.exists():
            default_dir = Path(os.environ.get("USERPROFILE", Path.home())) / "Desktop"
        _last_created_file = default_dir / "main.py"

    file_path = _last_created_file

    # Build the prompt
    ext = file_path.suffix.lower()
    lang_hint = {
        ".py": "Write clean Python 3.10+ code with proper error handling and docstrings.",
        ".js": "Write modern vanilla JavaScript (ES2022+), no frameworks.",
        ".html": "Write complete, modern HTML5 with embedded CSS and JavaScript.",
        ".css": "Write modern CSS3 with variables and responsive design.",
        ".ts": "Write TypeScript with proper types.",
        ".java": "Write Java 17+ with proper class structure.",
        ".cpp": "Write modern C++ with proper headers.",
        ".sh": "Write a bash shell script.",
        ".bat": "Write a Windows batch script.",
    }.get(ext, "Write clean, well-commented code.")

    prompt = (
        f"Generate complete, working code for a file named '{file_path.name}'. "
        f"Task/Description: {description}. "
        f"{lang_hint} "
        f"Output ONLY the raw file content, no explanations, no markdown code fences, no backticks."
    )

    # Generate code
    try:
        from commands.coding_agent import _generate_code
        code = _generate_code(prompt)
    except Exception as e:
        log.warning("Code generation failed: %s", e)
        code = f"# Could not generate code automatically.\n# Description: {description}\n"

    # Write to file
    try:
        file_path.write_text(code, encoding="utf-8")
        log.info("Wrote code to: %s", file_path)
    except Exception as e:
        return False, f"Could not write code to {file_path.name}: {e}"

    # Open in VS Code
    try:
        from commands.coding_agent import _open_in_vscode
        _open_in_vscode(file_path)
    except Exception:
        pass

    return True, f"Code written to {file_path.name} and opened in VS Code."

