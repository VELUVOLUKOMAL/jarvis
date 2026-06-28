"""
Media Control — Play/pause/next/prev via keyboard media keys.
"""
from __future__ import annotations

import logging
import subprocess
import sys

log = logging.getLogger("jarvis.media")

# Virtual key codes for Windows
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2


def _press_vk(vk: int) -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        KEYEVENTF_KEYUP = 0x0002
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        return True
    except Exception as e:
        log.warning("VK press failed: %s", e)
        return False


def media_play_pause() -> tuple[bool, str]:
    ok = _press_vk(VK_MEDIA_PLAY_PAUSE)
    return ok, "Playing." if ok else "Media key not available."


def media_next() -> tuple[bool, str]:
    ok = _press_vk(VK_MEDIA_NEXT_TRACK)
    return ok, "Next track." if ok else "Media key not available."


def media_prev() -> tuple[bool, str]:
    ok = _press_vk(VK_MEDIA_PREV_TRACK)
    return ok, "Previous track." if ok else "Media key not available."


def media_stop() -> tuple[bool, str]:
    ok = _press_vk(VK_MEDIA_STOP)
    return ok, "Stopped." if ok else "Media key not available."
