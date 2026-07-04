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


def _win_search(query: str, root: str = "C:\\", timeout: int = 4) -> list[str]:
    """Query the Windows Search Indexer via PowerShell — returns results in ~1 second."""
    clean_query = query.replace("'", "''")
    ps_cmd = (
        f"$conn = New-Object -ComObject ADODB.Connection; "
        f"$conn.Open('Provider=Search.CollatorDSO;Extended Properties=\"Application=Windows\";'); "
        f"$rs = New-Object -ComObject ADODB.Recordset; "
        f"$q = \"SELECT TOP 20 System.ItemPathDisplay FROM SystemIndex "
        f"WHERE System.ItemNameDisplay LIKE '%{clean_query}%'\"; "
        f"try {{ $rs.Open($q, $conn); "
        f"while (-not $rs.EOF) {{ "
        f"Write-Output $rs.Fields.Item('System.ItemPathDisplay').Value; "
        f"$rs.MoveNext() }} }} catch {{}}"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=timeout
        )
        paths = [
            line.strip() for line in result.stdout.splitlines()
            if line.strip() and os.path.exists(line.strip())
        ]
        if paths:
            log.info("Indexer found %d matches for '%s'", len(paths), query)
            return paths[:20]
    except Exception as e:
        log.warning("Indexer search failed (%s)", e)
    return []


def _quick_search(name: str, max_depth: int = 2) -> list[str]:
    """Shallow 2-level scan of common user folders — typically completes in <0.5 seconds."""
    results: list[str] = []
    pattern = name.lower()

    def _scan_dir(folder: Path, depth: int) -> None:
        if depth > max_depth or len(results) >= 10:
            return
        try:
            for item in folder.iterdir():
                if len(results) >= 10:
                    return
                if pattern in item.name.lower():
                    results.append(str(item))
                if item.is_dir() and not item.name.startswith('.'):
                    _scan_dir(item, depth + 1)
        except (PermissionError, OSError):
            pass

    for loc in QUICK_LOCATIONS:
        if loc.exists():
            _scan_dir(loc, 0)
        if len(results) >= 10:
            break
    return results


def find_and_open(name: str) -> tuple[bool, str]:
    """
    Find a file or folder by name and open it.
    Strips noise words, searches quick locations first, then the whole drive.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Strip common noise words that aren't part of a filename
    _NOISE = {"song", "file", "video", "document", "photo", "picture", "folder",
              "directory", "music", "movie", "clip", "audio", "track", "image"}
    name = name.strip().strip("'\"")
    words = [w for w in name.lower().split() if w not in _NOISE]

    queries_to_try = [name]  # always try full name first
    cleaned = " ".join(words).strip()
    if cleaned and cleaned != name.lower():
        queries_to_try.append(cleaned)
    for w in words:
        if len(w) > 2 and w not in queries_to_try:
            queries_to_try.append(w)

    def _parallel_search(query: str) -> list[str]:
        """Run quick_search + win_search in parallel, return first non-empty result."""
        results: list[str] = []
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                executor.submit(_quick_search, query): "quick",
                executor.submit(_win_search, query): "indexer",
            }
            for future in as_completed(futures, timeout=5):
                try:
                    res = future.result()
                    if res:
                        results.extend(res)
                        break  # take first result that comes back
                except Exception:
                    pass
        return results

    matches: list[str] = []
    for q in queries_to_try:
        log.info("Searching for: '%s'", q)
        matches = _parallel_search(q)
        if matches:
            break

    if not matches:
        return False, f"I couldn't find any file or folder named '{name}', sir."

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



def delete_file_with_confirmation(filename: str, location: str = "", update_hud_fn=None) -> tuple[bool, str]:
    """Delete a file or folder from Desktop/Downloads (or specified location) with verification."""
    filename = filename.strip().strip("'\"")
    if not filename:
        return False, "No file or folder name specified."

    target_path = None

    # 1. If location is specified, search only in that location
    if location:
        target_dir = _resolve_location(location)
        cand = target_dir / filename
        if cand.exists():
            target_path = cand
        else:
            # Try a quick search within target_dir
            try:
                for item in target_dir.rglob(f"*{filename}*"):
                    target_path = item
                    break
            except Exception:
                pass
    else:
        # 2. No location: search Desktop and Downloads
        desktop = Path(os.environ.get("USERPROFILE", Path.home())) / "Desktop"
        downloads = Path(os.environ.get("USERPROFILE", Path.home())) / "Downloads"
        candidates = [desktop / filename, downloads / filename]
        for cand in candidates:
            if cand.exists():
                target_path = cand
                break
        if target_path is None:
            matches = _quick_search(filename)
            if matches:
                target_path = Path(matches[0])

    if target_path is None or not target_path.exists():
        loc_str = f" in '{location}'" if location else ""
        return False, f"I couldn't find any file or folder named '{filename}'{loc_str}."

    confirmed = True
    item_type = "folder" if target_path.is_dir() else "file"
    if update_hud_fn:
        import queue
        res_queue = queue.Queue()
        update_hud_fn("ASK_CONFIRMATION", (f"Are you sure you want to delete {item_type} '{target_path.name}'?", res_queue))
        try:
            confirmed = res_queue.get(timeout=10.0)
        except queue.Empty:
            confirmed = False
    else:
        import tkinter.messagebox as mbox
        confirmed = mbox.askyesno("Confirm Delete", f"Delete {item_type} '{target_path.name}'?")

    if confirmed:
        try:
            if target_path.is_dir():
                import shutil
                shutil.rmtree(target_path)
                return True, f"Folder {target_path.name} has been deleted."
            else:
                target_path.unlink()
                return True, f"File {target_path.name} has been deleted."
        except Exception as e:
            return False, f"Failed to delete {item_type}: {e}"
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

    # Resolve language specific extension from the description
    desc_l = description.lower()
    detected_name = None
    if "java" in desc_l:
        detected_name = "Main.java"
    elif "cpp" in desc_l or "c++" in desc_l:
        detected_name = "main.cpp"
    elif " c " in f" {desc_l} " or " c code" in desc_l or " c program" in desc_l:
        detected_name = "main.c"
    elif "javascript" in desc_l or " js" in desc_l or "node" in desc_l:
        detected_name = "main.js"
    elif "html" in desc_l:
        detected_name = "index.html"
    elif "css" in desc_l:
        detected_name = "style.css"
    elif "batch" in desc_l or " bat" in desc_l:
        detected_name = "run.bat"
    elif "shell" in desc_l or "bash" in desc_l:
        detected_name = "script.sh"

    default_dir = Path("c:/Users/likith/Downloads/jarvis-main/jarvis-main")
    if not default_dir.exists():
        default_dir = Path(os.environ.get("USERPROFILE", Path.home())) / "Desktop"

    # If the user explicitly specified a language, override the last file to match it
    if detected_name:
        file_path = default_dir / detected_name
        _last_created_file = file_path
    else:
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

        if _last_created_file is None or not _last_created_file.suffix or _last_created_file.is_dir():
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
        ".java": "Write Java 17+ with proper class structure and a public class Main.",
        ".cpp": "Write modern C++ with proper headers.",
        ".c": "Write clean C99 code with stdio.h, proper headers and a main function.",
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

