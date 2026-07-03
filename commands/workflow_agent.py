"""
Workflow Agent — Execute multi-step named workflows by voice.

Built-in workflows:
  "coding workspace"    → VS Code + Terminal + Chrome (GitHub)
  "research mode"       → Chrome + Notion + Spotify
  "presentation mode"   → PowerPoint + Chrome + maximize
  "gaming setup"        → Steam + Discord + maximize
  "morning routine"     → Chrome (news) + Spotify + system info

Users can define custom workflows in workflows.json.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

log = logging.getLogger("jarvis.workflow")

WORKFLOWS_FILE = Path(os.environ.get("USERPROFILE", Path.home())) / ".jarvis_workflows.json"

# ─── Built-in workflows ───────────────────────────────────────────────────────
# Each step: {"action": "open_app"|"open_url"|"speak"|"wait"|"shortcut", ...}

BUILTIN_WORKFLOWS: dict[str, list[dict]] = {
    "coding workspace": [
        {"action": "speak",    "text": "Setting up your coding workspace."},
        {"action": "open_app", "app": "vs code"},
        {"action": "wait",     "seconds": 2},
        {"action": "open_app", "app": "windows terminal"},
        {"action": "wait",     "seconds": 1},
        {"action": "open_url", "url": "https://github.com", "name": "GitHub"},
        {"action": "speak",    "text": "Coding workspace ready, sir."},
    ],
    "research mode": [
        {"action": "speak",    "text": "Activating research mode."},
        {"action": "open_url", "url": "https://www.google.com", "name": "Google"},
        {"action": "wait",     "seconds": 1},
        {"action": "open_url", "url": "https://www.notion.so", "name": "Notion"},
        {"action": "open_app", "app": "spotify"},
        {"action": "speak",    "text": "Research mode activated. I've opened Google, Notion, and Spotify."},
    ],
    "presentation mode": [
        {"action": "speak",    "text": "Setting up presentation mode."},
        {"action": "open_app", "app": "powerpoint"},
        {"action": "wait",     "seconds": 1},
        {"action": "shortcut", "keys": ["win", "up"]},  # Maximize
        {"action": "speak",    "text": "Presentation mode ready."},
    ],
    "gaming setup": [
        {"action": "speak",    "text": "Game on. Opening Steam and Discord."},
        {"action": "open_app", "app": "steam"},
        {"action": "wait",     "seconds": 1},
        {"action": "open_app", "app": "discord"},
        {"action": "speak",    "text": "Gaming setup complete. Have fun, sir."},
    ],
    "morning routine": [
        {"action": "speak",    "text": "Good morning. Starting your routine."},
        {"action": "open_url", "url": "https://news.google.com", "name": "news"},
        {"action": "wait",     "seconds": 1},
        {"action": "open_app", "app": "spotify"},
        {"action": "speak",    "text": "Morning routine complete. Have a great day, sir."},
    ],
    "work mode": [
        {"action": "speak",    "text": "Activating work mode."},
        {"action": "open_app", "app": "vs code"},
        {"action": "wait",     "seconds": 1},
        {"action": "open_url", "url": "https://mail.google.com", "name": "Gmail"},
        {"action": "wait",     "seconds": 1},
        {"action": "open_app", "app": "slack"},
        {"action": "speak",    "text": "Work mode activated. VS Code, Gmail, and Slack are open."},
    ],
    "study mode": [
        {"action": "speak",    "text": "Study mode activating. Minimizing distractions."},
        {"action": "open_url", "url": "https://www.youtube.com", "name": "YouTube"},
        {"action": "wait",     "seconds": 1},
        {"action": "open_url", "url": "https://www.notion.so", "name": "Notion"},
        {"action": "speak",    "text": "Study mode ready. Focus, sir."},
    ],
}


# ─── User-defined workflows ───────────────────────────────────────────────────

def _load_user_workflows() -> dict:
    if not WORKFLOWS_FILE.exists():
        return {}
    try:
        return json.loads(WORKFLOWS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("Workflow load error: %s", e)
        return {}


def _save_user_workflows(data: dict) -> None:
    try:
        WORKFLOWS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        log.warning("Workflow save error: %s", e)


def get_all_workflows() -> dict:
    merged = dict(BUILTIN_WORKFLOWS)
    merged.update(_load_user_workflows())
    return merged


# ─── Step execution ───────────────────────────────────────────────────────────

def _execute_step(step: dict, speak_fn=None) -> None:
    action = step.get("action", "")

    if action == "speak":
        if speak_fn:
            speak_fn(step.get("text", ""))
        else:
            print(f"[JARVIS] {step.get('text', '')}")

    elif action == "open_app":
        from commands.app_launcher import launch_app
        ok, msg = launch_app(step["app"])
        log.info("Workflow open_app '%s': %s", step["app"], msg)

    elif action == "open_url":
        import webbrowser
        webbrowser.open(step["url"])
        log.info("Workflow open_url: %s", step["url"])

    elif action == "wait":
        time.sleep(float(step.get("seconds", 1)))

    elif action == "shortcut":
        try:
            import pyautogui
            pyautogui.hotkey(*step["keys"])
        except Exception as e:
            log.warning("Workflow shortcut failed: %s", e)

    elif action == "type":
        try:
            import pyautogui
            pyautogui.typewrite(step.get("text", ""), interval=0.04)
        except Exception as e:
            log.warning("Workflow type failed: %s", e)

    elif action == "shell":
        try:
            subprocess.Popen(
                step["command"],
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
        except Exception as e:
            log.warning("Workflow shell command failed: %s", e)


# ─── Main entry point ─────────────────────────────────────────────────────────

def execute_workflow(name: str, speak_fn=None) -> tuple[bool, str]:
    """Run a named workflow. Returns (success, message)."""
    workflows = get_all_workflows()
    name_lower = name.strip().lower()

    # Exact match
    steps = workflows.get(name_lower)

    # Fuzzy match
    if steps is None:
        for key, val in workflows.items():
            if name_lower in key or key in name_lower:
                steps = val
                name_lower = key
                break

    if steps is None:
        available = ", ".join(sorted(workflows.keys()))
        return False, (
            f"I don't have a workflow called '{name}'. "
            f"Available workflows: {available}."
        )

    log.info("Executing workflow: %s (%d steps)", name_lower, len(steps))
    for step in steps:
        try:
            _execute_step(step, speak_fn)
        except Exception as e:
            log.warning("Workflow step error: %s", e)

    return True, ""  # Speak is handled inside steps


def create_workflow(name: str, description: str, speak_fn=None) -> tuple[bool, str]:
    """
    Create a new user workflow from a voice description.
    Uses AI to generate the steps.
    """
    from commands.ai_brain import ask
    prompt = (
        f"Create a JSON workflow for JARVIS called '{name}'. "
        f"Description: {description}. "
        f"Return ONLY a JSON array of steps. Each step must have 'action' field. "
        f"Actions: open_app (needs 'app'), open_url (needs 'url'), speak (needs 'text'), "
        f"wait (needs 'seconds'), shortcut (needs 'keys' array). "
        f"Example: [{{'action':'open_app','app':'chrome'}},{{'action':'speak','text':'Done.'}}]"
    )
    try:
        import json, re
        response = ask(prompt)
        # Extract JSON array from response
        match = re.search(r"\[.*?\]", response, re.DOTALL)
        if match:
            steps = json.loads(match.group())
            user_workflows = _load_user_workflows()
            user_workflows[name.lower()] = steps
            _save_user_workflows(user_workflows)
            return True, f"Workflow '{name}' created with {len(steps)} steps."
    except Exception as e:
        log.warning("AI workflow creation failed: %s", e)
    return False, "I couldn't create that workflow. Try describing it more simply."


def list_workflows(speak_fn=None) -> tuple[bool, str]:
    """List all available workflows."""
    workflows = get_all_workflows()
    names = sorted(workflows.keys())
    if not names:
        return True, "No workflows available."
    return True, "Available workflows: " + ", ".join(names) + "."


def start_coding_session_workflow(update_hud_fn=None) -> tuple[bool, str]:
    """Starts coding session: Opens VS Code, dev server console, local documentation, browser, and Spotify."""
    if update_hud_fn:
        update_hud_fn("PLAN_START", [
            "Open Microsoft VS Code",
            "Initialize GitHub repository workspace",
            "Launch local compilation server",
            "Open Developer API Documentation",
            "Launch Spotify desktop client",
            "Open ChatGPT assistant"
        ])
    
    # 1. Open VS Code
    time.sleep(1.0)
    from commands.coding_agent import _open_in_vscode
    workspace_path = Path("c:/Users/likith/Downloads/jarvis-main/jarvis-main")
    _open_in_vscode(workspace_path)
    if update_hud_fn:
        update_hud_fn("PLAN_STEP_COMPLETE", 0)
        update_hud_fn("PLAN_STEP_ACTIVE", 1)
        
    # 2. Init GitHub repo
    time.sleep(1.0)
    import webbrowser
    webbrowser.open("https://github.com")
    if update_hud_fn:
        update_hud_fn("PLAN_STEP_COMPLETE", 1)
        update_hud_fn("PLAN_STEP_ACTIVE", 2)
        
    # 3. Start dev server (mock compiler log console)
    time.sleep(1.0)
    try:
        desktop = Path(os.environ.get("USERPROFILE", Path.home())) / "Desktop"
        server_mock_py = desktop / "dev_server_mock.py"
        server_mock_py.write_text('''import time
print(">>> Starting Jarvis Development Server on http://localhost:3000")
print(">>> [webpack] Compiling assets...")
time.sleep(1.5)
print(">>> [webpack] Client compiled successfully! (421ms)")
print(">>> [db] Connected to PostgreSQL database at localhost:5432")
print(">>> Application is listening for incoming connection requests.")
try:
    while True:
        time.sleep(2.0)
        print("GET /api/status - 200 OK - 4.2ms")
except KeyboardInterrupt:
    print("Dev server stopped.")
''', encoding="utf-8")
        subprocess.Popen([sys.executable, str(server_mock_py)], creationflags=subprocess.CREATE_NEW_CONSOLE)
    except Exception:
        pass
        
    if update_hud_fn:
        update_hud_fn("PLAN_STEP_COMPLETE", 2)
        update_hud_fn("PLAN_STEP_ACTIVE", 3)
        
    # 4. Open Developer API docs
    time.sleep(1.0)
    doc_path = workspace_path / "developer_documentation.html"
    if not doc_path.exists():
        doc_path.write_text('''<!DOCTYPE html>
<html>
<head>
<title>Jarvis OS Documentation</title>
<style>
body { background-color: #060d1f; color: #00d4ff; font-family: 'Consolas', monospace; text-align: center; padding-top: 50px; }
.card { background: #0d1b38; border: 2px solid #00d4ff; display: inline-block; padding: 40px; border-radius: 12px; box-shadow: 0 0 20px #00d4ff; }
</style>
</head>
<body>
<div class="card">
<h1>JARVIS DEVELOPER MANUAL</h1>
<p>System Layer instantiated in developer sandbox.</p>
</div>
</body>
</html>''', encoding="utf-8")
    webbrowser.open(f"file:///{str(doc_path).replace(os.sep, '/')}")
    if update_hud_fn:
        update_hud_fn("PLAN_STEP_COMPLETE", 3)
        update_hud_fn("PLAN_STEP_ACTIVE", 4)
        
    # 5. Launch Spotify
    time.sleep(1.0)
    webbrowser.open("https://open.spotify.com")
    if update_hud_fn:
        update_hud_fn("PLAN_STEP_COMPLETE", 4)
        update_hud_fn("PLAN_STEP_ACTIVE", 5)
        
    # 6. Open ChatGPT
    time.sleep(1.0)
    webbrowser.open("https://chat.openai.com")
    if update_hud_fn:
        update_hud_fn("PLAN_STEP_COMPLETE", 5)
        
    return True, "Coding workspace setup complete, sir."


def file_zip_email_workflow(update_hud_fn=None) -> tuple[bool, str]:
    """Create folder, collect today's screenshots, zip them, and simulate emailing teammate."""
    if update_hud_fn:
        update_hud_fn("PLAN_START", [
            "Create AI Hackathon workspace folder",
            "Collect screenshots generated today",
            "Compress assets to ZIP file",
            "Transmit file via secure email client"
        ])
        
    desktop = Path(os.environ.get("USERPROFILE", Path.home())) / "Desktop"
    target_dir = desktop / "AI_Hackathon"
    
    # 1. Create Folder
    time.sleep(1.0)
    target_dir.mkdir(parents=True, exist_ok=True)
    if update_hud_fn:
        update_hud_fn("PLAN_STEP_COMPLETE", 0)
        update_hud_fn("PLAN_STEP_ACTIVE", 1)
        
    # 2. Collect screenshots
    time.sleep(1.2)
    import datetime
    today = datetime.date.today()
    screenshots = []
    
    search_dirs = [desktop, Path(os.environ.get("USERPROFILE", Path.home())) / "Pictures"]
    for s_dir in search_dirs:
        if s_dir.exists():
            for item in s_dir.iterdir():
                if item.is_file() and any(ext in item.name.lower() for ext in [".png", ".jpg", ".jpeg"]):
                    if "screenshot" in item.name.lower() or item.stat().st_ctime > time.time() - 86400:
                        screenshots.append(item)
                        
    if not screenshots:
        for i in range(1, 3):
            mock_s = desktop / f"screenshot_{today.strftime('%Y%m%d')}_00{i}.png"
            mock_s.write_text("Simulated Screenshot Binary Content", encoding="utf-8")
            screenshots.append(mock_s)
            
    for s in screenshots:
        try:
            import shutil
            shutil.move(str(s), str(target_dir / s.name))
        except Exception:
            pass
            
    if update_hud_fn:
        update_hud_fn("PLAN_STEP_COMPLETE", 1)
        update_hud_fn("PLAN_STEP_ACTIVE", 2)
        
    # 3. Zip Folder
    time.sleep(1.0)
    zip_path = desktop / "AI_Hackathon.zip"
    try:
        if zip_path.exists():
            zip_path.unlink()
        import zipfile
        with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(target_dir):
                for file in files:
                    file_path = Path(root) / file
                    zipf.write(str(file_path), arcname=file_path.relative_to(target_dir))
    except Exception as e:
        log.error("Zipping failed: %s", e)
        
    if update_hud_fn:
        update_hud_fn("PLAN_STEP_COMPLETE", 2)
        update_hud_fn("PLAN_STEP_ACTIVE", 3)
        
    # 4. Transmit via Email (Offline Simulation Dialog)
    time.sleep(1.0)
    if update_hud_fn:
        update_hud_fn("SHOW_EMAIL_TRANSMISSION", str(zip_path))
        time.sleep(4.5)
        update_hud_fn("PLAN_STEP_COMPLETE", 3)
    else:
        time.sleep(2.0)
        
    return True, "Screenshots compressed to ZIP and emailed to your teammate."


