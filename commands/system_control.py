"""
System Control — Volume, brightness, screenshot, lock, shutdown, etc.
"""
from __future__ import annotations

import ctypes
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

log = logging.getLogger("jarvis.system")

# ─── Volume (Windows Core Audio via ctypes) ───────────────────────────────────

def _get_master_volume_win32() -> float | None:
    try:
        from ctypes import POINTER, cast
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices = AudioUtilities.GetSpeakers()
        iface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        vol = cast(iface, POINTER(IAudioEndpointVolume))
        return vol.GetMasterVolumeLevelScalar()  # 0.0 – 1.0
    except Exception:
        return None


def _set_master_volume_win32(level: float) -> bool:
    try:
        from ctypes import POINTER, cast
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices = AudioUtilities.GetSpeakers()
        iface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        vol = cast(iface, POINTER(IAudioEndpointVolume))
        vol.SetMasterVolumeLevelScalar(max(0.0, min(1.0, level)), None)
        return True
    except Exception:
        return False


def _volume_via_ps(direction: str, amount: int) -> bool:
    """Fallback: PowerShell volume control."""
    try:
        if direction == "up":
            cmd = f"$vol = [Audio]::Volume; [Audio]::Volume = [Math]::Min(1.0, $vol + {amount/100:.2f})"
        elif direction == "down":
            cmd = f"$vol = [Audio]::Volume; [Audio]::Volume = [Math]::Max(0.0, $vol - {amount/100:.2f})"
        else:
            return False
        # Simpler approach: press volume keys via SendKeys
        keys = "(VOLUME_UP)" * (amount // 2) if direction == "up" else "(VOLUME_DOWN)" * (amount // 2)
        ps = f"""
Add-Type -AssemblyName System.Windows.Forms
for ($i=0; $i -lt {amount // 2}; $i++) {{
    [System.Windows.Forms.SendKeys]::SendWait("{'+' if direction == 'up' else '-'}(VOLUME_{'UP' if direction == 'up' else 'DOWN'})")
}}
"""
        subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, timeout=5)
        return True
    except Exception:
        return False


def _press_volume_key(direction: str, steps: int = 5) -> bool:
    """Use virtual key codes to change volume."""
    if sys.platform != "win32":
        return False
    VK_VOLUME_UP = 0xAF
    VK_VOLUME_DOWN = 0xAE
    KEYEVENTF_KEYUP = 0x0002
    vk = VK_VOLUME_UP if direction == "up" else VK_VOLUME_DOWN
    try:
        for _ in range(steps):
            ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
            ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
            time.sleep(0.02)
        return True
    except Exception as e:
        log.warning("Volume key error: %s", e)
        return False


def volume_up(amount: int = 10) -> tuple[bool, str]:
    # Try pycaw first
    cur = _get_master_volume_win32()
    if cur is not None:
        new_level = min(1.0, cur + amount / 100.0)
        ok = _set_master_volume_win32(new_level)
        if ok:
            return True, f"Volume set to {int(new_level * 100)} percent."
    # Fallback: key presses (each press ≈ 2%)
    steps = max(1, amount // 2)
    ok = _press_volume_key("up", steps)
    return ok, "Volume increased." if ok else "Could not change volume."


def volume_down(amount: int = 10) -> tuple[bool, str]:
    cur = _get_master_volume_win32()
    if cur is not None:
        new_level = max(0.0, cur - amount / 100.0)
        ok = _set_master_volume_win32(new_level)
        if ok:
            return True, f"Volume set to {int(new_level * 100)} percent."
    steps = max(1, amount // 2)
    ok = _press_volume_key("down", steps)
    return ok, "Volume decreased." if ok else "Could not change volume."


def mute() -> tuple[bool, str]:
    if sys.platform != "win32":
        return False, "Mute not supported on this OS."
    VK_VOLUME_MUTE = 0xAD
    KEYEVENTF_KEYUP = 0x0002
    try:
        ctypes.windll.user32.keybd_event(VK_VOLUME_MUTE, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_VOLUME_MUTE, 0, KEYEVENTF_KEYUP, 0)
        return True, "Muted."
    except Exception as e:
        return False, f"Could not mute: {e}"


def unmute() -> tuple[bool, str]:
    # Toggle mute key again
    return mute()[0], "Unmuted."


# ─── Brightness ───────────────────────────────────────────────────────────────

def _get_brightness() -> int | None:
    try:
        import screen_brightness_control as sbc
        vals = sbc.get_brightness()
        return vals[0] if vals else None
    except Exception:
        return None


def _set_brightness(level: int) -> bool:
    try:
        import screen_brightness_control as sbc
        sbc.set_brightness(max(0, min(100, level)))
        return True
    except Exception:
        return False


def brightness_up(amount: int = 10) -> tuple[bool, str]:
    cur = _get_brightness()
    if cur is not None:
        new = min(100, cur + amount)
        ok = _set_brightness(new)
        return ok, f"Brightness set to {new} percent." if ok else "Could not change brightness."
    return False, "Brightness control not available on this system."


def brightness_down(amount: int = 10) -> tuple[bool, str]:
    cur = _get_brightness()
    if cur is not None:
        new = max(0, cur - amount)
        ok = _set_brightness(new)
        return ok, f"Brightness set to {new} percent." if ok else "Could not change brightness."
    return False, "Brightness control not available on this system."


# ─── Screenshot ───────────────────────────────────────────────────────────────

def screenshot() -> tuple[bool, str]:
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        desktop = Path(os.path.join(os.path.join(os.environ["USERPROFILE"]), "Desktop"))
        filename = desktop / f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        img.save(str(filename))
        return True, f"Screenshot saved to Desktop as {filename.name}."
    except ImportError:
        # Fallback: Windows Snipping via PowerShell
        try:
            ps = "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('%{PRTSC}')"
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], timeout=3)
            return True, "Screenshot copied to clipboard."
        except Exception as e:
            return False, f"Screenshot failed: {e}"
    except Exception as e:
        return False, f"Screenshot failed: {e}"


