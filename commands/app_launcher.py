"""
App Launcher — Opens/focuses Windows applications by name.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

log = logging.getLogger("jarvis.app_launcher")

_USER = os.environ.get("USERPROFILE", r"C:\Users\User")
_LOCAL = os.environ.get("LOCALAPPDATA", os.path.join(_USER, "AppData", "Local"))
_ROAMING = os.environ.get("APPDATA", os.path.join(_USER, "AppData", "Roaming"))
_PROGFILES = os.environ.get("ProgramFiles", r"C:\Program Files")
_PROGFILESX86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")

# Maps voice name → list of candidate paths/commands (tried in order)
APP_MAP: dict[str, list[str]] = {
    "vs code": [
        shutil.which("code") or "",
        os.path.join(_LOCAL, "Programs", "Microsoft VS Code", "Code.exe"),
        os.path.join(_PROGFILES, "Microsoft VS Code", "Code.exe"),
    ],
    "cursor": [
        shutil.which("cursor") or "",
        os.path.join(_LOCAL, "Programs", "cursor", "Cursor.exe"),
        os.path.join(_LOCAL, "Programs", "Cursor", "Cursor.exe"),
    ],
    "antigravity": [
        shutil.which("antigravity") or "",
        os.path.join(_LOCAL, "Programs", "antigravity", "Antigravity.exe"),
        os.path.join(_LOCAL, "Programs", "Antigravity", "Antigravity.exe"),
        # Also try opening via the web if not found locally
    ],
    "chrome": [
        os.path.join(_PROGFILES, "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(_PROGFILESX86, "Google", "Chrome", "Application", "chrome.exe"),
        shutil.which("google-chrome") or "",
        shutil.which("chrome") or "",
    ],
    "firefox": [
        os.path.join(_PROGFILES, "Mozilla Firefox", "firefox.exe"),
        shutil.which("firefox") or "",
    ],
    "edge": [
        os.path.join(_PROGFILES, "Microsoft", "Edge", "Application", "msedge.exe"),
        shutil.which("msedge") or "",
    ],
    "spotify": [
        os.path.join(_ROAMING, "Spotify", "Spotify.exe"),
        os.path.join(_LOCAL, "Microsoft", "WindowsApps", "Spotify.exe"),
    ],
    "discord": [
        os.path.join(_LOCAL, "Discord", "Update.exe"),
        os.path.join(_ROAMING, "discord", "Discord.exe"),
    ],
    "whatsapp": [
        os.path.join(_LOCAL, "WhatsApp", "WhatsApp.exe"),
        shutil.which("whatsapp") or "",
    ],
    "telegram": [
        os.path.join(_ROAMING, "Telegram Desktop", "Telegram.exe"),
        shutil.which("telegram") or "",
    ],
    "explorer": ["explorer.exe"],
    "notepad": ["notepad.exe"],
    "calculator": ["calc.exe"],
    "task manager": ["taskmgr.exe"],
    "paint": ["mspaint.exe"],
    "cmd": ["cmd.exe"],
    "powershell": ["powershell.exe"],
    "windows terminal": [
        shutil.which("wt") or "",
        "wt.exe",
    ],
    "word": [
        os.path.join(_PROGFILES, "Microsoft Office", "root", "Office16", "WINWORD.EXE"),
        os.path.join(_PROGFILESX86, "Microsoft Office", "root", "Office16", "WINWORD.EXE"),
        shutil.which("winword") or "",
    ],
    "excel": [
        os.path.join(_PROGFILES, "Microsoft Office", "root", "Office16", "EXCEL.EXE"),
        shutil.which("excel") or "",
    ],
    "powerpoint": [
        os.path.join(_PROGFILES, "Microsoft Office", "root", "Office16", "POWERPNT.EXE"),
        shutil.which("powerpnt") or "",
    ],
    "steam": [
        os.path.join(_PROGFILES, "Steam", "Steam.exe"),
        os.path.join(_PROGFILESX86, "Steam", "Steam.exe"),
    ],
    "photoshop": [
        os.path.join(_PROGFILES, "Adobe", "Adobe Photoshop 2024", "Photoshop.exe"),
        os.path.join(_PROGFILES, "Adobe", "Adobe Photoshop 2023", "Photoshop.exe"),
        os.path.join(_PROGFILES, "Adobe", "Adobe Photoshop 2022", "Photoshop.exe"),
        shutil.which("photoshop") or "",
    ],
    "obs": [
        os.path.join(_PROGFILES, "obs-studio", "bin", "64bit", "obs64.exe"),
        shutil.which("obs64") or "",
    ],
    "vlc": [
        os.path.join(_PROGFILES, "VideoLAN", "VLC", "vlc.exe"),
        shutil.which("vlc") or "",
    ],
    "settings": ["ms-settings:"],
    "control panel": ["control.exe"],
    "device manager": ["devmgmt.msc"],
    "task scheduler": ["taskschd.msc"],
    "registry editor": ["regedit.exe"],
    "snipping tool": ["snippingtool.exe"],
    "zoom": [
        os.path.join(_ROAMING, "Zoom", "bin", "Zoom.exe"),
        shutil.which("zoom") or "",
    ],
    "slack": [
        os.path.join(_LOCAL, "slack", "slack.exe"),
        shutil.which("slack") or "",
    ],
}


def _is_running(process_name: str) -> bool:
    """Check if a process is currently running."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {process_name}", "/NH"],
            capture_output=True, text=True, timeout=3
        )
        return process_name.lower() in result.stdout.lower()
    except Exception:
        return False


