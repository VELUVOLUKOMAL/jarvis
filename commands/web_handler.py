"""
Web Handler — Opens websites, searches, LinkedIn, and startup-specific URLs for HEY CEO OS.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import urllib.parse
import webbrowser

log = logging.getLogger("hey.web_handler")


def _chrome_exe() -> str | None:
    prog   = os.environ.get("ProgramFiles",      r"C:\Program Files")
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
            kw: dict = {
                "args": [chrome, url],
                "stdin": subprocess.DEVNULL,
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
            }
            if sys.platform == "win32":
                kw["creationflags"] = subprocess.CREATE_NO_WINDOW
            subprocess.Popen(**kw)
            return
        except OSError as e:
            log.warning("Chrome launch failed: %s", e)
    webbrowser.open(url)


# ─── General web actions ──────────────────────────────────────────────────────

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
    return True, f"Searching Google for {query}."


# ─── Startup-specific searches ────────────────────────────────────────────────

def linkedin_search(query: str) -> tuple[bool, str]:
    """Search LinkedIn for people, roles, or companies."""
    url = ("https://www.linkedin.com/search/results/people/?"
           "keywords=" + urllib.parse.quote_plus(query))
    _open_url(url)
    return True, f"Searching LinkedIn for {query}."


def linkedin_job_search(query: str) -> tuple[bool, str]:
    """Search LinkedIn jobs."""
    url = ("https://www.linkedin.com/jobs/search/?"
           "keywords=" + urllib.parse.quote_plus(query))
    _open_url(url)
    return True, f"Searching LinkedIn jobs for {query}."


def search_investors(query: str = "startup investors") -> tuple[bool, str]:
    """Open AngelList or Crunchbase investor search."""
    url = "https://angel.co/investors?q=" + urllib.parse.quote_plus(query)
    _open_url(url)
    return True, "Opening investor search on AngelList."


def search_yc(query: str = "") -> tuple[bool, str]:
    """Open Y Combinator page."""
    url = "https://www.ycombinator.com"
    if query:
        url = "https://www.google.com/search?q=site:ycombinator.com+" + urllib.parse.quote_plus(query)
    _open_url(url)
    return True, "Opening Y Combinator."


def search_startup_grants(query: str = "startup grants") -> tuple[bool, str]:
    """Search for startup grants."""
    url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)
    _open_url(url)
    return True, f"Searching for {query}."


def market_research(query: str) -> tuple[bool, str]:
    """Open market research search."""
    url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)
    _open_url(url)
    return True, f"Researching {query}."


def open_html_page(page_url: str, page_name: str = "") -> tuple[bool, str]:
    """
    Open a local HTML page from the startup platform.
    Looks for the file relative to the project root, then falls back to Google.
    """
    from pathlib import Path
    project_root = Path(__file__).resolve().parent.parent

    # Search common subdirectories for the page
    candidates = [
        project_root / page_url,
        project_root / "web" / page_url,
        project_root / "app" / page_url,
        project_root / "frontend" / page_url,
        project_root / "pages" / page_url,
        project_root / "html" / page_url,
        project_root / "public" / page_url,
        project_root / "src" / page_url,
    ]
    for candidate in candidates:
        if candidate.is_file():
            _open_url(candidate.as_uri())
            label = page_name or page_url
            return True, f"Opening {label}."

    # If not found locally, just open with the default browser
    # so the user can see the intent was understood
    label = page_name or page_url.replace(".html", "").replace("-", " ").title()
    _open_url(f"file:///{project_root / page_url}")
    return True, f"Navigating to {label}."


# ─── WhatsApp ─────────────────────────────────────────────────────────────────

def whatsapp_action(target: str) -> tuple[bool, str]:
    target_clean = target.lower().strip()

    contacts: dict[str, str] = {}
    contacts_env = os.environ.get("WHATSAPP_CONTACTS") or ""
    if contacts_env:
        for item in contacts_env.split(","):
            if ":" in item:
                k, v = item.split(":", 1)
                contacts[k.strip().lower()] = "".join(filter(str.isdigit, v.strip()))

    phone_number = None
    if target_clean in contacts:
        phone_number = contacts[target_clean]
    else:
        digits_only = "".join(filter(str.isdigit, target_clean))
        if len(digits_only) >= 10:
            phone_number = digits_only

    if not phone_number:
        return False, (f"No phone number found for {target}. "
                       "Add them to WHATSAPP_CONTACTS in your .env file.")

    url = f"whatsapp://send?phone={phone_number}"
    try:
        os.startfile(url)
    except Exception as e:
        log.warning("WhatsApp protocol failed, falling back to browser: %s", e)
        _open_url(f"https://wa.me/{phone_number}")

    return True, f"Opening WhatsApp chat with {target}."