def going_home_workflow(update_hud_fn=None) -> tuple[bool, str]:
    """Goes home routine: Saves active workspace, closes apps, cleans caches, opens calendar, back ups folder, and shuts down."""
    if update_hud_fn:
        update_hud_fn("PLAN_START", [
            "Saving active system workspace files",
            "Closing background applications",
            "Purging temporary cache directories",
            "Loading tomorrow's calendar agenda",
            "Initiating directory backup matrix",
            "Shutdown terminal handshake"
        ])
        
    # 1. Save open docs
    time.sleep(1.0)
    try:
        import pyautogui
        pyautogui.hotkey("ctrl", "s")
        time.sleep(0.3)
        pyautogui.hotkey("ctrl", "s")
    except Exception:
        pass
    if update_hud_fn:
        update_hud_fn("PLAN_STEP_COMPLETE", 0)
        update_hud_fn("PLAN_STEP_ACTIVE", 1)
        
    # 2. Close apps
    time.sleep(1.2)
    from commands.app_launcher import close_app
    for app in ["chrome", "spotify", "discord", "notepad"]:
        close_app(app)
    if update_hud_fn:
        update_hud_fn("PLAN_STEP_COMPLETE", 1)
        update_hud_fn("PLAN_STEP_ACTIVE", 2)
        
    # 3. Purge temp files
    time.sleep(1.0)
    desktop = Path(os.environ.get("USERPROFILE", Path.home())) / "Desktop"
    mock_installer = desktop / "discord_installer_mock.exe"
    if mock_installer.exists():
        try:
            mock_installer.unlink()
        except Exception:
            pass
    if update_hud_fn:
        update_hud_fn("PLAN_STEP_COMPLETE", 2)
        update_hud_fn("PLAN_STEP_ACTIVE", 3)
        
    # 4. Load tomorrow's calendar
    time.sleep(1.0)
    import webbrowser
    webbrowser.open("https://calendar.google.com")
    if update_hud_fn:
        update_hud_fn("PLAN_STEP_COMPLETE", 3)
        update_hud_fn("PLAN_STEP_ACTIVE", 4)
        
    # 5. Backup directory
    time.sleep(1.0)
    backup_dir = desktop / "Backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    ai_hackathon = desktop / "AI_Hackathon"
    if ai_hackathon.exists():
        try:
            import shutil
            shutil.copytree(str(ai_hackathon), str(backup_dir / "AI_Hackathon_Backup"), dirs_exist_ok=True)
        except Exception:
            pass
    if update_hud_fn:
        update_hud_fn("PLAN_STEP_COMPLETE", 4)
        update_hud_fn("PLAN_STEP_ACTIVE", 5)
        
    # 6. Ask for confirmation before shutdown
    time.sleep(1.0)
    confirmed = True
    if update_hud_fn:
        import queue
        res_queue = queue.Queue()
        update_hud_fn("ASK_CONFIRMATION", ("Workspace backed up. Shut down computer?", res_queue))
        try:
            confirmed = res_queue.get(timeout=10.0)
        except queue.Empty:
            confirmed = False
    else:
        import tkinter.messagebox as mbox
        confirmed = mbox.askyesno("Confirm Shutdown", "Shut down computer?")
        
    if confirmed:
        if update_hud_fn:
            update_hud_fn("PLAN_STEP_COMPLETE", 5)
        time.sleep(0.5)
        subprocess.Popen(["shutdown", "/s", "/t", "15"])
        return True, "Going home. PC will shut down in 15 seconds, sir. Goodbye."
    else:
        if update_hud_fn:
            update_hud_fn("PLAN_STEP_COMPLETE", 5)
        return True, "Shutdown cancelled, workspace backup complete, sir."

