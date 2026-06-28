"""
install_jarvis.py
-----------------
Run this ONCE to:
  1. Install all Python dependencies
  2. Add Jarvis to Windows Startup so it launches when you log in

Usage:
    python install_jarvis.py
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENV = HERE / ".venv"
STARTUP_FOLDER = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
SHORTCUT_NAME = "JARVIS.bat"


def pip(*args):
    """Run pip inside the venv."""
    venv_python = VENV / "Scripts" / "python.exe"
    python = str(venv_python) if venv_python.exists() else sys.executable
    subprocess.check_call([python, "-m", "pip", "install", "--quiet", *args])


def main():
    print("=" * 55)
    print("  JARVIS — Installer")
    print("=" * 55)

    # ── 1. Install dependencies ────────────────────────────────────────────────
    print("\n[1/2] Installing Python dependencies...")
    packages = [
        "numpy>=1.24,<3",
        "sounddevice>=0.4.6,<0.6",
        "elevenlabs>=1.50,<3",
        "websockets>=13",
        "python-dotenv>=1.0,<2",
        "SpeechRecognition>=3.10.0,<4.0.0",
        "requests",
        "pyttsx3",
        "pillow",
        "psutil",
        "screen-brightness-control",
        "pycaw",
        "comtypes",
    ]
    try:
        pip(*packages)
        print("    [OK] All packages installed.")
    except subprocess.CalledProcessError as e:
        print(f"    [WARN] pip failed: {e}")
        print("    Try manually: pip install -r requirements.txt")

    # PyAudio is tricky — try separately
    try:
        pip("pyaudio")
        print("    [OK] PyAudio installed.")
    except subprocess.CalledProcessError:
        print("    [WARN] PyAudio install failed. Trying pipwin...")
        try:
            pip("pipwin")
            python = str(VENV / "Scripts" / "python.exe") if (VENV / "Scripts" / "python.exe").exists() else sys.executable
            subprocess.check_call([python, "-m", "pipwin", "install", "pyaudio"])
            print("    [OK] PyAudio installed via pipwin.")
        except Exception:
            print("    [WARN] Could not install PyAudio automatically.")
            print("    Download manually from: https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio")

    # ── 2. Add to Windows Startup ──────────────────────────────────────────────
    print("\n[2/2] Adding Jarvis to Windows Startup...")
    bat_content = f"""@echo off
cd /d "{HERE}"
if exist ".venv\\Scripts\\activate.bat" call .venv\\Scripts\\activate.bat
start "" pythonw jarvis.py
"""
    startup_bat = STARTUP_FOLDER / SHORTCUT_NAME
    try:
        STARTUP_FOLDER.mkdir(parents=True, exist_ok=True)
        startup_bat.write_text(bat_content)
        print(f"    [OK] Startup script created: {startup_bat}")
        print("    Jarvis will now start automatically when you log into Windows.")
    except Exception as e:
        print(f"    [WARN] Could not create startup entry: {e}")
        print(f"    Manually copy start_jarvis.bat to:\n    {STARTUP_FOLDER}")

    print("\n" + "=" * 55)
    print("  Setup complete!")
    print("  Run Jarvis now with:  python jarvis.py")
    print("  Or double-click:      start_jarvis.bat")
    print("=" * 55)


if __name__ == "__main__":
    main()