def _focus_window(exe_name: str) -> bool:
    """Try to focus an existing window using PowerShell."""
    if sys.platform != "win32":
        return False
    try:
        ps_script = f"""
$proc = Get-Process | Where-Object {{$_.MainWindowTitle -ne '' -and $_.Name -like '*{exe_name.replace('.exe','')}*'}} | Select-Object -First 1
if ($proc) {{
    Add-Type -AssemblyName Microsoft.VisualBasic
    [Microsoft.VisualBasic.Interaction]::AppActivate($proc.Id)
    $sig = '[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow); [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);'
    $type = Add-Type -MemberDefinition $sig -Name Win32 -Namespace WinAPI -PassThru
    $type::ShowWindow($proc.MainWindowHandle, 9)
    $type::SetForegroundWindow($proc.MainWindowHandle)
    Write-Output 'focused'
}}
"""
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True, timeout=5
        )
        return "focused" in result.stdout
    except Exception:
        return False


def _find_in_start_menu(app_name: str) -> str | None:
    # Folders to search
    start_menu_paths = [
        os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"), "Microsoft", "Windows", "Start Menu", "Programs"),
        os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs")
    ]
    name_clean = app_name.lower().strip()
    
    # Search recursively for shortcut files (.lnk)
    for folder in start_menu_paths:
        if not os.path.exists(folder):
            continue
        for root, dirs, files in os.walk(folder):
            for file in files:
                if file.lower().endswith(".lnk"):
                    file_name = file[:-4].lower()
                    if name_clean == file_name or name_clean in file_name:
                        return os.path.join(root, file)
    return None


def launch_app(app_name: str) -> tuple[bool, str]:
    """
    Launch or focus an app by name.
    Returns (success, message).
    """
    name = app_name.lower().strip()

    # Special case: WhatsApp Store app
    if name == "whatsapp":
        try:
            os.startfile("whatsapp:")
            return True, "Opening WhatsApp."
        except Exception:
            pass

    # Special case: Spotify Store app
    if name == "spotify":
        try:
            os.startfile("spotify:")
            return True, "Opening Spotify."
        except Exception:
            pass

    # Find candidates
    candidates = APP_MAP.get(name, [])

    # If not in map, try shutil.which as a last resort
    if not candidates:
        found = shutil.which(name) or shutil.which(name + ".exe")
        if found:
            candidates = [found]

    # If still not found, search the Windows Start Menu!
    if not candidates:
        lnk_path = _find_in_start_menu(name)
        if lnk_path:
            candidates = [lnk_path]

    if not candidates:
        return False, f"I don't know how to open {app_name}. You can add it to the app list."

    for path in candidates:
        if not path:
            continue
        try:
            # Special case: ms-settings:, .msc, and .lnk files
            if path.startswith("ms-") or path.endswith(".msc") or path.endswith(".lnk"):
                os.startfile(path)
                return True, f"Opening {app_name}."

            # Special case: Discord updater
            if "Discord" in path and "Update.exe" in path:
                subprocess.Popen(
                    [path, "--processStart", "Discord.exe"],
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                )
                return True, f"Opening {app_name}."

            # Check if file exists (for absolute paths)
            if os.path.sep in path and not os.path.isfile(path):
                continue

            subprocess.Popen(
                [path],
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            return True, f"Opening {app_name}."
        except FileNotFoundError:
            continue
        except Exception as e:
            log.warning("Failed to launch %s via %s: %s", app_name, path, e)
            continue

    return False, f"Could not find {app_name} on this computer."
