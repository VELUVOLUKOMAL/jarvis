r"""
setup_autostart.py
------------------
Makes Jarvis start AUTOMATICALLY every time Windows boots.
No terminal window. Runs silently in the background 24/7.

Run ONCE (as Administrator for best results):
    .venv\Scripts\python.exe setup_autostart.py
"""
import ctypes
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENV_PYTHONW = HERE / ".venv" / "Scripts" / "pythonw.exe"
VENV_PYTHON  = HERE / ".venv" / "Scripts" / "python.exe"
JARVIS_PY    = HERE / "jarvis.py"
TASK_NAME    = "JARVIS_Assistant"


def task_exists() -> bool:
    r = subprocess.run(
        ["schtasks", "/query", "/tn", TASK_NAME],
        capture_output=True, text=True
    )
    return r.returncode == 0


def create_task() -> bool:
    # Use pythonw.exe so no console window appears
    exe = str(VENV_PYTHONW) if VENV_PYTHONW.exists() else str(VENV_PYTHON)
    if not Path(exe).exists():
        exe = sys.executable.replace("python.exe", "pythonw.exe")
        if not Path(exe).exists():
            exe = sys.executable

    cmd = " ".join([f'"{exe}"', f'"{JARVIS_PY}"'])

    result = subprocess.run(
        [
            "schtasks", "/create",
            "/tn", TASK_NAME,
            "/tr", cmd,
            "/sc", "ONLOGON",
            "/ru", os.environ.get("USERNAME", ""),
            "/rl", "HIGHEST",
            "/it",               # Run only when the user is logged on (interactive session)
            "/f",                # Overwrite if exists
            "/delay", "0000:05"  # 5-second delay after login for mic to be ready
        ],
        capture_output=True, text=True
    )
    return result.returncode == 0


def remove_task() -> bool:
    r = subprocess.run(
        ["schtasks", "/delete", "/tn", TASK_NAME, "/f"],
        capture_output=True, text=True
    )
    return r.returncode == 0


def fix_permissions() -> None:
    """Reset jarvis.py ownership to current user so it can always be edited."""
    username = os.environ.get("USERNAME", "")
    target = str(JARVIS_PY)
    print(f"[INFO] Resetting file permissions for {target}...")
    subprocess.run(["takeown", "/F", target, "/A"], capture_output=True)
    subprocess.run(["icacls", target, "/grant", f"{username}:F", "/grant", "administrators:F"], capture_output=True)
    subprocess.run(["attrib", "-r", "-s", target], capture_output=True)
    print("[OK] File permissions reset.")


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def main():
    if not is_admin():
        print("[INFO] Requesting administrator privileges...")
        params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{sys.argv[0]}" {params}', None, 1
        )
        sys.exit(0)

    print("=" * 55)
    print("  JARVIS — Auto-Start Setup")
    print("=" * 55)

    if "--remove" in sys.argv:
        print("\nRemoving JARVIS from startup...")
        if remove_task():
            print("[OK] JARVIS removed from Windows startup.")
        else:
            print("[FAIL] Could not remove. Try running as Administrator.")
        return

    print(f"\nJarvis script : {JARVIS_PY}")
    print(f"Python (no UI): {VENV_PYTHONW}")

    if not JARVIS_PY.exists():
        print(f"[ERROR] jarvis.py not found at {JARVIS_PY}")
        sys.exit(1)

    # Always reset file permissions first
    fix_permissions()

    if task_exists():
        print("\n[INFO] Task already exists. Updating...")

    print("\nCreating Windows Scheduled Task (ONLOGON)...")
    if create_task():
        print("[OK] JARVIS will now start automatically on every login!")
        print(f"     Task name: {TASK_NAME}")
        print("\n     To remove auto-start later:")
        print(f"     .venv\\Scripts\\python.exe setup_autostart.py --remove")

        # Also start Jarvis right now (in background)
        exe = str(VENV_PYTHONW) if VENV_PYTHONW.exists() else str(VENV_PYTHON)
        print("\nStarting Jarvis in the background now...")
        subprocess.Popen(
            [exe, str(JARVIS_PY)],
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
            close_fds=True,
        )
        print("[OK] Jarvis is running in the background!")
        print("     Say 'Jarvis' or double-clap to wake it.")
    else:
        print("[FAIL] Could not create task.")
        print("       Try: Run this script as Administrator (right-click → Run as admin)")

    print("=" * 55)


if __name__ == "__main__":
    main()
