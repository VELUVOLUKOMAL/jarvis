"""
Text Input Overlay — Type commands to JARVIS via keyboard (quiet mode).

Activated by hotkey Ctrl+Shift+J or by saying "text mode" / "type mode".
A sleek overlay appears, user types a command and presses Enter.
JARVIS processes it exactly like a voice command.
"""
from __future__ import annotations

import logging
import threading
import tkinter as tk
from tkinter import font as tkfont

log = logging.getLogger("jarvis.overlay")

_overlay_active = False
_overlay_lock   = threading.Lock()


class TextOverlay:
    """
    A minimal floating input bar — Iron Man HUD style.
    """

    COLORS = {
        "bg":       "#060d1f",
        "input_bg": "#0d1b38",
        "border":   "#00d4ff",
        "text":     "#e2e8f0",
        "accent":   "#00d4ff",
        "muted":    "#475569",
        "prompt":   "#7c3aed",
    }

    def __init__(self, command_callback):
        """
        command_callback: called with the typed text string when user presses Enter.
        """
        self.callback = command_callback
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.95)
        self.root.configure(bg=self.COLORS["bg"])

        # Center horizontally, place near bottom of screen
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w, h = 600, 70
        x = (sw - w) // 2
        y = sh - 140
        self.root.geometry(f"{w}x{h}+{x}+{y}")

        self._build_ui()
        self.root.bind("<Escape>", lambda e: self._close())
        self.root.bind("<FocusOut>", lambda e: self._close())

    def _build_ui(self):
        C = self.COLORS

        # Outer border frame
        border_frame = tk.Frame(self.root, bg=C["border"], padx=1, pady=1)
        border_frame.pack(fill="both", expand=True)

        inner = tk.Frame(border_frame, bg=C["bg"])
        inner.pack(fill="both", expand=True)

        # Top row: icon + label
        top = tk.Frame(inner, bg=C["bg"], pady=2)
        top.pack(fill="x", padx=10)

        tk.Label(
            top, text="⚡ JARVIS",
            bg=C["bg"], fg=C["accent"],
            font=("Consolas", 8, "bold")
        ).pack(side="left")

        tk.Label(
            top, text="Press ESC to cancel",
            bg=C["bg"], fg=C["muted"],
            font=("Consolas", 7)
        ).pack(side="right")

        # Input row
        input_frame = tk.Frame(inner, bg=C["input_bg"], pady=4, padx=8)
        input_frame.pack(fill="x", padx=8, pady=(0, 6))

        tk.Label(
            input_frame, text=">",
            bg=C["input_bg"], fg=C["prompt"],
            font=("Consolas", 14, "bold")
        ).pack(side="left", padx=(0, 6))

        self.entry_var = tk.StringVar()
        self.entry = tk.Entry(
            input_frame,
            textvariable=self.entry_var,
            bg=C["input_bg"],
            fg=C["text"],
            insertbackground=C["accent"],
            relief="flat",
            font=("Consolas", 13),
            bd=0,
        )
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", self._submit)
        self.entry.focus_force()

    def _submit(self, event=None):
        text = self.entry_var.get().strip()
        self._close()
        if text and self.callback:
            threading.Thread(target=self.callback, args=(text,), daemon=True).start()

    def _close(self):
        global _overlay_active
        with _overlay_lock:
            _overlay_active = False
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self):
        self.root.mainloop()


# ─── Public API ───────────────────────────────────────────────────────────────

def open_text_overlay(command_callback) -> None:
    """Open the text input overlay. Non-blocking (runs in thread)."""
    global _overlay_active
    with _overlay_lock:
        if _overlay_active:
            return
        _overlay_active = True

    def _run():
        try:
            overlay = TextOverlay(command_callback)
            overlay.run()
        except Exception as e:
            log.warning("Overlay error: %s", e)
        finally:
            global _overlay_active
            with _overlay_lock:
                _overlay_active = False

    threading.Thread(target=_run, daemon=True).start()


def setup_hotkey(command_callback) -> bool:
    """
    Register Ctrl+Shift+J as a global hotkey to open the overlay.
    Requires: pip install keyboard
    Returns True if hotkey registered successfully.
    """
    try:
        import keyboard
        keyboard.add_hotkey(
            "ctrl+shift+j",
            lambda: open_text_overlay(command_callback),
            suppress=False,
        )
        log.info("Global hotkey Ctrl+Shift+J registered for text input overlay.")
        return True
    except ImportError:
        log.info("'keyboard' package not installed — hotkey disabled. pip install keyboard")
        return False
    except Exception as e:
        log.warning("Hotkey registration failed: %s", e)
        return False
