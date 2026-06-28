"""
Input Control — Full mouse and keyboard control via pyautogui.

Commands:
  "Type [text]"                 → Types text at cursor
  "Press Control S"             → Sends Ctrl+S hotkey
  "Press Enter"                 → Presses Enter
  "Move mouse to center"        → Centers mouse on screen
  "Click"                       → Left click at current position
  "Double click"                → Double click
  "Right click"                 → Right click
  "Scroll up / down"            → Scrolls
  "Copy" / "Paste" / "Undo"    → Common shortcuts
  "Select all"                  → Ctrl+A
  "Drag [from] to [to]"         → Drag operation
"""
from __future__ import annotations

import logging
import re
import time

log = logging.getLogger("jarvis.input")

# Map of spoken key names → pyautogui key names
KEY_MAP: dict[str, str] = {
    "enter":        "enter",
    "return":       "enter",
    "escape":       "escape",
    "esc":          "escape",
    "space":        "space",
    "spacebar":     "space",
    "tab":          "tab",
    "backspace":    "backspace",
    "delete":       "delete",
    "del":          "delete",
    "up":           "up",
    "down":         "down",
    "left":         "left",
    "right":        "right",
    "home":         "home",
    "end":          "end",
    "page up":      "pageup",
    "page down":    "pagedown",
    "f1":           "f1",  "f2": "f2",  "f3": "f3",  "f4": "f4",
    "f5":           "f5",  "f6": "f6",  "f7": "f7",  "f8": "f8",
    "f9":           "f9",  "f10": "f10","f11": "f11","f12": "f12",
    "print screen": "printscreen",
    "control":      "ctrl",  "ctrl": "ctrl",
    "alt":          "alt",
    "shift":        "shift",
    "windows":      "win",   "win": "win",
    "caps lock":    "capslock",
    "num lock":     "numlock",
}

# Common shortcut phrases
SHORTCUTS: dict[str, list[str]] = {
    "copy":             ["ctrl", "c"],
    "paste":            ["ctrl", "v"],
    "cut":              ["ctrl", "x"],
    "undo":             ["ctrl", "z"],
    "redo":             ["ctrl", "y"],
    "select all":       ["ctrl", "a"],
    "save":             ["ctrl", "s"],
    "save as":          ["ctrl", "shift", "s"],
    "find":             ["ctrl", "f"],
    "new tab":          ["ctrl", "t"],
    "close tab":        ["ctrl", "w"],
    "reopen tab":       ["ctrl", "shift", "t"],
    "new window":       ["ctrl", "n"],
    "refresh":          ["f5"],
    "full screen":      ["f11"],
    "task view":        ["win", "tab"],
    "show desktop":     ["win", "d"],
    "lock screen":      ["win", "l"],
    "open run":         ["win", "r"],
    "open search":      ["win", "s"],
    "open settings":    ["win", "i"],
    "take screenshot":  ["win", "shift", "s"],
    "switch window":    ["alt", "tab"],
    "close window":     ["alt", "f4"],
    "zoom in":          ["ctrl", "="],
    "zoom out":         ["ctrl", "-"],
    "zoom reset":       ["ctrl", "0"],
}


def _get_pyautogui():
    try:
        import pyautogui
        pyautogui.FAILSAFE = True   # Move mouse to top-left corner to abort
        pyautogui.PAUSE = 0.05      # Small pause between actions
        return pyautogui
    except ImportError:
        raise RuntimeError("pyautogui not installed. Run: pip install pyautogui")


def type_text(text: str) -> tuple[bool, str]:
    """Type text at the current cursor position."""
    try:
        pg = _get_pyautogui()
        time.sleep(0.2)
        pg.typewrite(text, interval=0.04)
        log.info("Typed: %r", text)
        return True, f"Typed: {text[:40]}{'...' if len(text) > 40 else ''}."
    except Exception as e:
        log.warning("Type error: %s", e)
        return False, f"Could not type: {e}"


def press_shortcut(spoken: str) -> tuple[bool, str]:
    """
    Handle 'press X' commands. Supports hotkeys like 'Control S', 'Alt F4', 'F5'.
    """
    t = spoken.strip().lower()

    # Check predefined shortcuts first
    for phrase, keys in SHORTCUTS.items():
        if phrase in t or t == phrase:
            try:
                pg = _get_pyautogui()
                pg.hotkey(*keys)
                return True, f"Pressed {phrase}."
            except Exception as e:
                return False, f"Shortcut failed: {e}"

    # Parse "Control S", "Alt F4", "Shift Enter", etc.
    # Strip "press" keyword
    t = re.sub(r"^press\s+", "", t).strip()

    # Replace spoken modifier names with shorthand
    parts = re.split(r"[\s+]+", t)
    mapped_keys = []
    for part in parts:
        key = KEY_MAP.get(part, part)  # If not in map, pass through
        if key:
            mapped_keys.append(key)

    if mapped_keys:
        try:
            pg = _get_pyautogui()
            if len(mapped_keys) == 1:
                pg.press(mapped_keys[0])
            else:
                pg.hotkey(*mapped_keys)
            return True, f"Pressed {' + '.join(mapped_keys)}."
        except Exception as e:
            return False, f"Key press failed: {e}"

    return False, f"I didn't understand the key combination: {spoken}"


def mouse_click(button: str = "left", double: bool = False) -> tuple[bool, str]:
    """Click the mouse at current position."""
    try:
        pg = _get_pyautogui()
        if double:
            pg.doubleClick(button=button)
            return True, "Double clicked."
        else:
            pg.click(button=button)
            return True, f"{button.title()} clicked."
    except Exception as e:
        return False, f"Click failed: {e}"


def mouse_move(where: str) -> tuple[bool, str]:
    """Move mouse to a named position or coordinates."""
    try:
        import pyautogui
        screen_w, screen_h = pyautogui.size()
        t = where.strip().lower()

        positions = {
            "center":       (screen_w // 2, screen_h // 2),
            "top left":     (10, 10),
            "top right":    (screen_w - 10, 10),
            "bottom left":  (10, screen_h - 10),
            "bottom right": (screen_w - 10, screen_h - 10),
            "top":          (screen_w // 2, 10),
            "bottom":       (screen_w // 2, screen_h - 10),
            "left":         (10, screen_h // 2),
            "right":        (screen_w - 10, screen_h // 2),
        }

        for name, (x, y) in positions.items():
            if name in t:
                pyautogui.moveTo(x, y, duration=0.3)
                return True, f"Mouse moved to {name}."

        # Try "x y" coordinates
        nums = re.findall(r"\d+", t)
        if len(nums) >= 2:
            pyautogui.moveTo(int(nums[0]), int(nums[1]), duration=0.3)
            return True, f"Mouse moved to {nums[0]}, {nums[1]}."

        return False, "I didn't understand where to move the mouse."
    except Exception as e:
        return False, f"Mouse move failed: {e}"


def scroll(direction: str = "down", amount: int = 3) -> tuple[bool, str]:
    """Scroll up or down."""
    try:
        pg = _get_pyautogui()
        clicks = amount if direction == "up" else -amount
        pg.scroll(clicks)
        return True, f"Scrolled {direction}."
    except Exception as e:
        return False, f"Scroll failed: {e}"
