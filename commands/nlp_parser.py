"""
NLP Parser — Maps raw voice text to structured intents + params.
"""
from __future__ import annotations
import re

# ─── Website shortcuts ────────────────────────────────────────────────────────
WEBSITE_MAP: dict[str, str] = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "github": "https://www.github.com",
    "spotify": "https://open.spotify.com",
    "netflix": "https://www.netflix.com",
    "twitter": "https://www.twitter.com",
    "instagram": "https://www.instagram.com",
    "facebook": "https://www.facebook.com",
    "reddit": "https://www.reddit.com",
    "amazon": "https://www.amazon.in",
    "linkedin": "https://www.linkedin.com",
    "claude": "https://claude.ai",
    "chatgpt": "https://chat.openai.com",
    "whatsapp web": "https://web.whatsapp.com",
    "binance": "https://www.binance.com",
    "stackoverflow": "https://stackoverflow.com",
    "wikipedia": "https://www.wikipedia.org",
    "notion": "https://www.notion.so",
    "figma": "https://www.figma.com",
    "vercel": "https://vercel.com",
}

# ─── App name aliases ─────────────────────────────────────────────────────────
APP_ALIASES: dict[str, str] = {
    "visual studio code": "vs code",
    "vscode": "vs code",
    "vs code": "vs code",
    "code": "vs code",
    "google chrome": "chrome",
    "microsoft edge": "edge",
    "file explorer": "explorer",
    "windows explorer": "explorer",
    "files": "explorer",
    "terminal": "windows terminal",
    "command prompt": "cmd",
    "command line": "cmd",
    "anti gravity": "antigravity",
    "anti-gravity": "antigravity",
    "photoshop": "photoshop",
}

# Known folder names
FOLDER_NAMES = {"desktop", "downloads", "documents", "pictures", "photos",
                "videos", "music", "onedrive", "home", "c drive", "ssd", "recycle bin"}


def _strip(text: str) -> str:
    return re.sub(r"[!?.,]+$", "", text.lower().strip())


