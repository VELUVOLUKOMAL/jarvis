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