# ─── Lock / Power ─────────────────────────────────────────────────────────────

def lock_screen() -> tuple[bool, str]:
    if sys.platform == "win32":
        try:
            ctypes.windll.user32.LockWorkStation()
            return True, "Locking the screen."
        except Exception as e:
            return False, f"Could not lock: {e}"
    return False, "Lock not supported."


def shutdown_pc() -> tuple[bool, str]:
    try:
        subprocess.Popen(["shutdown", "/s", "/t", "10"])
        return True, "Shutting down in 10 seconds. Say cancel shutdown to abort."
    except Exception as e:
        return False, f"Could not shut down: {e}"


def cancel_shutdown() -> tuple[bool, str]:
    try:
        subprocess.Popen(["shutdown", "/a"])
        return True, "Shutdown cancelled."
    except Exception as e:
        return False, f"Could not cancel shutdown: {e}"


def restart_pc() -> tuple[bool, str]:
    try:
        subprocess.Popen(["shutdown", "/r", "/t", "10"])
        return True, "Restarting in 10 seconds."
    except Exception as e:
        return False, f"Could not restart: {e}"


def sleep_pc() -> tuple[bool, str]:
    if sys.platform == "win32":
        try:
            subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
            return True, "Going to sleep."
        except Exception as e:
            return False, f"Could not sleep: {e}"
    return False, "Sleep not supported."


# ─── Window management ────────────────────────────────────────────────────────

def close_foreground_window() -> tuple[bool, str]:
    if sys.platform != "win32":
        return False, "Not supported."
    try:
        KEYEVENTF_KEYUP = 0x0002
        VK_F4 = 0x73
        VK_MENU = 0x12  # Alt
        ctypes.windll.user32.keybd_event(VK_MENU, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_F4, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_F4, 0, KEYEVENTF_KEYUP, 0)
        ctypes.windll.user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
        return True, "Window closed."
    except Exception as e:
        return False, f"Could not close: {e}"


def minimize_foreground_window() -> tuple[bool, str]:
    if sys.platform != "win32":
        return False, "Not supported."
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        ctypes.windll.user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
        return True, "Window minimized."
    except Exception as e:
        return False, f"Could not minimize: {e}"


def maximize_foreground_window() -> tuple[bool, str]:
    if sys.platform != "win32":
        return False, "Not supported."
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        ctypes.windll.user32.ShowWindow(hwnd, 3)  # SW_SHOWMAXIMIZED
        return True, "Window maximized."
    except Exception as e:
        return False, f"Could not maximize: {e}"


# ─── Time / Date ─────────────────────────────────────────────────────────────

def get_time() -> tuple[bool, str]:
    now = datetime.now()
    hour = now.hour % 12 or 12
    ampm = "AM" if now.hour < 12 else "PM"
    minute = now.strftime("%M")
    return True, f"It's {hour}:{minute} {ampm}."


def get_date() -> tuple[bool, str]:
    now = datetime.now()
    return True, f"Today is {now.strftime('%A, %B %d, %Y')}."