def parse_command(text: str) -> dict:
    """Parse voice command text into {intent, params}."""
    t = _strip(text)

    # ── Simple greeting/wake word repetition ──────────────────────────────────
    if t in ["jarvis", "javris", "jarves", "jarv"] or t in ["hello", "hi", "hey", "hello jarvis", "hi jarvis", "hey jarvis"]:
        return {"intent": "greeting", "params": {}}

    # ── Voice enrollment ──────────────────────────────────────────────────────
    if any(p in t for p in ["enroll my voice", "register voice", "setup voice", "train my voice"]):
        return {"intent": "voice_enroll", "params": {}}

    # ── Voice unlock ──────────────────────────────────────────────────────────
    unlock_m = re.match(r"unlock\s+(.+)", t)
    if unlock_m:
        return {"intent": "voice_unlock", "params": {"code": unlock_m.group(1).strip()}}

    # ── Sleep / dismiss ───────────────────────────────────────────────────────
    if any(w in t for w in ["goodbye", "go to sleep", "bye", "see you", "that's all", "dismiss", "stop listening"]):
        return {"intent": "sleep", "params": {}}

    # ── Jarvis Active State control ───────────────────────────────────────────
    if any(w in t for w in ["jarvis off", "turn off jarvis", "deactivate jarvis", "go offline", "deactivate", "turn off", "stop", "off"]):
        if not any(w in t for w in ["computer", "laptop", "pc"]):
            return {"intent": "jarvis_off", "params": {}}
    if any(w in t for w in ["jarvis on", "turn on jarvis", "activate jarvis", "go online", "activate", "turn on", "wake up"]):
        return {"intent": "jarvis_on", "params": {}}

    # ── Thanks ────────────────────────────────────────────────────────────────
    if any(w in t for w in ["thank you", "thanks", "thank"]):
        return {"intent": "thanks", "params": {}}

    # ── Time / Date ───────────────────────────────────────────────────────────
    if any(p in t for p in ["what time", "current time", "what's the time", "time is it"]):
        return {"intent": "time", "params": {}}
    if any(p in t for p in ["what date", "what day", "today's date", "current date", "what's today"]):
        return {"intent": "date", "params": {}}

    # ── System Monitor HUD / Dashboard ────────────────────────────────────────
    if any(p in t for p in ["open system monitor", "show dashboard", "system stats", "open dashboard", "show system monitor", "show system stats"]):
        return {"intent": "dashboard_open", "params": {}}
    if any(p in t for p in ["close system monitor", "close dashboard", "hide dashboard", "hide system monitor"]):
        return {"intent": "dashboard_close", "params": {}}

    # ── Volume ────────────────────────────────────────────────────────────────
    if any(p in t for p in ["volume up", "turn up", "louder", "increase volume", "raise volume"]):
        m = re.search(r"(\d+)", t)
        return {"intent": "volume_up", "params": {"amount": int(m.group(1)) if m else 10}}
    if any(p in t for p in ["volume down", "turn down", "quieter", "lower volume", "decrease volume", "reduce volume"]):
        m = re.search(r"(\d+)", t)
        return {"intent": "volume_down", "params": {"amount": int(m.group(1)) if m else 10}}
    set_vol_m = re.search(r"(?:set|change)\s+volume\s+to\s+(\d+)", t)
    if set_vol_m:
        return {"intent": "set_volume", "params": {"level": int(set_vol_m.group(1))}}
    if re.search(r"\bunmute\b", t):
        return {"intent": "unmute", "params": {}}
    if re.search(r"\bmute\b", t):
        return {"intent": "mute", "params": {}}

    # ── Brightness ────────────────────────────────────────────────────────────
    if any(p in t for p in ["brightness up", "brighter", "increase brightness"]):
        m = re.search(r"(\d+)", t)
        return {"intent": "brightness_up", "params": {"amount": int(m.group(1)) if m else 10}}
    if any(p in t for p in ["brightness down", "dimmer", "decrease brightness", "lower brightness", "reduce brightness"]):
        m = re.search(r"(\d+)", t)
        return {"intent": "brightness_down", "params": {"amount": int(m.group(1)) if m else 10}}

    # ── Screenshot ────────────────────────────────────────────────────────────
    if any(p in t for p in ["screenshot", "screen shot", "capture screen"]):
        return {"intent": "screenshot", "params": {}}

    # ── Lock ──────────────────────────────────────────────────────────────────
    if (re.search(r"\block\b", t) and any(w in t for w in ["screen", "computer", "laptop", "pc"])) or t == "lock":
        return {"intent": "lock", "params": {}}

    # ── Power ─────────────────────────────────────────────────────────────────
    if any(p in t for p in ["cancel shutdown", "abort shutdown", "stop shutdown"]):
        return {"intent": "cancel_shutdown", "params": {}}
    if any(p in t for p in ["shut down", "shutdown", "power off", "turn off the computer", "turn off the laptop"]):
        return {"intent": "shutdown", "params": {}}
    if any(p in t for p in ["restart", "reboot"]):
        return {"intent": "restart", "params": {}}
    if "sleep" in t and any(w in t for w in ["computer", "laptop", "pc"]):
        return {"intent": "pc_sleep", "params": {}}

    # ── Long-term Memory ──────────────────────────────────────────────────────
    remember_m = re.match(r"remember\s+that\s+(.+?)\s+(?:is|are|was|were)\s+(.+)", t)
    if remember_m:
        return {"intent": "remember_fact", "params": {"key": remember_m.group(1).strip(), "value": remember_m.group(2).strip()}}
    
    forget_all_m = re.match(r"(?:clear|wipe|forget)\s+all\s+(?:memories|memory|what you remember)", t)
    if forget_all_m:
        return {"intent": "forget_all", "params": {}}
        
    forget_m = re.match(r"forget\s+(?:that|about\s+)?(.+)", t)
    if forget_m:
        return {"intent": "forget_memory", "params": {"key": forget_m.group(1).strip()}}

    recall_all_m = re.match(r"what\s+do\s+you\s+remember$", t)
    if recall_all_m:
        return {"intent": "recall_all", "params": {}}

    recall_m = re.match(r"(?:what\s+do\s+you\s+remember\s+about|recall|find\s+my\s+memory\s+about|where\s+is\s+my)\s+(.+)", t)
    if recall_m:
        return {"intent": "recall_memory", "params": {"query": recall_m.group(1).strip()}}

    # ── Autonomous Coding Workspace Agent ─────────────────────────────────────
    coding_m = re.match(r"(?:create|build|write|scaffold)\s+(?:a|an)?\s*(?:python|web|flask|react|node|html|landing|portfolio)?\s*(?:website|app|script|project|calculator|todo|api|page)\s*(?:called\s+(.+))?\s*(?:to\s+(.+))?", t)
    if coding_m and any(w in t for w in ["website", "app", "script", "project", "calculator", "todo", "page"]):
        return {"intent": "coding_task", "params": {"description": text}}
    # Broad catch for coding instructions
    if t.startswith("write code for ") or t.startswith("create a python ") or t.startswith("create a website"):
        return {"intent": "coding_task", "params": {"description": text}}

    # ── Screen Understanding & Screen-Aware Actions ───────────────────────────
    if any(p in t for p in ["what am i looking at", "what's on my screen", "describe my screen", "explain this screen"]):
        return {"intent": "screen_describe", "params": {}}
    if any(p in t for p in ["read this text", "read the screen", "read text on screen", "ocr screen"]):
        return {"intent": "screen_read", "params": {}}
    
    click_m = re.match(r"(?:click|press|tap)\s+(?:on\s+)?(?:the\s+)?(.+)", t)
    if click_m and not any(w in t for w in ["shortcut", "key", "button lock"]):
        # Discard generic click words like "left click" or "double click" handled by input control
        if click_m.group(1).strip() not in ["left", "right", "double", "here"]:
            return {"intent": "screen_click", "params": {"element": click_m.group(1).strip()}}

    fill_m = re.match(r"fill\s+(?:in\s+)?(?:the\s+)?(.+?)\s+with\s+(.+)", t)
    if fill_m:
        return {"intent": "screen_fill", "params": {"field": fill_m.group(1).strip(), "value": fill_m.group(2).strip()}}

    # ── Keyboard & Mouse Control (pyautogui) ──────────────────────────────────
    if t.startswith("type this email ") or t.startswith("type: ") or t.startswith("type "):
        typed = text[5:].strip()
        if typed.lower().startswith("this email "):
            typed = typed[11:].strip()
        if typed.lower().startswith("email "):
            typed = typed[6:].strip()
        return {"intent": "keyboard_type", "params": {"text": typed}}

    if t.startswith("press ") or any(t == s for s in ["copy", "paste", "cut", "undo", "redo", "save", "select all"]):
        return {"intent": "keyboard_press", "params": {"keys": text}}

    if t == "double click":
        return {"intent": "mouse_click", "params": {"button": "left", "double": True}}
    if t == "right click":
        return {"intent": "mouse_click", "params": {"button": "right", "double": False}}
    if t == "click" or t == "left click" or t == "click mouse":
        return {"intent": "mouse_click", "params": {"button": "left", "double": False}}

    move_m = re.match(r"move\s+(?:the\s+)?mouse\s+(?:to\s+)?(.+)", t)
    if move_m:
        return {"intent": "mouse_move", "params": {"where": move_m.group(1).strip()}}

    if any(p in t for p in ["scroll up", "scroll down"]):
        direction = "up" if "up" in t else "down"
        return {"intent": "mouse_scroll", "params": {"direction": direction}}

    # ── Git & GitHub ──────────────────────────────────────────────────────────
    if any(p in t for p in ["git status", "show git status", "repo status"]):
        return {"intent": "git_status", "params": {}}
    commit_m = re.match(r"(?:git commit|commit my changes|commit changes)\s+(?:with\s+message\s+)?(.+)", t)
    if commit_m:
        return {"intent": "git_commit", "params": {"message": commit_m.group(1).strip()}}
    if any(p in t for p in ["git push", "push to github", "push code", "push changes"]):
        return {"intent": "git_push", "params": {}}
    if any(p in t for p in ["git pull", "pull code", "pull latest", "pull changes"]):
        return {"intent": "git_pull", "params": {}}
    branch_m = re.match(r"(?:git branch|create branch|git create branch)\s+(.+)", t)
    if branch_m:
        return {"intent": "git_branch_create", "params": {"name": branch_m.group(1).strip()}}
    switch_m = re.match(r"(?:git checkout|switch branch|switch to branch)\s+(.+)", t)
    if switch_m:
        return {"intent": "git_branch_switch", "params": {"name": switch_m.group(1).strip()}}
    if any(p in t for p in ["git log", "show git log", "show commits"]):
        return {"intent": "git_log", "params": {}}
    if any(p in t for p in ["git init", "initialize git", "initialize repository"]):
        return {"intent": "git_init", "params": {}}
    clone_m = re.match(r"git clone\s+(.+)", t)
    if clone_m:
        return {"intent": "git_clone", "params": {"url": clone_m.group(1).strip()}}

    # ── Workflow Automation ───────────────────────────────────────────────────
    if any(p in t for p in ["prepare my coding workspace", "prepare coding workspace", "open coding workspace"]):
        return {"intent": "workflow_run", "params": {"name": "coding workspace"}}
    if any(p in t for p in ["start morning routine", "morning routine"]):
        return {"intent": "workflow_run", "params": {"name": "morning routine"}}
    if any(p in t for p in ["activate research mode", "research mode"]):
        return {"intent": "workflow_run", "params": {"name": "research mode"}}
    if any(p in t for p in ["presentation mode", "setup presentation"]):
        return {"intent": "workflow_run", "params": {"name": "presentation mode"}}
    if any(p in t for p in ["gaming setup", "gaming mode"]):
        return {"intent": "workflow_run", "params": {"name": "gaming setup"}}
    
    workflow_run_m = re.match(r"(?:run|execute|start)\s+workflow\s+(.+)", t)
    if workflow_run_m:
        return {"intent": "workflow_run", "params": {"name": workflow_run_m.group(1).strip()}}
    
    workflow_create_m = re.match(r"create\s+workflow\s+(.+?)\s+to\s+(.+)", t)
    if workflow_create_m:
        return {"intent": "workflow_create", "params": {"name": workflow_create_m.group(1).strip(), "description": workflow_create_m.group(2).strip()}}
        
    if any(p in t for p in ["list workflows", "show workflows", "what workflows do you have"]):
        return {"intent": "workflow_list", "params": {}}

    # ── Timer ─────────────────────────────────────────────────────────────────
    timer_m = re.search(r"(?:set|start|create)\s+(?:a\s+)?(?:(\w+)\s+)?timer\s+(?:for\s+)?(.+)", t)
    if timer_m:
        return {"intent": "set_timer", "params": {"duration_str": timer_m.group(2), "label": timer_m.group(1) or "Timer"}}
    if any(p in t for p in ["cancel timer", "stop timer", "clear timer"]):
        return {"intent": "cancel_timer", "params": {}}

    # ── System info ───────────────────────────────────────────────────────────
    if any(p in t for p in ["battery", "battery level", "how much battery", "battery percentage"]):
        return {"intent": "battery", "params": {}}
    if any(p in t for p in ["cpu", "ram", "memory usage", "system performance"]):
        return {"intent": "cpu_ram", "params": {}}
    if any(p in t for p in ["disk space", "storage space", "how much space", "free space"]):
        m = re.search(r"\b([a-z])\s+drive\b", t)
        return {"intent": "disk_space", "params": {"drive": m.group(1).upper() if m else "C"}}
    if any(p in t for p in ["ip address", "my ip", "network address"]):
        return {"intent": "ip_address", "params": {}}

    # ── Media ─────────────────────────────────────────────────────────────────
    if t in ("play", "resume") or any(p in t for p in ["play music", "resume music", "resume playing", "unpause"]):
        return {"intent": "media_play", "params": {}}
    if t in ("pause", "stop") or any(p in t for p in ["pause music", "stop music", "stop playing"]):
        return {"intent": "media_pause", "params": {}}
    if t in ("next", "skip", "next song", "next track") or (
        any(w in t for w in ["next", "skip"]) and any(w in t for w in ["song", "track", "music"])
    ):
        return {"intent": "media_next", "params": {}}
    if t in ("previous", "prev", "previous song") or (
        any(w in t for w in ["previous", "prev"]) and any(w in t for w in ["song", "track"])
    ):
        return {"intent": "media_prev", "params": {}}

    # ── Window management ─────────────────────────────────────────────────────
    if "close" in t and any(w in t for w in ["window", "this", "current", "tab"]):
        return {"intent": "close_window", "params": {}}
    if "minimize" in t:
        return {"intent": "minimize_window", "params": {}}
    if any(p in t for p in ["maximize", "full screen", "fullscreen"]):
        return {"intent": "maximize_window", "params": {}}

    # ── YouTube / Google search ───────────────────────────────────────────────
    yt_open_play_m = re.search(r"open\s+youtube\s+and\s+(?:play|search|find)\s+(.+)", t)
    if yt_open_play_m:
        return {"intent": "youtube_search", "params": {"query": yt_open_play_m.group(1).strip()}}

    google_open_search_m = re.search(r"open\s+(?:chrome|google|browser)\s+and\s+(?:search|find|look up)\s+for\s+(.+)", t)
    if not google_open_search_m:
        google_open_search_m = re.search(r"open\s+(?:chrome|google|browser)\s+and\s+(?:search|find|look up)\s+(.+)", t)
    if google_open_search_m:
        return {"intent": "google_search", "params": {"query": google_open_search_m.group(1).strip()}}

    yt_m = re.search(r"(?:search|play|find|look up)\s+(.+?)\s+(?:on|in)\s+youtube", t)
    if yt_m:
        return {"intent": "youtube_search", "params": {"query": yt_m.group(1).strip()}}
    if t.startswith("play ") and not any(w in t for w in ["music", "song", "track", "playlist"]):
        query = t[5:].strip()
        if query:
            return {"intent": "youtube_search", "params": {"query": query}}

    # Google search
    if "on google" in t:
        query = t.replace("on google", "").replace("search for", "").replace("search", "").strip()
        if query:
            return {"intent": "google_search", "params": {"query": query}}
    if t.startswith("google "):
        return {"intent": "google_search", "params": {"query": t[7:].strip()}}
    if t.startswith("search for "):
        return {"intent": "google_search", "params": {"query": t[11:].strip()}}
    if t.startswith("search "):
        query = t[7:].strip()
        if query and not any(w in query for w in ["youtube", "folder", "file"]):
            return {"intent": "google_search", "params": {"query": query}}
    if t.startswith("look up "):
        return {"intent": "google_search", "params": {"query": t[8:].strip()}}

    # ── Open folder shortcut ──────────────────────────────────────────────────
    folder_m = re.search(
        r"(?:open|show|go to)\s+(?:my\s+)?(desktop|downloads|documents|pictures|photos|videos|music|onedrive|home|c drive|ssd|recycle bin)",
        t
    )
    if folder_m:
        return {"intent": "open_folder", "params": {"folder": folder_m.group(1)}}

    # ── Find file ─────────────────────────────────────────────────────────────
    find_m = re.search(r"(?:find|locate|search for|where is)\s+(?:file\s+|folder\s+)?(.+?)(?:\s+file|\s+folder)?$", t)
    if find_m:
        return {"intent": "find_file", "params": {"name": find_m.group(1).strip()}}

    # ── Open website / app / folder ───────────────────────────────────────────
    open_m = re.search(
        r"(?:open|go to|browse|navigate to|take me to)\s+(.+?)(?:\s+(?:website|site|page|app|application))?$", t
    )
    if open_m:
        target = open_m.group(1).strip()
        target_norm = APP_ALIASES.get(target, target)
        if target_norm in WEBSITE_MAP:
            return {"intent": "open_website", "params": {"url": WEBSITE_MAP[target_norm], "name": target_norm}}
        if "." in target and " " not in target:
            url = target if target.startswith("http") else f"https://{target}"
            return {"intent": "open_website", "params": {"url": url, "name": target}}
        if target_norm in FOLDER_NAMES:
            return {"intent": "open_folder", "params": {"folder": target_norm}}
        return {"intent": "open_app", "params": {"app": target_norm}}

    # ── Launch / Start ────────────────────────────────────────────────────────
    launch_m = re.search(r"(?:launch|start|run|execute)\s+(.+?)(?:\s+(?:app|application|program))?$", t)
    if launch_m:
        app_name = launch_m.group(1).strip()
        app_name = APP_ALIASES.get(app_name, app_name)
        return {"intent": "open_app", "params": {"app": app_name}}

    # ── WhatsApp Call/Message ─────────────────────────────────────────────────
    wa_m = re.search(r"(?:whatsapp|message|call)\s+(.+?)(?:\s+on\s+whatsapp)?$", t)
    if wa_m and ("whatsapp" in t or t.startswith("call ") or t.startswith("message ")):
        if "whatsapp" in t:
            target = wa_m.group(1).replace("on whatsapp", "").strip()
            if target:
                return {"intent": "whatsapp_action", "params": {"target": target}}

    # ── Fallback: AI question ─────────────────────────────────────────────────
    return {"intent": "question", "params": {"query": text}}
