#!/usr/bin/env python3
"""
HEY — AI CEO Operating System
Say "Hey" to wake up the system. Give startup commands.
Controls your entire startup platform end-to-end.
"""
from __future__ import annotations

import enum
import hashlib
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
import wave
from pathlib import Path

from dotenv import load_dotenv
import numpy as np
import sounddevice as sd
import requests

try:
    import speech_recognition as sr
except ImportError:
    sr = None

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

load_dotenv(Path(__file__).resolve().parent / ".env")

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("hey")

# ─── State machine ───────────────────────────────────────────────────────────
class State(enum.Enum):
    SLEEPING = "sleeping"
    AWAKE    = "awake"
    ACTING   = "acting"

_state = State.SLEEPING
_state_lock = threading.Lock()

def get_state() -> State:
    with _state_lock:
        return _state

def set_state(s: State) -> None:
    global _state
    with _state_lock:
        _state = s
    log.info("State → %s", s.value)
    try:
        from commands.hud_gui import set_hud_status
        if s == State.SLEEPING:
            set_hud_status("Sleeping")
        elif s == State.AWAKE:
            set_hud_status("Listening...")
        elif s == State.ACTING:
            set_hud_status("Executing...")
    except Exception:
        pass
