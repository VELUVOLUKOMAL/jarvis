"""
add_to_startup.py
-----------------
Adds Jarvis to Windows Startup folder so it runs at every login.
No admin, no Task Scheduler, no password needed.
Run once:  .venv\Scripts\python.exe add_to_startup.py
"""
import os
import sys
import winreg
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAUNCHER = HERE / "start_jarvis_bg.bat"
STARTUP_FOLDER = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
SHORTCUT_NAME = "JARVIS_Assistant.bat"

def add_to_startup():
    dest = STARTUP_FOLDER / SHORTCUT_NAME
    try:
        # Copy the bat file to Startup folder
        import shutil
        shutil.copy2(str(LAUNCHER), str(dest))
        print(f"[OK] Jarvis added to Startup folder: {dest}")
        print("     Jarvis will now start automatically every time you log in!")
    except Exception as e:
        print(f"[FAIL] Could not copy to Startup folder: {e}")
        # Fallback: use Registry Run key
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                  r"Software\Microsoft\Windows\CurrentVersion\Run",
                                  0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "JARVIS_Assistant", 0, winreg.REG_SZ, str(LAUNCHER))
            winreg.CloseKey(key)
            print(f"[OK] Jarvis added to Registry Run key (fallback).")
        except Exception as e2:
            print(f"[FAIL] Registry fallback also failed: {e2}")

def remove_from_startup():
    dest = STARTUP_FOLDER / SHORTCUT_NAME
    if dest.exists():
        dest.unlink()
        print(f"[OK] Jarvis removed from Startup folder.")
    # Also remove from Registry if present
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                              r"Software\Microsoft\Windows\CurrentVersion\Run",
                              0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, "JARVIS_Assistant")
        winreg.CloseKey(key)
    except Exception:
        pass

if __name__ == "__main__":
    if "--remove" in sys.argv:
        remove_from_startup()
    else:
        add_to_startup()
        # Also launch Jarvis right now
        import subprocess
        print("\nStarting Jarvis now...")
        subprocess.Popen(
            [str(LAUNCHER)],
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
            close_fds=True,
        )
        print("[OK] Jarvis is running! Say 'Jarvis' or double-clap to wake it.")
