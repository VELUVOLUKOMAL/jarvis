#!/usr/bin/env python3
"""
JARVIS — Personal AI Assistant (like Siri for Windows)
Say "Jarvis" or double-clap → it wakes up → give any command.
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
log = logging.getLogger("jarvis")

# ─── State machine ───────────────────────────────────────────────────────────
class State(enum.Enum):
    SLEEPING = "sleeping"   # only listening for wake word / clap
    AWAKE    = "awake"      # listening for a command
    ACTING   = "acting"     # executing a command

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
            set_hud_status("Acting...")
    except Exception:
        pass


# ─── Config ──────────────────────────────────────────────────────────────────
WAKE_WORDS      = [w.strip().lower() for w in (os.environ.get("WAKE_WORDS") or "jarvis,javris,jarves,jarv").split(",")]
WAKE_RESPONSE   = (os.environ.get("JARVIS_WAKE_RESPONSE") or "Yes sir?").strip()
TRIGGER_MODE    = (os.environ.get("TRIGGER_MODE") or "both").strip().lower()
COMMAND_TIMEOUT = float(os.environ.get("COMMAND_TIMEOUT") or "6")

# Audio
SAMPLE_RATE = 16000
BLOCK_MS    = 40
CHANNELS    = 1

# Clap detection
SPIKE_RATIO       = 7.0
COOLDOWN_S        = 0.45
MIN_DOUBLE_GAP_S  = 0.05
MAX_DOUBLE_GAP_S  = 0.35
RETRIGGER_RATIO   = 0.55
NOISE_FLOOR_ALPHA = 0.992
MIN_RMS           = 0.012
QUIET_GATE_MULT   = 2.2

# ElevenLabs
EL_API_KEY  = (os.environ.get("ELEVENLABS_API_KEY") or "").strip()
EL_VOICE_ID = (os.environ.get("ELEVENLABS_VOICE_ID") or "").strip()
EL_MODEL    = (os.environ.get("ELEVENLABS_MODEL_ID") or "eleven_multilingual_v2").strip()
EL_FORMAT   = (os.environ.get("ELEVENLABS_OUTPUT_FORMAT") or "pcm_24000").strip()

# Voice activity detection
SILENCE_TIMEOUT_S    = 1.2
MAX_SPEECH_DURATION_S = 6.0
MIN_SPEECH_RMS       = 0.01

_jarvis_active = True
_jarvis_active_lock = threading.Lock()

def is_jarvis_active() -> bool:
    with _jarvis_active_lock:
        return _jarvis_active

def set_jarvis_active(val: bool) -> None:
    global _jarvis_active
    with _jarvis_active_lock:
        _jarvis_active = val
    log.info("Jarvis active state → %s", val)

class RollingVAD:
    def __init__(self, size: int = 150, percentile: int = 20, multiplier: float = 3.0, min_rms: float = 0.01):
        self.size = size
        self.percentile = percentile
        self.multiplier = multiplier
        self.min_rms = min_rms
        self.history = []

    def calibrate(self, device_idx: int, blocksize: int) -> None:
        log.info("Calibrating background noise levels...")
        try:
            with sd.InputStream(device=device_idx, samplerate=SAMPLE_RATE, channels=CHANNELS,
                                dtype="float32", blocksize=blocksize) as stream:
                for _ in range(30):  # ~1.2 seconds of history
                    data, _ = stream.read(blocksize)
                    self.history.append(rms_mono(data))
        except Exception as e:
            log.warning("Calibration warning: %s. Using default baseline.", e)
            self.history = [self.min_rms / 3.0] * 30

    def add(self, level: float) -> None:
        self.history.append(level)
        if len(self.history) > self.size:
            self.history.pop(0)

    def get_threshold(self) -> float:
        if not self.history:
            return self.min_rms
        noise_floor = np.percentile(self.history, self.percentile)
        return max(noise_floor * self.multiplier, self.min_rms)

# ─── Audio helpers ───────────────────────────────────────────────────────────

def block_samples() -> int:
    return max(int(SAMPLE_RATE * BLOCK_MS / 1000), 1)

def rms_mono(block: np.ndarray) -> float:
    b = np.mean(block.astype(np.float64), axis=1) if block.ndim > 1 else block.astype(np.float64)
    return float(np.sqrt(np.mean(b ** 2))) if b.size else 0.0

def _input_devices():
    return [(i, d) for i, d in enumerate(sd.query_devices()) if d["max_input_channels"] >= 1]

def _probe_rms(device: int, blocksize: int) -> float | None:
    try:
        with sd.InputStream(device=device, samplerate=SAMPLE_RATE, channels=CHANNELS,
                            dtype="float32", blocksize=blocksize) as s:
            peak = 0.0
            deadline = time.monotonic() + 0.5
            while time.monotonic() < deadline:
                data, _ = s.read(blocksize)
                peak = max(peak, rms_mono(data))
            return peak
    except sd.PortAudioError:
        return None

def choose_input_device(blocksize: int) -> int:
    log.info("Audio devices:\n%s", sd.query_devices())
    override = (os.environ.get("JARVIS_INPUT_DEVICE") or "").strip()
    if override:
        idx = int(override) if override.isdigit() else next(
            (i for i, d in _input_devices() if override.lower() in d["name"].lower()), 0)
        log.info("Using configured mic [%d]: %s", idx, sd.query_devices(idx)["name"])
        return idx
    default = sd.default.device[0]
    if default is not None and default >= 0:
        peak = _probe_rms(default, blocksize)
        if peak is not None and peak >= 0.001:
            log.info("Using default mic [%d]: %s", default, sd.query_devices(default)["name"])
            return default
    best_idx, best_peak = None, -1.0
    for idx, _ in _input_devices():
        if idx == default:
            continue
        p = _probe_rms(idx, blocksize)
        if p is not None and p > best_peak:
            best_peak, best_idx = p, idx
    if best_idx is not None and best_peak >= 0.001:
        log.info("Auto-selected mic [%d]: %s", best_idx, sd.query_devices(best_idx)["name"])
        return best_idx
    return default if default is not None and default >= 0 else _input_devices()[0][0]

# ─── TTS ─────────────────────────────────────────────────────────────────────

def _el_pcm_rate() -> int:
    if EL_FORMAT.startswith("pcm_"):
        try:
            return int(EL_FORMAT.split("_")[1])
        except (ValueError, IndexError):
            pass
    return 24000

def _play_pcm(raw: bytes, rate: int) -> None:
    arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    sd.play(arr, rate)
    sd.wait()

def speak_offline(text: str) -> None:
    if sys.platform == "win32":
        try:
            esc = text.replace("'", "''").replace('"', '`"')
            cmd = (
                f"Add-Type -AssemblyName System.Speech; "
                f"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                f"$s.Rate = 2; $s.Speak('{esc}')"
            )
            # Run PowerShell TTS in background so it never hangs Python
            subprocess.Popen(["powershell", "-NoProfile", "-Command", cmd],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # Sleep approximate speech duration so logs and sessions remain aligned
            words = len(text.split())
            time.sleep(max(1.2, words * 0.35))
            return
        except Exception as e:
            log.warning("PowerShell TTS failed: %s", e)

    if pyttsx3:
        try:
            engine = pyttsx3.init()
            voices = engine.getProperty("voices")
            for v in voices:
                if "male" in v.name.lower() or "david" in v.name.lower():
                    engine.setProperty("voice", v.id)
                    break
            engine.setProperty("rate", 175)
            engine.say(text)
            engine.runAndWait()
            return
        except Exception as e:
            log.warning("pyttsx3 failed: %s", e)

    print(f"\n[JARVIS]: {text}\n")


def speak(text: str) -> None:
    """Speak text — ElevenLabs (direct API with strict 4s timeout) if available, else offline fallback."""
    log.info("Speaking: %r", text)
    try:
        from commands.hud_gui import log_to_hud
        log_to_hud("JARVIS", text)
    except Exception:
        pass

    if not EL_API_KEY or not EL_VOICE_ID:
        speak_offline(text)
        return

    # Check cache
    key = f"{text}|{EL_VOICE_ID}|{EL_MODEL}|{EL_FORMAT}".encode()
    digest = hashlib.sha256(key).hexdigest()[:24]
    cache_dir = Path(__file__).parent / ".cache" / "jarvis_tts"
    cache_path = cache_dir / f"{digest}.wav"
    if cache_path.is_file():
        try:
            with wave.open(str(cache_path), "rb") as wf:
                raw = wf.readframes(wf.getnframes())
                rate = wf.getframerate()
            _play_pcm(raw, rate)
            return
        except Exception:
            pass

    # Direct API request with strict 4-second timeout to prevent lag
    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{EL_VOICE_ID}?output_format={EL_FORMAT}"
        headers = {
            "xi-api-key": EL_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "text": text,
            "model_id": EL_MODEL,
        }
        r = requests.post(url, json=payload, headers=headers, timeout=4)
        r.raise_for_status()
        raw = r.content
    except Exception as e:
        log.warning("ElevenLabs failed or timed out: %s — using offline fallback.", e)
        speak_offline(text)
        return

    if not raw:
        speak_offline(text)
        return

    rate = _el_pcm_rate()
    # Save to cache
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        with wave.open(str(cache_path), "wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(rate)
            wf.writeframes(raw)
    except Exception:
        pass
    _play_pcm(raw, rate)

# ─── Speech recognition ──────────────────────────────────────────────────────

def _transcribe_frames(frames: list, rate: int) -> str | None:
    if sr is None:
        return None
    try:
        audio_np = np.concatenate(frames, axis=0)
        audio_i16 = (audio_np * 32767).astype(np.int16)
        audio_data = sr.AudioData(audio_i16.tobytes(), rate, 2)
        recognizer = sr.Recognizer()
        return recognizer.recognize_google(audio_data).lower().strip()
    except sr.UnknownValueError:
        return None
    except Exception as e:
        log.warning("Transcription error: %s", e)
        return None

def listen_for_speech(device_idx: int, timeout: float = 6.0, after_speech_silence: float = 1.2) -> str | None:
    """
    Listen on device_idx for up to `timeout` seconds.
    Returns transcribed text or None.
    """
    if sr is None:
        log.warning("SpeechRecognition not installed.")
        return None

    blocksize = block_samples()
    vad = RollingVAD(size=150, percentile=20, multiplier=3.0, min_rms=MIN_SPEECH_RMS)
    vad.calibrate(device_idx, blocksize)

    recording = False
    speech_frames: list = []
    silence_start: float | None = None
    speech_start: float | None = None
    deadline = time.monotonic() + timeout

    try:
        with sd.InputStream(device=device_idx, samplerate=SAMPLE_RATE, channels=CHANNELS,
                            dtype="float32", blocksize=blocksize) as stream:
            while time.monotonic() < deadline:
                data, _ = stream.read(blocksize)
                level = rms_mono(data)
                now = time.monotonic()
                vad_threshold = vad.get_threshold()

                if not recording:
                    vad.add(level)
                    if level >= vad_threshold:
                        recording = True
                        speech_frames = [data.copy()]
                        speech_start = now
                        silence_start = None
                else:
                    speech_frames.append(data.copy())
                    duration = now - (speech_start or now)
                    if level < vad_threshold:
                        if silence_start is None:
                            silence_start = now
                        elif (now - silence_start) >= after_speech_silence:
                            if duration >= 0.3:
                                break  # natural end of speech
                            recording = False
                            speech_frames = []
                    else:
                        silence_start = None
                    if duration >= MAX_SPEECH_DURATION_S:
                        break
    except Exception as e:
        log.warning("listen_for_speech error: %s", e)
        return None

    if not speech_frames:
        return None
    return _transcribe_frames(speech_frames, SAMPLE_RATE)

# ─── Command router ──────────────────────────────────────────────────────────

# Command verbs used to detect compound command boundaries
_COMPOUND_SPLIT_MARKERS = [
    " and open ", " and create ", " and write ", " and run ",
    " and launch ", " and start ", " and close ", " and search ",
    " then open ", " then create ", " then write ", " then run ",
    " then launch ", " then start ",
]


def _split_compound_command(text: str) -> list[str]:
    """Split a compound voice command into individual sub-commands."""
    t_lower = text.lower()
    for marker in _COMPOUND_SPLIT_MARKERS:
        if marker in t_lower:
            idx = t_lower.find(marker)
            first = text[:idx].strip()
            second = text[idx + len(marker):].strip()
            # Recursively split the second part too
            rest = _split_compound_command(second)
            if first:
                return [first] + rest
    return [text] if text.strip() else []


def handle_command(text: str) -> None:
    """Parse and execute a voice command. Supports compound 'and/then' chaining."""
    # Handle compound commands (e.g. "open VS code and create test.py and write code")
    parts = _split_compound_command(text)
    if len(parts) > 1:
        for part in parts:
            if part.strip():
                _execute_single_command(part.strip())
        return
    _execute_single_command(text)


def _execute_single_command(text: str) -> None:
    """Parse and execute a single voice command."""
    from commands.nlp_parser import parse_command
    result = parse_command(text)
    intent = result["intent"]
    params = result["params"]
    log.info("Intent: %s | Params: %s", intent, params)

    # ── Custom Hackathon Intents ──────────────────────────────────────────────
    if intent == "close_app":
        from commands.app_launcher import close_app
        ok, msg = close_app(params["app"])
        speak(msg)
        return

    if intent == "search_software":
        from commands.app_launcher import search_installed_software
        ok, msg = search_installed_software(params["query"])
        speak(msg)
        return

    if intent == "create_folder":
        from commands.file_manager import create_folder
        ok, msg = create_folder(params["folder"])
        speak(msg)
        return

    if intent == "delete_file":
        from commands.file_manager import delete_file_with_confirmation
        from commands.hud_gui import _hud_instance
        def run_hud_update(action_type, data):
            from commands.hud_gui import trigger_hud_confirmation
            if action_type == "ASK_CONFIRMATION":
                trigger_hud_confirmation(data[0], data[1])
        ok, msg = delete_file_with_confirmation(params["file"], update_hud_fn=run_hud_update if _hud_instance else None)
        speak(msg)
        return

    if intent == "rename_file":
        from commands.file_manager import rename_file
        ok, msg = rename_file(params["old_name"], params["new_name"])
        speak(msg)
        return

    if intent == "move_file":
        from commands.file_manager import move_file
        ok, msg = move_file(params["file"], params["folder"])
        speak(msg)
        return

    if intent == "install_software":
        from commands.app_launcher import install_software_workflow
        from commands.hud_gui import _hud_instance, start_hud_plan, set_hud_plan_step_active, set_hud_plan_step_complete, trigger_hud_setup_window
        def run_hud_update(action_type, data):
            if action_type == "PLAN_START":
                start_hud_plan(data)
            elif action_type == "PLAN_STEP_ACTIVE":
                set_hud_plan_step_active(data)
            elif action_type == "PLAN_STEP_COMPLETE":
                set_hud_plan_step_complete(data)
            elif action_type == "SHOW_SETUP_WINDOW":
                trigger_hud_setup_window(data)
        ok, msg = install_software_workflow(params["software"], update_hud_fn=run_hud_update if _hud_instance else None)
        speak(msg)
        return

    if intent == "toggle_wifi":
        from commands.system_control import toggle_wifi
        ok, msg = toggle_wifi(params["state"])
        speak(msg)
        return

    if intent == "toggle_bluetooth":
        from commands.system_control import toggle_bluetooth
        ok, msg = toggle_bluetooth(params["state"])
        speak(msg)
        return

    if intent == "toggle_dark_mode":
        from commands.system_control import toggle_dark_mode
        ok, msg = toggle_dark_mode(params["state"])
        speak(msg)
        return

    if intent == "start_coding_session":
        from commands.workflow_agent import start_coding_session_workflow
        from commands.hud_gui import _hud_instance, start_hud_plan, set_hud_plan_step_active, set_hud_plan_step_complete
        def run_hud_update(action_type, data):
            if action_type == "PLAN_START":
                start_hud_plan(data)
            elif action_type == "PLAN_STEP_ACTIVE":
                set_hud_plan_step_active(data)
            elif action_type == "PLAN_STEP_COMPLETE":
                set_hud_plan_step_complete(data)
        ok, msg = start_coding_session_workflow(update_hud_fn=run_hud_update if _hud_instance else None)
        speak(msg)
        return

    if intent == "file_zip_email":
        from commands.workflow_agent import file_zip_email_workflow
        from commands.hud_gui import _hud_instance, start_hud_plan, set_hud_plan_step_active, set_hud_plan_step_complete, trigger_hud_email_window
        def run_hud_update(action_type, data):
            if action_type == "PLAN_START":
                start_hud_plan(data)
            elif action_type == "PLAN_STEP_ACTIVE":
                set_hud_plan_step_active(data)
            elif action_type == "PLAN_STEP_COMPLETE":
                set_hud_plan_step_complete(data)
            elif action_type == "SHOW_EMAIL_TRANSMISSION":
                trigger_hud_email_window(data)
        ok, msg = file_zip_email_workflow(update_hud_fn=run_hud_update if _hud_instance else None)
        speak(msg)
        return

    if intent == "going_home":
        from commands.workflow_agent import going_home_workflow
        from commands.hud_gui import _hud_instance, start_hud_plan, set_hud_plan_step_active, set_hud_plan_step_complete, trigger_hud_confirmation
        def run_hud_update(action_type, data):
            if action_type == "PLAN_START":
                start_hud_plan(data)
            elif action_type == "PLAN_STEP_ACTIVE":
                set_hud_plan_step_active(data)
            elif action_type == "PLAN_STEP_COMPLETE":
                set_hud_plan_step_complete(data)
            elif action_type == "ASK_CONFIRMATION":
                trigger_hud_confirmation(data[0], data[1])
        ok, msg = going_home_workflow(update_hud_fn=run_hud_update if _hud_instance else None)
        speak(msg)
        return

    if intent == "vscode_write_code":
        from commands.vs_code_agent import write_code_in_vscode
        from commands.hud_gui import _hud_instance, start_hud_plan, set_hud_plan_step_active, set_hud_plan_step_complete
        def run_hud_update(action_type, data):
            if action_type == "PLAN_START":
                start_hud_plan(data)
            elif action_type == "PLAN_STEP_ACTIVE":
                set_hud_plan_step_active(data)
            elif action_type == "PLAN_STEP_COMPLETE":
                set_hud_plan_step_complete(data)
        ok, msg = write_code_in_vscode(params["filename"], params["description"], update_hud_fn=run_hud_update if _hud_instance else None)
        speak(msg)
        return

    # ── Dismiss ──────────────────────────────────────────────────────────────
    if intent == "sleep":
        speak("Going to sleep. Call me when you need me, sir.")
        return

    # ── Jarvis Active State control / Termination ─────────────────────────────
    if intent == "jarvis_off":
        speak("Saving your work and shutting down completely. Goodbye, sir.")
        try:
            from commands.system_control import save_all_unsaved_files
            save_all_unsaved_files()
        except Exception:
            pass
        try:
            from commands.ai_brain import _save_history
        except Exception:
            pass
        time.sleep(1.5)
        os._exit(0)

    if intent == "jarvis_on":
        set_jarvis_active(True)
        speak("Jarvis is now active and online, sir.")
        return

    # ── Greeting ──────────────────────────────────────────────────────────────
    if intent == "greeting":
        speak("Yes sir, I am listening. What can I do for you?")
        return

    # ── WhatsApp Call/Message ─────────────────────────────────────────────────
    if intent == "whatsapp_action":
        from commands.web_handler import whatsapp_action
        target = params.get("target", "")
        ok, msg = whatsapp_action(target)
        speak(msg)
        return

    if intent == "thanks":
        speak("Anytime, sir.")
        return

    # ── Time / Date ───────────────────────────────────────────────────────────
    if intent == "time":
        from commands.system_control import get_time
        _, msg = get_time()
        speak(msg); return

    if intent == "date":
        from commands.system_control import get_date
        _, msg = get_date()
        speak(msg); return

    # ── Volume ────────────────────────────────────────────────────────────────
    if intent == "volume_up":
        from commands.system_control import volume_up
        _, msg = volume_up(params.get("amount", 10))
        speak(msg); return

    if intent == "volume_down":
        from commands.system_control import volume_down
        _, msg = volume_down(params.get("amount", 10))
        speak(msg); return

    if intent == "mute":
        from commands.system_control import mute
        _, msg = mute()
        speak(msg); return

    if intent == "unmute":
        from commands.system_control import unmute
        _, msg = unmute()
        speak(msg); return

    # ── Brightness ────────────────────────────────────────────────────────────
    if intent == "brightness_up":
        from commands.system_control import brightness_up
        _, msg = brightness_up(params.get("amount", 10))
        speak(msg); return

    if intent == "brightness_down":
        from commands.system_control import brightness_down
        _, msg = brightness_down(params.get("amount", 10))
        speak(msg); return

    # ── Screenshot ────────────────────────────────────────────────────────────
    if intent == "screenshot":
        from commands.system_control import screenshot
        _, msg = screenshot()
        speak(msg); return

    # ── Lock / Power ──────────────────────────────────────────────────────────
    if intent == "lock":
        from commands.system_control import lock_screen
        speak("Locking the screen, sir.")
        lock_screen(); return

    if intent == "shutdown":
        speak("Saving all open files before shutting down, sir.")
        try:
            from commands.system_control import save_all_unsaved_files
            save_all_unsaved_files()
        except Exception:
            pass
        from commands.system_control import shutdown_pc
        _, msg = shutdown_pc()
        speak(msg); return

    if intent == "restart":
        from commands.system_control import restart_pc
        _, msg = restart_pc()
        speak(msg); return

    if intent == "pc_sleep":
        from commands.system_control import sleep_pc
        _, msg = sleep_pc()
        speak(msg); return

    # ── Media ─────────────────────────────────────────────────────────────────
    if intent == "media_play":
        from commands.media_control import media_play_pause
        _, msg = media_play_pause()
        speak(msg); return

    if intent == "media_pause":
        from commands.media_control import media_play_pause
        _, msg = media_play_pause()
        speak("Paused."); return

    if intent == "media_next":
        from commands.media_control import media_next
        _, msg = media_next()
        speak(msg); return

    if intent == "media_prev":
        from commands.media_control import media_prev
        _, msg = media_prev()
        speak(msg); return

    # ── Window management ─────────────────────────────────────────────────────
    if intent == "close_window":
        from commands.system_control import close_foreground_window
        _, msg = close_foreground_window()
        speak(msg); return

    if intent == "minimize_window":
        from commands.system_control import minimize_foreground_window
        _, msg = minimize_foreground_window()
        speak(msg); return

    if intent == "maximize_window":
        from commands.system_control import maximize_foreground_window
        _, msg = maximize_foreground_window()
        speak(msg); return

    # ── Web ────────────────────────────────────────────────────────────────────
    if intent == "youtube_search":
        from commands.web_handler import youtube_search
        _, msg = youtube_search(params["query"])
        speak(msg); return

    if intent == "google_search":
        from commands.web_handler import google_search
        _, msg = google_search(params["query"])
        speak(msg); return

    if intent == "open_website":
        from commands.web_handler import open_website
        _, msg = open_website(params["url"], params.get("name", ""))
        speak(msg); return

    # ── Voice unlock ──────────────────────────────────────────────────────────
    if intent == "voice_unlock":
        unlock_code = (os.environ.get("VOICE_UNLOCK_CODE") or "").strip().lower()
        given_code = params.get("code", "").strip().lower()
        if not unlock_code:
            speak("No unlock code is set. Please run setup autologin to configure one.")
        elif given_code == unlock_code:
            # Send Win+L then type the Windows password to dismiss lock screen
            win_password = (os.environ.get("WINDOWS_PASSWORD") or "").strip()
            speak("Unlocking.")
            import ctypes, time as _t
            ctypes.windll.user32.keybd_event(0x5B, 0, 0, 0)   # Win down
            ctypes.windll.user32.keybd_event(0x4C, 0, 0, 0)   # L down
            ctypes.windll.user32.keybd_event(0x4C, 0, 0x0002, 0)  # L up
            ctypes.windll.user32.keybd_event(0x5B, 0, 0x0002, 0)  # Win up
            if win_password:
                _t.sleep(1.5)
                import subprocess
                ps = f"Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('{win_password}{{ENTER}}')"
                subprocess.Popen(["powershell", "-NoProfile", "-Command", ps],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            speak("Incorrect unlock code, sir.")
        return

    # ── Set volume to exact % ─────────────────────────────────────────────────
    if intent == "set_volume":
        from commands.system_control import _set_master_volume_win32
        level = max(0, min(100, params.get("level", 50)))
        ok = _set_master_volume_win32(level / 100.0)
        speak(f"Volume set to {level} percent." if ok else "Could not set volume.")
        return

    # ── Cancel shutdown ───────────────────────────────────────────────────────
    if intent == "cancel_shutdown":
        from commands.system_control import cancel_shutdown
        _, msg = cancel_shutdown()
        speak(msg); return

    # ── Timer ─────────────────────────────────────────────────────────────────
    if intent == "set_timer":
        from commands.system_info import set_timer, parse_duration
        duration_str = params.get("duration_str", "")
        label = params.get("label", "Timer")
        secs = parse_duration(duration_str)
        if secs:
            _, msg = set_timer(secs, label, speak_fn=speak)
            speak(msg)
        else:
            speak("I didn't catch the duration. Try saying something like: set a timer for 5 minutes.")
        return

    if intent == "cancel_timer":
        from commands.system_info import cancel_timer
        _, msg = cancel_timer()
        speak(msg); return

    # ── System info ───────────────────────────────────────────────────────────
    if intent == "battery":
        from commands.system_info import get_battery
        _, msg = get_battery()
        speak(msg); return

    if intent == "cpu_ram":
        from commands.system_info import get_cpu_ram
        _, msg = get_cpu_ram()
        speak(msg); return

    if intent == "disk_space":
        from commands.system_info import get_disk_space
        _, msg = get_disk_space(params.get("drive", "C"))
        speak(msg); return

    if intent == "ip_address":
        from commands.system_info import get_ip
        _, msg = get_ip()
        speak(msg); return

    # ── File manager ──────────────────────────────────────────────────────────
    if intent == "open_folder":
        from commands.file_manager import open_folder
        _, msg = open_folder(params.get("folder", "desktop"))
        speak(msg); return

    if intent == "find_file":
        speak("Searching for that file, one moment.")
        from commands.file_manager import find_and_open
        ok, msg = find_and_open(params.get("name", ""))
        speak(msg); return

    # ── App ────────────────────────────────────────────────────────────────────
    if intent == "open_app":
        from commands.app_launcher import launch_app
        ok, msg = launch_app(params["app"])
        speak(msg); return

    # ── AI question ───────────────────────────────────────────────────────────
    if intent == "question":
        speak("Let me think about that.")
        from commands.ai_brain import ask
        answer = ask(params["query"])
        speak(answer); return

    # ── Run Ollama ────────────────────────────────────────────────────────────
    if intent == "run_ollama":
        from commands.app_launcher import run_ollama_in_cmd
        ok, msg = run_ollama_in_cmd()
        speak(msg); return

    # ── Create File ───────────────────────────────────────────────────────────
    if intent == "create_file":
        from commands.file_manager import create_file
        ok, msg = create_file(params.get("filename", ""), params.get("location", ""))
        speak(msg); return

    # ── Write Code to Last File ───────────────────────────────────────────────
    if intent == "write_code_to_file":
        speak("Generating code now, sir. One moment.")
        from commands.file_manager import write_code_to_last_file
        ok, msg = write_code_to_last_file(params.get("description", ""))
        speak(msg); return

    # ── Clear Chat History ────────────────────────────────────────────────────
    if intent == "clear_chat_history":
        from commands.ai_brain import clear_history
        msg = clear_history()
        speak(msg); return

    speak("I'm not sure how to do that yet, sir.")


# ─── Wake & command flow ──────────────────────────────────────────────────────

def wake_and_listen(device_idx: int, source: str) -> None:
    """Called when wake word or clap detected. Listens for commands in a session."""
    if get_state() != State.SLEEPING:
        log.info("[%s] Already awake — ignoring duplicate trigger.", source)
        return

    set_state(State.AWAKE)
    try:
        speak(WAKE_RESPONSE)
        session_timeout = float(os.environ.get("JARVIS_SESSION_TIMEOUT", "60"))
        session_end = time.monotonic() + session_timeout
        first_turn = True

        while time.monotonic() < session_end:
            if not first_turn:
                log.info("Session active. Listening for next command...")
            else:
                first_turn = False

            text = listen_for_speech(device_idx, timeout=COMMAND_TIMEOUT)
            if not text:
                log.info("No speech detected. Ending session.")
                break

            log.info("Session Command: %r", text)
            try:
                from commands.hud_gui import log_to_hud, set_hud_status
                log_to_hud("YOU", text)
                set_hud_status("Thinking...")
            except Exception:
                pass

            from commands.nlp_parser import parse_command
            parsed = parse_command(text)
            if parsed["intent"] in ("sleep", "jarvis_off"):
                set_state(State.ACTING)
                handle_command(text)
                break

            set_state(State.ACTING)
            handle_command(text)

            # Reset session timer after successful action
            session_end = time.monotonic() + session_timeout
            set_state(State.AWAKE)

    finally:
        set_state(State.SLEEPING)

# ─── Voice listener thread (wake word detection) ─────────────────────────────

def voice_listener_thread(device_idx: int) -> None:
    if sr is None:
        log.warning("SpeechRecognition not installed — voice wake disabled.")
        return

    blocksize = block_samples()
    log.info("Voice listener active. Say: %s", ", ".join(f'"{w}"' for w in WAKE_WORDS))

    # Initialize dynamic VAD and calibrate
    vad = RollingVAD(size=150, percentile=20, multiplier=3.0, min_rms=MIN_SPEECH_RMS)
    vad.calibrate(device_idx, blocksize)

    while True:
        try:
            with sd.InputStream(device=device_idx, samplerate=SAMPLE_RATE,
                                channels=CHANNELS, dtype="float32",
                                blocksize=blocksize) as stream:
                recording = False
                speech_frames: list = []
                silence_start: float | None = None
                speech_start: float | None = None

                while True:
                    # If not sleeping, don't compete for the mic
                    if get_state() != State.SLEEPING:
                        time.sleep(0.1)
                        continue

                    data, _ = stream.read(blocksize)
                    level = rms_mono(data)
                    now = time.monotonic()
                    vad_threshold = vad.get_threshold()

                    if not recording:
                        vad.add(level)
                        if level >= vad_threshold:
                            recording = True
                            speech_frames = [data.copy()]
                            speech_start = now
                    else:
                        speech_frames.append(data.copy())
                        duration = now - (speech_start or now)
                        if level < vad_threshold:
                            if silence_start is None:
                                silence_start = now
                            elif (now - silence_start) >= SILENCE_TIMEOUT_S:
                                if duration >= 0.2:
                                    frames_copy = list(speech_frames)
                                    threading.Thread(
                                        target=_check_wake_word,
                                        args=(frames_copy, device_idx),
                                        daemon=True,
                                    ).start()
                                recording = False
                                speech_frames = []
                                silence_start = None
                        else:
                            silence_start = None
                        if duration >= MAX_SPEECH_DURATION_S:
                            recording = False
                            speech_frames = []
                            silence_start = None

        except sd.PortAudioError as e:
            log.warning("Voice listener audio error: %s — retrying in 2s.", e)
            time.sleep(2)
        except Exception as e:
            log.warning("Voice listener error: %s — retrying in 2s.", e)
            time.sleep(2)


def _check_wake_word(frames: list, device_idx: int) -> None:
    if get_state() != State.SLEEPING:
        return
    text = _transcribe_frames(frames, SAMPLE_RATE)
    if text is None:
        return
    log.info("Heard: %r", text)

    # If currently deactivated, only listen for activation phrase
    if not is_jarvis_active():
        if any(ph in text for ph in ["jarvis on", "wake up", "activate", "turn on", "online"]):
            set_jarvis_active(True)
            log.info("Jarvis activated by voice command!")
            threading.Thread(
                target=speak,
                args=("Jarvis is now active and online, sir.",),
                daemon=True,
            ).start()
        return

    # Check for direct deactivation command ("jarvis off" or "turn off")
    if any(word in text for word in WAKE_WORDS) and any(off_w in text for off_w in ["off", "deactivate", "go offline", "turn off", "stop"]):
        log.info("Jarvis shutting down by voice command!")
        speak("Shutting down completely. Goodbye, sir.")
        time.sleep(1.5)
        os._exit(0)

    # Otherwise check normal wake words
    for word in WAKE_WORDS:
        if word in text:
            # Voice verification
            from commands.voice_profile import verify_speaker, is_enrolled
            if os.environ.get("VOICE_PROFILE_ENABLED", "true").lower() == "true" and is_enrolled():
                is_owner, score = verify_speaker(frames)
                if not is_owner:
                    log.warning("Wake rejected: Speaker not verified (score=%.4f)", score)
                    return
            log.info("Wake word '%s' detected and speaker verified!", word)
            threading.Thread(
                target=wake_and_listen,
                args=(device_idx, "voice"),
                daemon=True,
            ).start()
            return

# ─── Clap detection (main loop) ──────────────────────────────────────────────

def clap_loop(device_idx: int) -> int:
    blocksize = block_samples()
    noise_floor = 1e-4
    last_double = 0.0
    first_clap: float | None = None
    spike_armed = True

    log.info("Clap detector active (double-clap to wake).")

    try:
        with sd.InputStream(device=device_idx, samplerate=SAMPLE_RATE, 
                            channels=CHANNELS, dtype="float32",
                            blocksize=blocksize) as stream:
            while True:
                data, overflowed = stream.read(blocksize)
                if overflowed:
                    log.debug("Input overflow")

                # Skip clap detection when awake/acting
                if get_state() != State.SLEEPING:
                    time.sleep(0.01)
                    continue

                level = rms_mono(data)
                quiet_gate = noise_floor * QUIET_GATE_MULT
                if level < quiet_gate:
                    noise_floor = NOISE_FLOOR_ALPHA * noise_floor + (1 - NOISE_FLOOR_ALPHA) * level
                    noise_floor = max(noise_floor, 1e-7)

                threshold = max(noise_floor * SPIKE_RATIO, MIN_RMS)
                now = time.monotonic()
                retrigger_level = threshold * RETRIGGER_RATIO

                if level < retrigger_level:
                    spike_armed = True

                if spike_armed and level >= threshold and (now - last_double) >= COOLDOWN_S:
                    spike_armed = False
                    if first_clap is None:
                        first_clap = now
                    else:
                        gap = now - first_clap
                        if gap < MIN_DOUBLE_GAP_S:
                            pass
                        elif gap <= MAX_DOUBLE_GAP_S:
                            first_clap = None
                            last_double = now
                            log.info("Double clap! (gap=%.3fs)", gap)
                            threading.Thread(
                                target=wake_and_listen,
                                args=(device_idx, "clap"),
                                daemon=True,
                            ).start()
                        else:
                            first_clap = now

    except KeyboardInterrupt:
        log.info("Stopped.")
        return 0
    except sd.PortAudioError as e:
        log.error("Audio error: %s", e)
        return 1

# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    blocksize = block_samples()

    log.info("=" * 60)
    log.info("  JARVIS — Personal AI Assistant")
    log.info("  Trigger: %s", TRIGGER_MODE.upper())
    log.info("  Wake words: %s", ", ".join(f'"{w}"' for w in WAKE_WORDS))
    log.info("  ElevenLabs TTS: %s", "enabled" if EL_API_KEY and EL_VOICE_ID else "offline fallback")
    from commands.ai_brain import is_ollama_available, GEMINI_API_KEY as G_KEY
    log.info("  Gemini AI: %s", "enabled" if G_KEY else "disabled")
    log.info("  Ollama AI: %s", "available" if is_ollama_available() else "not running")
    log.info("  Press Ctrl+C to stop.")
    log.info("=" * 60)

    device_idx = choose_input_device(blocksize)

    # Startup greeting
    threading.Thread(
        target=speak,
        args=("Jarvis online. I'm listening for your command, sir.",),
        daemon=True,
    ).start()

    # Voice listener thread
    if TRIGGER_MODE in ("voice", "both"):
        threading.Thread(
            target=voice_listener_thread,
            args=(device_idx,),
            daemon=True,
        ).start()

    # Clap loop in background if needed
    if TRIGGER_MODE in ("clap", "both"):
        threading.Thread(
            target=clap_loop,
            args=(device_idx,),
            daemon=True,
        ).start()

    # Run HUD GUI on the main thread
    from commands.hud_gui import HUDApp
    
    def start_listening_cb():
        threading.Thread(target=wake_and_listen, args=(device_idx, "manual"), daemon=True).start()
        
    app = HUDApp(start_listening_callback=start_listening_cb, submit_command_callback=handle_command)
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
