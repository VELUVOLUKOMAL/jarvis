"""
System Info — Battery, RAM, CPU, IP, uptime, disk space.
Also handles timers/alarms via threading.
"""
from __future__ import annotations

import logging
import os
import platform
import subprocess
import threading
import time
from datetime import datetime, timedelta

log = logging.getLogger("jarvis.sysinfo")

# Active timers: {name: (thread, cancel_event)}
_timers: dict[str, tuple[threading.Thread, threading.Event]] = {}


# ─── System info ─────────────────────────────────────────────────────────────

def get_battery() -> tuple[bool, str]:
    try:
        import psutil
        batt = psutil.sensors_battery()
        if batt is None:
            return True, "This computer is plugged in and doesn't have a battery sensor."
        pct = int(batt.percent)
        charging = batt.power_plugged
        mins = int(batt.secsleft / 60) if batt.secsleft and batt.secsleft > 0 else None
        status = "charging" if charging else "discharging"
        if mins and not charging:
            h, m = divmod(mins, 60)
            time_str = f"{h} hours {m} minutes remaining" if h else f"{m} minutes remaining"
            return True, f"Battery is at {pct} percent, {status}. {time_str}."
        return True, f"Battery is at {pct} percent, {status}."
    except ImportError:
        return False, "psutil not installed."
    except Exception as e:
        return False, f"Could not read battery: {e}"


def get_cpu_ram() -> tuple[bool, str]:
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory()
        used_gb = ram.used / (1024 ** 3)
        total_gb = ram.total / (1024 ** 3)
        return True, (
            f"CPU usage is {cpu:.0f} percent. "
            f"RAM usage is {used_gb:.1f} of {total_gb:.1f} gigabytes."
        )
    except ImportError:
        return False, "psutil not installed."
    except Exception as e:
        return False, f"Could not read system info: {e}"


def get_disk_space(drive: str = "C") -> tuple[bool, str]:
    try:
        import psutil
        usage = psutil.disk_usage(f"{drive}:\\")
        free_gb = usage.free / (1024 ** 3)
        total_gb = usage.total / (1024 ** 3)
        used_pct = usage.percent
        return True, (
            f"Drive {drive} has {free_gb:.1f} gigabytes free "
            f"out of {total_gb:.1f} gigabytes total. {used_pct:.0f} percent used."
        )
    except Exception as e:
        return False, f"Could not read disk info: {e}"


def get_ip() -> tuple[bool, str]:
    try:
        import socket
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        return True, f"Your computer's local IP address is {ip}."
    except Exception as e:
        return False, f"Could not get IP: {e}"


# ─── Timers ───────────────────────────────────────────────────────────────────

def set_timer(seconds: int, label: str = "Timer", speak_fn=None) -> tuple[bool, str]:
    """Set a timer. When it fires, calls speak_fn."""
    cancel_event = threading.Event()
    name = label

    def _run():
        if cancel_event.wait(timeout=seconds):
            log.info("Timer '%s' cancelled.", name)
            return
        msg = f"Sir, your {label} is done!"
        log.info("Timer fired: %s", msg)
        if speak_fn:
            speak_fn(msg)
        else:
            print(f"\n[JARVIS TIMER]: {msg}\n")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    _timers[name] = (t, cancel_event)

    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        duration = f"{h} hour{'s' if h > 1 else ''} {m} minute{'s' if m > 1 else ''}"
    elif m:
        duration = f"{m} minute{'s' if m > 1 else ''}"
    else:
        duration = f"{s} second{'s' if s > 1 else ''}"

    return True, f"Timer set for {duration}."


def cancel_timer(label: str = "") -> tuple[bool, str]:
    if not _timers:
        return False, "No active timers."
    # Cancel the most recent or named timer
    name = label if label in _timers else list(_timers.keys())[-1]
    _, cancel_event = _timers.pop(name)
    cancel_event.set()
    return True, f"Timer '{name}' cancelled."


def parse_duration(text: str) -> int | None:
    """Parse spoken duration to seconds. e.g. '5 minutes', '1 hour 30 minutes', '90 seconds'."""
    import re
    text = text.lower()
    total = 0
    patterns = [
        (r"(\d+)\s*hour", 3600),
        (r"(\d+)\s*hr",   3600),
        (r"(\d+)\s*min",  60),
        (r"(\d+)\s*sec",  1),
    ]
    found = False
    for pattern, mult in patterns:
        m = re.search(pattern, text)
        if m:
            total += int(m.group(1)) * mult
            found = True
    return total if found else None
