"""
Coding Agent — Autonomous code generation and project scaffolding.

Say: "Create a portfolio website", "Create a Python calculator script",
     "Create a React todo app", "Write a login page"

JARVIS will:
  1. Determine the project type and language
  2. Create a project folder
  3. Generate code using Ollama (local) or Gemini
  4. Write files to disk
  5. Open the project in VS Code
  6. Optionally start a dev server
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from pathlib import Path

log = logging.getLogger("jarvis.coding")

# ─── Project type templates ───────────────────────────────────────────────────

PROJECT_TYPES = {
    "portfolio website":    ("web", ["index.html", "style.css", "script.js"]),
    "website":              ("web", ["index.html", "style.css", "script.js"]),
    "html page":            ("web", ["index.html", "style.css"]),
    "landing page":         ("web", ["index.html", "style.css", "script.js"]),
    "login page":           ("web", ["index.html", "style.css", "script.js"]),
    "todo app":             ("web", ["index.html", "style.css", "script.js"]),
    "calculator":           ("python", ["main.py"]),
    "python script":        ("python", ["main.py"]),
    "python app":           ("python", ["main.py", "requirements.txt"]),
    "flask app":            ("flask", ["app.py", "templates/index.html", "static/style.css", "requirements.txt"]),
    "api":                  ("flask", ["app.py", "requirements.txt"]),
    "react app":            ("react", []),  # scaffold via create-react-app
    "node app":             ("node",  ["index.js", "package.json"]),
    "express api":          ("node",  ["index.js", "package.json"]),
    "batch script":         ("bat",   ["run.bat"]),
    "powershell script":    ("ps1",   ["run.ps1"]),
}

# ─── Code generation prompts ──────────────────────────────────────────────────

def _build_prompt(project_name: str, file_name: str, project_type: str, full_desc: str) -> str:
    lang_hints = {
        "web":    "Write clean, modern HTML5/CSS3/vanilla JavaScript.",
        "python": "Write clean Python 3.10+ code with proper error handling.",
        "flask":  "Write Flask 2.x Python code.",
        "node":   "Write modern Node.js ESM code.",
        "bat":    "Write a Windows batch script.",
        "ps1":    "Write a PowerShell script.",
    }
    hint = lang_hints.get(project_type, "Write clean, well-commented code.")
    return (
        f"You are an expert developer. Generate ONLY the file content for '{file_name}' "
        f"as part of a project called '{project_name}' described as: {full_desc}. "
        f"{hint} "
        f"Output ONLY the raw file content, no explanations, no markdown code blocks, no backticks. "
        f"Make it complete, functional, and visually impressive if it's a UI."
    )


def _generate_code(prompt: str) -> str:
    """Generate code via Ollama → Gemini fallback."""
    import os, requests, re

    ollama_url = (os.environ.get("OLLAMA_URL") or "http://localhost:11434").rstrip("/")
    ollama_model = (os.environ.get("OLLAMA_MODEL") or "llama3.2").strip()
    gemini_key = (os.environ.get("GEMINI_API_KEY") or "").strip()

    # Try Ollama first (local, private)
    try:
        r = requests.post(
            f"{ollama_url}/api/generate",
            json={"model": ollama_model, "prompt": prompt, "stream": False,
                  "options": {"num_predict": 2000, "temperature": 0.3}},
            timeout=60,
        )
        r.raise_for_status()
        code = r.json().get("response", "").strip()
        if code:
            # Strip accidental markdown fences
            code = re.sub(r"^```\w*\n?", "", code)
            code = re.sub(r"\n?```$", "", code)
            return code
    except Exception as e:
        log.warning("Ollama codegen failed: %s", e)

    # Try Gemini
    if gemini_key:
        try:
            model = (os.environ.get("GEMINI_MODEL") or "gemini-1.5-flash").strip()
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
            payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
            r = requests.post(url, json=payload, timeout=30)
            r.raise_for_status()
            code = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            code = re.sub(r"^```\w*\n?", "", code)
            code = re.sub(r"\n?```$", "", code)
            return code
        except Exception as e:
            log.warning("Gemini codegen failed: %s", e)

    return "# Code generation failed. Please check your AI connection.\nprint('Hello, World!')"


# ─── File scaffolding ─────────────────────────────────────────────────────────

def _create_project_files(project_dir: Path, files: list[str], project_name: str,
                           project_type: str, full_desc: str, speak_fn=None) -> None:
    for fname in files:
        fpath = project_dir / fname
        fpath.parent.mkdir(parents=True, exist_ok=True)

        if fpath.exists():
            continue  # Don't overwrite existing files

        if speak_fn:
            speak_fn(f"Generating {fname}.")
        log.info("Generating: %s", fname)

        prompt = _build_prompt(project_name, fname, project_type, full_desc)
        code = _generate_code(prompt)

        fpath.write_text(code, encoding="utf-8")
        log.info("Written: %s", fpath)
        time.sleep(0.3)  # Avoid hammering the AI


def _open_in_vscode(path: Path) -> bool:
    """Open a folder in VS Code."""
    import shutil
    code_exe = shutil.which("code")
    if not code_exe:
        local = os.environ.get("LOCALAPPDATA", "")
        code_exe = os.path.join(local, "Programs", "Microsoft VS Code", "Code.exe")
        if not os.path.isfile(code_exe):
            code_exe = None

    if code_exe:
        try:
            subprocess.Popen([code_exe, str(path)],
                             creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            return True
        except Exception as e:
            log.warning("VS Code open failed: %s", e)
    return False


def _start_dev_server(project_dir: Path, project_type: str, speak_fn=None) -> None:
    """Start a simple dev server for web projects."""
    if project_type == "web":
        try:
            if speak_fn:
                speak_fn("Starting a local web server. Opening browser preview.")
            # Python http.server
            subprocess.Popen(
                [sys.executable, "-m", "http.server", "8080", "--directory", str(project_dir)],
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
            )
            time.sleep(1.5)
            import webbrowser
            webbrowser.open("http://localhost:8080")
        except Exception as e:
            log.warning("Dev server failed: %s", e)

    elif project_type in ("flask",):
        if speak_fn:
            speak_fn("Flask project created. Open a terminal in VS Code and run: python app.py")


# ─── Main entry point ─────────────────────────────────────────────────────────

def execute_coding_task(description: str, speak_fn=None) -> tuple[bool, str]:
    """
    Autonomously create a coding project from a natural language description.
    Returns (success, message).
    """
    from commands.memory import get_projects_root
    import re, datetime

    desc_lower = description.strip().lower()

    # Detect project type
    project_type = "web"
    files: list[str] = ["index.html", "style.css", "script.js"]
    for keyword, (ptype, pfiles) in PROJECT_TYPES.items():
        if keyword in desc_lower:
            project_type = ptype
            files = pfiles
            break

    # Generate project name from description
    clean = re.sub(r"[^a-z0-9 ]", "", desc_lower)
    words = clean.split()[:4]
    timestamp = datetime.datetime.now().strftime("%Y%m%d")
    project_slug = "_".join(words) if words else f"project_{timestamp}"
    project_name = project_slug.replace("_", " ").title()

    # Create project directory
    root = get_projects_root()
    project_dir = root / project_slug
    project_dir.mkdir(parents=True, exist_ok=True)

    log.info("Creating project '%s' at %s", project_name, project_dir)

    if speak_fn:
        speak_fn(f"Starting project {project_name}. I'll generate the code now.")

    # Handle React specially (use npx create-react-app)
    if project_type == "react":
        if speak_fn:
            speak_fn("Setting up a React application. This may take a minute.")
        try:
            subprocess.Popen(
                ["npx", "create-react-app", str(project_dir), "--yes"],
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
            )
        except Exception as e:
            log.warning("create-react-app failed: %s", e)
        _open_in_vscode(project_dir)
        return True, f"React app creation started in {project_dir}. Check the terminal for progress."

    # Generate all files
    _create_project_files(project_dir, files, project_name, project_type, description, speak_fn)

    # Open in VS Code
    if speak_fn:
        speak_fn("Code generated. Opening in VS Code.")
    vscode_ok = _open_in_vscode(project_dir)

    # Start dev server for web projects
    _start_dev_server(project_dir, project_type, speak_fn)

    msg = (
        f"Project {project_name} is ready at {project_dir}. "
        + ("Opened in VS Code. " if vscode_ok else "")
        + ("Browser preview started at localhost 8080." if project_type == "web" else "")
    )
    return True, msg
