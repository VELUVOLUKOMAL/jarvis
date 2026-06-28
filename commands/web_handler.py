"""
Web Handler — Opens websites, does YouTube/Google searches.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import urllib.parse
import webbrowser

log = logging.getLogger("jarvis.web_handler")


def _chrome_exe() -> str | None:
    prog = os.environ.get("ProgramFiles", r"C:\Program Files")
    prog86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    for base in (prog, prog86):
        p = os.path.join(base, "Google", "Chrome", "Application", "chrome.exe")
        if os.path.isfile(p):
            return p
    return shutil.which("google-chrome") or shutil.which("chrome")


def _open_url(url: str) -> None:
    chrome = _chrome_exe()
    if chrome:
        try:
            kw: dict = {"args": [chrome, url], "stdin": subprocess.DEVNULL,
                        "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
            if sys.platform == "win32":
                kw["creationflags"] = subprocess.CREATE_NO_WINDOW
            subprocess.Popen(**kw)
            return
        except OSError as e:
            log.warning("Chrome launch failed: %s", e)
    webbrowser.open(url)


def open_website(url: str, name: str = "") -> tuple[bool, str]:
    _open_url(url)
    label = name or url
    return True, f"Opening {label}."


def youtube_search(query: str) -> tuple[bool, str]:
    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query)
    _open_url(url)
    return True, f"Searching YouTube for {query}."


def google_search(query: str) -> tuple[bool, str]:
    url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)
    _open_url(url)
    return True, f"Googling {query}."


def whatsapp_action(target: str) -> tuple[bool, str]:
    target_clean = target.lower().strip()
    
    contacts = {}
    contacts_env = os.environ.get("WHATSAPP_CONTACTS") or ""
    if contacts_env:
        for item in contacts_env.split(","):
            if ":" in item:
                k, v = item.split(":", 1)
                contacts[k.strip().lower()] = "".join(filter(str.isdigit, v.strip()))
                
    phone_number = None
    if target_clean in contacts:
        phone_number = contacts[target_clean]
        log.info("Resolved contact '%s' to phone number: %s", target, phone_number)
    else:
        digits_only = "".join(filter(str.isdigit, target_clean))
        if len(digits_only) >= 10:
            phone_number = digits_only
            
    if not phone_number:
        return False, f"Could not find a phone number for {target} in your WhatsApp contacts. Please add them to your .env file."
        
    # Open directly in the Windows WhatsApp Desktop app via protocol
    url = f"whatsapp://send?phone={phone_number}"
    try:
        os.startfile(url)
    except Exception as e:
        log.warning("Protocol start failed, falling back to browser: %s", e)
        _open_url(f"https://wa.me/{phone_number}")
        
    return True, f"Opening WhatsApp chat with {target}."
