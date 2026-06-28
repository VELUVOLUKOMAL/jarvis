"""
Screen Agent — Screenshot + Gemini Vision analysis + screen-aware actions.

Commands:
  "What am I looking at?"       → Screenshot + AI description
  "What's on my screen?"        → Same
  "Click the blue button"       → Vision locates + pyautogui clicks (no confirmation)
  "Fill this form with [data]"  → Vision reads form + types
  "Read this text"              → OCR via Gemini Vision
  "Find [element] on screen"    → Returns coordinates
"""
from __future__ import annotations

import base64
import io
import logging
import os
import time

log = logging.getLogger("jarvis.screen")


def _grab_screenshot_b64() -> tuple[str, object]:
    """Take a screenshot and return (base64_string, PIL_image)."""
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        return b64, img
    except ImportError:
        raise RuntimeError("Pillow not installed. Run: pip install pillow")


def _ask_gemini_vision(b64_image: str, prompt: str) -> str | None:
    """Send screenshot to Gemini Vision and return the response."""
    import requests
    gemini_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not gemini_key:
        return None

    # Use gemini-1.5-flash which supports vision
    model = "gemini-1.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"

    payload = {
        "contents": [{
            "role": "user",
            "parts": [
                {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": b64_image,
                    }
                },
                {"text": prompt}
            ]
        }],
        "generationConfig": {
            "maxOutputTokens": 300,
            "temperature": 0.2,
        }
    }

    try:
        r = requests.post(url, json=payload, timeout=20)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        log.warning("Gemini Vision failed: %s", e)
        return None


def describe_screen() -> tuple[bool, str]:
    """Describe what's currently on screen."""
    try:
        b64, _ = _grab_screenshot_b64()
    except Exception as e:
        return False, f"Could not take screenshot: {e}"

    prompt = (
        "You are Jarvis, an AI assistant. Describe what you see on this computer screen "
        "in 2-3 concise sentences. Focus on the main application, content visible, and any "
        "notable elements. Be conversational, not technical. No markdown."
    )
    answer = _ask_gemini_vision(b64, prompt)
    if answer:
        return True, answer
    return False, "I couldn't analyze the screen right now. Gemini Vision may be unavailable."


def read_screen_text() -> tuple[bool, str]:
    """Extract and read text from the current screen."""
    try:
        b64, _ = _grab_screenshot_b64()
    except Exception as e:
        return False, f"Could not take screenshot: {e}"

    prompt = (
        "Read and transcribe all visible text on this screen. "
        "Focus on the main content area. Keep it concise (under 5 sentences). No markdown."
    )
    answer = _ask_gemini_vision(b64, prompt)
    if answer:
        return True, answer
    return False, "I couldn't read the screen text right now."


def find_and_click(element_description: str) -> tuple[bool, str]:
    """
    Use Gemini Vision to locate a UI element and click it immediately.
    No confirmation — clicks directly as per user preference.
    """
    try:
        import pyautogui
    except ImportError:
        return False, "pyautogui not installed. Run: pip install pyautogui"

    try:
        b64, img = _grab_screenshot_b64()
        width, height = img.size
    except Exception as e:
        return False, f"Screenshot failed: {e}"

    prompt = (
        f"I need to click on: '{element_description}' on this screen. "
        f"The screen is {width}x{height} pixels. "
        f"Find this element and respond with ONLY two numbers: X Y (pixel coordinates of the center). "
        f"Example: 850 420. If you cannot find it, respond with: NOT_FOUND"
    )
    answer = _ask_gemini_vision(b64, prompt)
    if not answer:
        return False, "I couldn't analyze the screen to find that element."

    if "NOT_FOUND" in answer.upper():
        return False, f"I couldn't find '{element_description}' on the screen."

    # Parse coordinates
    import re
    nums = re.findall(r"\d+", answer)
    if len(nums) >= 2:
        x, y = int(nums[0]), int(nums[1])
        # Safety clamp to screen bounds
        x = max(0, min(x, width - 1))
        y = max(0, min(y, height - 1))
        try:
            pyautogui.click(x, y)
            log.info("Clicked at (%d, %d) for: %s", x, y, element_description)
            return True, f"Clicked on {element_description}."
        except Exception as e:
            return False, f"Click failed: {e}"

    return False, f"Couldn't parse screen coordinates from AI response."


def fill_form_field(field_description: str, value: str) -> tuple[bool, str]:
    """Click a form field and type a value."""
    try:
        import pyautogui
    except ImportError:
        return False, "pyautogui not installed."

    ok, msg = find_and_click(field_description)
    if not ok:
        return False, msg

    time.sleep(0.3)
    # Clear existing content and type new value
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyautogui.typewrite(value, interval=0.04)
    return True, f"Filled {field_description} with {value}."


def save_screenshot(speak_fn=None) -> tuple[bool, str]:
    """Save a screenshot to Desktop."""
    import os
    from datetime import datetime
    from pathlib import Path
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
        fname = f"jarvis_screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        fpath = desktop / fname
        img.save(str(fpath))
        return True, f"Screenshot saved to Desktop as {fname}."
    except Exception as e:
        return False, f"Screenshot failed: {e}"