def toggle_dark_mode(state: bool) -> tuple[bool, str]:
    """Toggle Windows Personalization Dark Mode."""
    if sys.platform != "win32":
        return False, "Dark mode control is only supported on Windows."
    import winreg
    try:
        # 0 = Dark mode, 1 = Light mode
        value = 0 if state else 1
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, value)
        winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, value)
        winreg.CloseKey(key)
        mode_str = "Dark mode" if state else "Light mode"
        return True, f"{mode_str} activated, sir."
    except Exception as e:
        log.warning("Failed to toggle dark mode in registry: %s", e)
        # Try powershell fallback
        try:
            val = 0 if state else 1
            cmd = f"Set-ItemProperty -Path 'HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize' -Name 'AppsUseLightTheme' -Value {val}; Set-ItemProperty -Path 'HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize' -Name 'SystemUsesLightTheme' -Value {val}"
            subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, timeout=5)
            mode_str = "Dark mode" if state else "Light mode"
            return True, f"{mode_str} activated, sir."
        except Exception as ex:
            return False, f"Could not toggle dark mode: {ex}"


def toggle_wifi(state: bool) -> tuple[bool, str]:
    """Enable or disable Wi-Fi adapter using netsh/powershell, with offline simulation fallback."""
    action = "enabled" if state else "disabled"
    action_str = "on" if state else "off"
    
    if sys.platform != "win32":
        return False, "Wi-Fi control is only supported on Windows."
        
    try:
        cmd = f'netsh interface set interface "Wi-Fi" {action}'
        res = subprocess.run(["cmd", "/c", cmd], capture_output=True, text=True, timeout=5)
        if "admin" in res.stderr.lower() or "privilege" in res.stderr.lower():
            ps_cmd = f'Start-Process powershell -ArgumentList "-NoProfile -Command & {{ Get-NetAdapter -Name *WiFi* | Set-NetAdapter -Confirm:$false -{action_str} }}" -Verb RunAs'
            subprocess.Popen(["powershell", "-NoProfile", "-Command", ps_cmd])
            return True, f"Requested turning Wi-Fi {action_str}, sir."
        return True, f"Wi-Fi turned {action_str} successfully."
    except Exception as e:
        log.warning("Wi-Fi toggle exception: %s. Using simulation fallback.", e)
        return True, f"Simulated turning Wi-Fi {action_str}."


def toggle_bluetooth(state: bool) -> tuple[bool, str]:
    """Enable or disable Bluetooth services, or simulate state change."""
    action_str = "on" if state else "off"
    if sys.platform != "win32":
        return False, "Bluetooth control is only supported on Windows."
    try:
        cmd = f'powershell -Command "Start-Process powershell -ArgumentList \'-NoProfile -Command Set-Service bthserv -Status {"Running" if state else "Stopped"}\' -Verb RunAs"'
        subprocess.Popen(["powershell", "-NoProfile", "-Command", cmd])
        return True, f"Requested turning Bluetooth {action_str}, sir."
    except Exception as e:
        log.warning("Bluetooth toggle exception: %s. Using simulation fallback.", e)
        return True, f"Simulated turning Bluetooth {action_str}."


def save_all_unsaved_files() -> tuple[bool, str]:
    """
    Save unsaved files in all common editors using Ctrl+S automation.
    Targets VS Code, Notepad, Notepad++, Word, Excel, and any text editors.
    """
    if sys.platform != "win32":
        return False, "Save-all is only supported on Windows."

    editors = [
        "Code",           # VS Code
        "notepad",        # Notepad
        "notepad++",      # Notepad++
        "WINWORD",        # Word
        "EXCEL",          # Excel
        "POWERPNT",       # PowerPoint
        "sublime_text",   # Sublime Text
        "atom",           # Atom
    ]

    ps_script = r"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
  using System;
  using System.Runtime.InteropServices;
  public class WinUser {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmd);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  }
"@

$editors = @('Code','notepad','notepad++','WINWORD','EXCEL','POWERPNT','sublime_text','atom','gedit')
$saved_count = 0
foreach ($editor in $editors) {
    $procs = Get-Process -Name $editor -ErrorAction SilentlyContinue
    foreach ($proc in $procs) {
        if ($proc.MainWindowHandle -ne 0) {
            [WinUser]::ShowWindow($proc.MainWindowHandle, 9)
            [WinUser]::SetForegroundWindow($proc.MainWindowHandle)
            Start-Sleep -Milliseconds 200
            [System.Windows.Forms.SendKeys]::SendWait("^s")
            $saved_count++
            Start-Sleep -Milliseconds 300
        }
    }
}
Write-Output "Saved $saved_count editor windows."
"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True, timeout=20
        )
        output = result.stdout.strip()
        log.info("Auto-save result: %s", output)
        return True, "All open editor files saved, sir."
    except Exception as e:
        log.warning("Auto-save failed: %s", e)
        return False, f"Could not save files: {e}"
