"""
NLP Parser — Maps raw voice text to structured intents + params for HEY CEO OS.
Add new intents here without touching any other file.
"""
from __future__ import annotations
import re

# ─── Website shortcuts ────────────────────────────────────────────────────────
WEBSITE_MAP: dict[str, str] = {
    "youtube":       "https://www.youtube.com",
    "google":        "https://www.google.com",
    "gmail":         "https://mail.google.com",
    "github":        "https://www.github.com",
    "spotify":       "https://open.spotify.com",
    "netflix":       "https://www.netflix.com",
    "twitter":       "https://www.twitter.com",
    "instagram":     "https://www.instagram.com",
    "facebook":      "https://www.facebook.com",
    "reddit":        "https://www.reddit.com",
    "amazon":        "https://www.amazon.in",
    "linkedin":      "https://www.linkedin.com",
    "claude":        "https://claude.ai",
    "chatgpt":       "https://chat.openai.com",
    "whatsapp web":  "https://web.whatsapp.com",
    "binance":       "https://www.binance.com",
    "stackoverflow": "https://stackoverflow.com",
    "wikipedia":     "https://www.wikipedia.org",
    "notion":        "https://www.notion.so",
    "figma":         "https://www.figma.com",
    "vercel":        "https://vercel.com",
    "y combinator":  "https://www.ycombinator.com",
    "yc":            "https://www.ycombinator.com",
    "producthunt":   "https://www.producthunt.com",
    "angellist":     "https://angel.co",
    "crunchbase":    "https://www.crunchbase.com",
    "techcrunch":    "https://techcrunch.com",
}

# ─── App name aliases ─────────────────────────────────────────────────────────
APP_ALIASES: dict[str, str] = {
    "visual studio code": "vs code",
    "vscode": "vs code",
    "vs code": "vs code",
    "vs": "vs code",
    "visual studio": "vs code",
    "code editor": "vs code",
    "code": "vs code",
    "google chrome": "chrome",
    "microsoft edge": "edge",
    "file explorer": "explorer",
    "windows explorer": "explorer",
    "file manager": "explorer",
    "files": "explorer",
    "my files": "explorer",
    "folder": "explorer",
    "terminal": "windows terminal",
    "command prompt": "cmd",
    "command line": "cmd",
    "notepad": "notepad",
    "paint": "mspaint",
    "word": "microsoft word",
    "excel": "microsoft excel",
    "powerpoint": "microsoft powerpoint",
}

FOLDER_NAMES = {"desktop", "downloads", "documents", "pictures", "photos",
                "videos", "music", "onedrive", "home", "c drive", "ssd", "recycle bin"}


def _strip(text: str) -> str:
    return re.sub(r"[!?.,]+$", "", text.lower().strip())


def parse_command(text: str) -> dict:
    """Parse voice command text into {intent, params}. Add new intents here."""
    t = _strip(text)

    # ── Wake word / greeting ──────────────────────────────────────────────────
    if t in ["hey", "hey hey"] or re.match(r"^hey\s*$", t):
        return {"intent": "greeting", "params": {}}
    if t in ["hello", "hi", "hello hey", "hi hey"]:
        return {"intent": "greeting", "params": {}}

    # ── Sleep / dismiss ───────────────────────────────────────────────────────
    if any(w in t for w in ["goodbye", "go to sleep", "bye", "see you",
                             "that's all", "dismiss", "stop listening"]):
        return {"intent": "sleep", "params": {}}

    # ── HEY on/off ────────────────────────────────────────────────────────────
    if any(w in t for w in ["hey off", "turn off hey", "deactivate hey",
                             "go offline", "deactivate", "stop", "off"]):
        if not any(w in t for w in ["computer", "laptop", "pc"]):
            return {"intent": "hey_off", "params": {}}
    if any(w in t for w in ["hey on", "turn on hey", "activate hey",
                             "go online", "activate", "wake up"]):
        return {"intent": "hey_on", "params": {}}

    # ── Thanks ────────────────────────────────────────────────────────────────
    if any(w in t for w in ["thank you", "thanks", "thank"]):
        return {"intent": "thanks", "params": {}}

    # =========================================================================
    # STARTUP CEO COMMANDS
    # =========================================================================

    # ── Hiring ────────────────────────────────────────────────────────────────
    hire_m = re.match(
        r"(?:hire|recruit|find|search for|look for|get me)\s+(?:a\s+|an\s+)?(.+?)(?:\s+developer|\s+designer|\s+engineer|\s+manager|\s+lead|\s+intern)?$",
        t
    )
    if hire_m and any(w in t for w in [
        "hire", "recruit", "developer", "designer", "engineer", "manager",
        "lead", "intern", "cto", "cfo", "cmo", "vp", "founder"
    ]):
        role = hire_m.group(1).strip()
        return {"intent": "startup_hire", "params": {"role": role}}

    # ── Document generation ───────────────────────────────────────────────────
    if any(p in t for p in ["create an nda", "generate nda", "make an nda",
                             "create nda", "draft nda", "nda"]):
        return {"intent": "startup_generate_doc",
                "params": {"doc_type": "nda", "doc_name": "Non-Disclosure Agreement"}}

    if any(p in t for p in ["founder agreement", "create founder agreement",
                             "generate founder agreement", "founders agreement"]):
        return {"intent": "startup_generate_doc",
                "params": {"doc_type": "founder_agreement", "doc_name": "Founder Agreement"}}

    if any(p in t for p in ["employment contract", "generate employment contract",
                             "create employment contract", "employee contract"]):
        return {"intent": "startup_generate_doc",
                "params": {"doc_type": "employment_contract", "doc_name": "Employment Contract"}}

    if any(p in t for p in ["privacy policy", "generate privacy policy",
                             "create privacy policy"]):
        return {"intent": "startup_generate_doc",
                "params": {"doc_type": "privacy_policy", "doc_name": "Privacy Policy"}}

    if any(p in t for p in ["terms and conditions", "terms of service",
                             "generate terms", "create terms"]):
        return {"intent": "startup_generate_doc",
                "params": {"doc_type": "terms_conditions", "doc_name": "Terms and Conditions"}}

    if any(p in t for p in ["business plan", "generate business plan",
                             "create business plan"]):
        return {"intent": "startup_generate_doc",
                "params": {"doc_type": "business_plan", "doc_name": "Business Plan"}}

    if any(p in t for p in ["create invoice", "generate invoice", "make invoice"]):
        return {"intent": "startup_generate_doc",
                "params": {"doc_type": "invoice", "doc_name": "Invoice"}}

    if any(p in t for p in ["create proposal", "generate proposal", "make proposal"]):
        return {"intent": "startup_generate_doc",
                "params": {"doc_type": "proposal", "doc_name": "Proposal"}}

    # Generic document generation
    gen_doc_m = re.match(
        r"(?:generate|create|draft|make|write)\s+(?:a\s+|an\s+)?(.+?)(?:\s+document|\s+template|\s+contract)?$",
        t
    )
    if gen_doc_m and any(w in t for w in [
        "generate", "draft", "contract", "agreement", "document",
        "template", "policy", "report"
    ]):
        doc_name = gen_doc_m.group(1).strip()
        return {"intent": "startup_generate_doc",
                "params": {"doc_type": "custom", "doc_name": doc_name}}

    # ── Contract review ───────────────────────────────────────────────────────
    if any(p in t for p in ["review contract", "review this contract",
                             "analyze contract", "check contract",
                             "review employee agreement", "analyze agreement"]):
        return {"intent": "startup_review_contract", "params": {}}

    if any(p in t for p in ["show contracts", "open contracts", "my contracts",
                             "list contracts", "view contracts"]):
        return {"intent": "startup_open_page",
                "params": {"page": "contracts", "url": "contract-review.html"}}

    # ── Compliance ────────────────────────────────────────────────────────────
    if any(p in t for p in ["check compliance", "open compliance",
                             "compliance tracker", "compliance check",
                             "show compliance", "analyze compliance"]):
        return {"intent": "startup_compliance", "params": {}}

    # ── Risk analysis ─────────────────────────────────────────────────────────
    if any(p in t for p in ["analyze startup risks", "startup risks", "analyze risks",
                             "risk analyzer", "check risks", "show risks",
                             "business risks", "analyze company"]):
        return {"intent": "startup_risks", "params": {}}

    # ── Pitch deck / investors ────────────────────────────────────────────────
    if any(p in t for p in ["create pitch deck", "pitch deck", "generate pitch",
                             "pitch generator", "make pitch deck"]):
        return {"intent": "startup_pitch_deck", "params": {}}

    if any(p in t for p in ["search investors", "find investors", "investor search",
                             "look for investors", "search funding",
                             "search funding opportunities", "funding opportunities"]):
        return {"intent": "startup_search_investors", "params": {}}

    if any(p in t for p in ["prepare investor update", "investor update",
                             "investor report"]):
        return {"intent": "startup_generate_doc",
                "params": {"doc_type": "investor_update", "doc_name": "Investor Update"}}

    # ── Financial ─────────────────────────────────────────────────────────────
    if any(p in t for p in ["open finance", "show finance", "finances"]):
        return {"intent": "startup_open_page",
                "params": {"page": "finance", "url": "finance.html"}}

    if any(p in t for p in ["generate budget", "create budget", "make budget"]):
        return {"intent": "startup_generate_doc",
                "params": {"doc_type": "budget", "doc_name": "Budget"}}

    if any(p in t for p in ["review expenses", "show expenses", "expenses"]):
        return {"intent": "startup_open_page",
                "params": {"page": "expenses", "url": "finance.html"}}

    if any(p in t for p in ["show revenue", "check revenue", "revenue"]):
        return {"intent": "startup_open_page",
                "params": {"page": "revenue", "url": "finance.html"}}

    if any(p in t for p in ["check sales", "show sales", "sales"]):
        return {"intent": "startup_open_page",
                "params": {"page": "sales", "url": "analytics.html"}}

    # ── Dashboard / pages ─────────────────────────────────────────────────────
    if any(p in t for p in ["dashboard", "open dashboard", "show dashboard",
                             "go to dashboard", "home"]):
        return {"intent": "startup_open_page",
                "params": {"page": "dashboard", "url": "dashboard.html"}}

    if any(p in t for p in ["settings", "open settings", "show settings"]):
        return {"intent": "startup_open_page",
                "params": {"page": "settings", "url": "settings.html"}}

    if any(p in t for p in ["knowledge base", "open knowledge base",
                             "knowledge", "open kb"]):
        return {"intent": "startup_open_page",
                "params": {"page": "knowledge_base", "url": "knowledge-base.html"}}

    if any(p in t for p in ["open legal chat", "legal chat", "legal ai",
                             "legal assistant"]):
        return {"intent": "startup_open_page",
                "params": {"page": "legal_chat", "url": "legal-chat.html"}}

    if any(p in t for p in ["open analytics", "show analytics", "analytics"]):
        return {"intent": "startup_open_page",
                "params": {"page": "analytics", "url": "analytics.html"}}

    if any(p in t for p in ["open crm", "show crm", "crm", "customer relations"]):
        return {"intent": "startup_open_page",
                "params": {"page": "crm", "url": "crm.html"}}

    if any(p in t for p in ["open notifications", "show notifications",
                             "notifications"]):
        return {"intent": "startup_open_page",
                "params": {"page": "notifications", "url": "notifications.html"}}

    if any(p in t for p in ["open messages", "show messages", "messages"]):
        return {"intent": "startup_open_page",
                "params": {"page": "messages", "url": "messages.html"}}

    if any(p in t for p in ["open documents", "show documents", "documents",
                             "my documents"]):
        return {"intent": "startup_open_page",
                "params": {"page": "documents", "url": "document-generator.html"}}

    if any(p in t for p in ["show team", "open team", "team members", "my team"]):
        return {"intent": "startup_open_page",
                "params": {"page": "team", "url": "team.html"}}

    # ── Tasks / Roadmap / Schedule ────────────────────────────────────────────
    if any(p in t for p in ["summarize today's tasks", "today's tasks",
                             "show pending work", "pending work",
                             "what's today's schedule", "today's schedule"]):
        return {"intent": "startup_dashboard_summary", "params": {}}

    if any(p in t for p in ["create tasks", "add tasks", "new task", "create task"]):
        return {"intent": "startup_open_page",
                "params": {"page": "tasks", "url": "dashboard.html"}}

    if any(p in t for p in ["create roadmap", "product roadmap", "roadmap"]):
        return {"intent": "startup_open_page",
                "params": {"page": "roadmap", "url": "roadmap.html"}}

    if any(p in t for p in ["generate report", "create report", "show report"]):
        return {"intent": "startup_generate_doc",
                "params": {"doc_type": "report", "doc_name": "Report"}}

    # ── Calendar / Meetings ───────────────────────────────────────────────────
    if any(p in t for p in ["create meeting", "schedule meeting",
                             "call meeting", "book meeting"]):
        return {"intent": "startup_open_page",
                "params": {"page": "calendar", "url": "calendar.html"}}

    if any(p in t for p in ["send email", "compose email", "write email",
                             "open email"]):
        return {"intent": "startup_open_page",
                "params": {"page": "email", "url": "messages.html"}}

    # ── Market / Competitors / Ideas ─────────────────────────────────────────
    if any(p in t for p in ["find competitors", "competitor analysis",
                             "search competitors"]):
        return {"intent": "startup_research",
                "params": {"query": "competitor analysis", "type": "competitors"}}

    if any(p in t for p in ["search market trends", "market trends",
                             "market analysis"]):
        return {"intent": "startup_research",
                "params": {"query": "market trends", "type": "market"}}

    if any(p in t for p in ["find startup ideas", "startup ideas",
                             "new business ideas"]):
        return {"intent": "startup_research",
                "params": {"query": "startup ideas", "type": "ideas"}}

    if any(p in t for p in ["search startup grants", "startup grants",
                             "government grants", "grants"]):
        return {"intent": "startup_research",
                "params": {"query": "startup grants", "type": "grants"}}

    # ── LinkedIn search ───────────────────────────────────────────────────────
    if any(p in t for p in ["search for ai engineers", "search ai engineers"]):
        return {"intent": "linkedin_search", "params": {"query": "AI engineers"}}

    linkedin_m = re.match(r"(?:search|find|look for)\s+(.+?)\s+on\s+linkedin", t)
    if linkedin_m:
        return {"intent": "linkedin_search",
                "params": {"query": linkedin_m.group(1).strip()}}

    if "linkedin" in t and any(w in t for w in ["search", "find", "look"]):
        q = re.sub(r"(?:search|find|look\s+for|on\s+linkedin|linkedin)", "", t).strip()
        if q:
            return {"intent": "linkedin_search", "params": {"query": q}}

    # ── Deploy / GitHub ───────────────────────────────────────────────────────
    if any(p in t for p in ["deploy website", "deploy app", "deploy"]):
        return {"intent": "startup_deploy", "params": {}}

    # ── YC / grants search ────────────────────────────────────────────────────
    if any(p in t for p in ["search yc", "open y combinator", "y combinator",
                             "yc applications", "apply yc"]):
        return {"intent": "open_website",
                "params": {"url": "https://www.ycombinator.com", "name": "Y Combinator"}}

    # =========================================================================
    # SYSTEM / PC COMMANDS
    # =========================================================================

    # ── Time / Date ───────────────────────────────────────────────────────────
    if any(p in t for p in ["what time", "current time", "what's the time"]):
        return {"intent": "time", "params": {}}
    if any(p in t for p in ["what date", "what day", "today's date", "current date"]):
        return {"intent": "date", "params": {}}

    # ── Voice enrollment ──────────────────────────────────────────────────────
    if any(p in t for p in ["enroll my voice", "register voice",
                             "setup voice", "train my voice"]):
        return {"intent": "voice_enroll", "params": {}}

    # ── Voice unlock ──────────────────────────────────────────────────────────
    unlock_m = re.match(r"unlock\s+(.+)", t)
    if unlock_m:
        return {"intent": "voice_unlock", "params": {"code": unlock_m.group(1).strip()}}

    # ── Volume ────────────────────────────────────────────────────────────────
    if any(p in t for p in ["volume up", "turn up", "louder",
                             "increase volume", "raise volume"]):
        m = re.search(r"(\d+)", t)
        return {"intent": "volume_up", "params": {"amount": int(m.group(1)) if m else 10}}
    if any(p in t for p in ["volume down", "turn down", "quieter",
                             "lower volume", "decrease volume"]):
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
    if any(p in t for p in ["brightness down", "dimmer", "decrease brightness"]):
        m = re.search(r"(\d+)", t)
        return {"intent": "brightness_down", "params": {"amount": int(m.group(1)) if m else 10}}

    # ── Screenshot ────────────────────────────────────────────────────────────
    if any(p in t for p in ["screenshot", "screen shot", "capture screen"]):
        return {"intent": "screenshot", "params": {}}

    # ── Lock ──────────────────────────────────────────────────────────────────
    if (re.search(r"\block\b", t) and any(w in t for w in [
            "screen", "computer", "laptop", "pc"])) or t == "lock":
        return {"intent": "lock", "params": {}}

    # ── Power ─────────────────────────────────────────────────────────────────
    if any(p in t for p in ["cancel shutdown", "abort shutdown"]):
        return {"intent": "cancel_shutdown", "params": {}}
    if any(p in t for p in ["shut down", "shutdown", "power off",
                             "turn off the computer"]):
        return {"intent": "shutdown", "params": {}}
    if any(p in t for p in ["restart", "reboot"]):
        return {"intent": "restart", "params": {}}
    if "sleep" in t and any(w in t for w in ["computer", "laptop", "pc",
                                              "mode", "system"]):
        return {"intent": "pc_sleep", "params": {}}

    # ── Media ─────────────────────────────────────────────────────────────────
    if t in ("play", "resume") or any(p in t for p in [
            "play music", "resume music", "unpause"]):
        return {"intent": "media_play", "params": {}}
    if t in ("pause", "stop") or any(p in t for p in ["pause music", "stop music"]):
        return {"intent": "media_pause", "params": {}}
    if t in ("next", "skip", "next song") or (
        any(w in t for w in ["next", "skip"]) and
        any(w in t for w in ["song", "track", "music"])
    ):
        return {"intent": "media_next", "params": {}}
    if t in ("previous", "prev") or (
        any(w in t for w in ["previous", "prev"]) and
        any(w in t for w in ["song", "track"])
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
    yt_m = re.search(r"(?:search|play|find)\s+(.+?)\s+(?:on|in)\s+youtube", t)
    if yt_m:
        return {"intent": "youtube_search", "params": {"query": yt_m.group(1).strip()}}
    if t.startswith("play ") and not any(w in t for w in ["music", "track"]):
        q = t[5:].strip()
        if q:
            return {"intent": "youtube_search", "params": {"query": q}}
    if t.startswith("google "):
        return {"intent": "google_search", "params": {"query": t[7:].strip()}}
    if t.startswith("search for "):
        return {"intent": "google_search", "params": {"query": t[11:].strip()}}
    if t.startswith("look up "):
        return {"intent": "google_search", "params": {"query": t[8:].strip()}}
    if "on google" in t:
        q = t.replace("on google", "").replace("search for", "").replace("search", "").strip()
        if q:
            return {"intent": "google_search", "params": {"query": q}}

    # ── Timer ─────────────────────────────────────────────────────────────────
    timer_m = re.search(
        r"(?:set|start|create)\s+(?:a\s+)?(?:(\w+)\s+)?timer\s+(?:for\s+)?(.+)", t)
    if timer_m:
        return {"intent": "set_timer",
                "params": {"duration_str": timer_m.group(2),
                           "label": timer_m.group(1) or "Timer"}}
    if any(p in t for p in ["cancel timer", "stop timer"]):
        return {"intent": "cancel_timer", "params": {}}

    # ── System info ───────────────────────────────────────────────────────────
    if any(p in t for p in ["battery", "battery level", "battery percentage"]):
        return {"intent": "battery", "params": {}}
    if any(p in t for p in ["cpu", "ram", "memory usage"]):
        return {"intent": "cpu_ram", "params": {}}
    if any(p in t for p in ["disk space", "storage space", "free space"]):
        m = re.search(r"\b([a-z])\s+drive\b", t)
        return {"intent": "disk_space",
                "params": {"drive": m.group(1).upper() if m else "C"}}
    if any(p in t for p in ["ip address", "my ip", "network address"]):
        return {"intent": "ip_address", "params": {}}

    # ── File manager ──────────────────────────────────────────────────────────
    folder_m = re.search(
        r"(?:open|show|go to)\s+(?:my\s+)?(desktop|downloads|documents|"
        r"pictures|photos|videos|music|onedrive|home|c drive|recycle bin)", t)
    if folder_m:
        return {"intent": "open_folder", "params": {"folder": folder_m.group(1)}}

    # ── Close app ─────────────────────────────────────────────────────────────
    close_app_m = re.match(
        r"(?:close|exit|terminate|quit)\s+(?:app\s+|application\s+)?(.+)", t)
    if close_app_m and not any(w in t for w in [
            "computer", "pc", "laptop", "window"]):
        return {"intent": "close_app",
                "params": {"app": close_app_m.group(1).strip()}}

    # ── Install software ──────────────────────────────────────────────────────
    install_m = re.match(
        r"(?:install|setup|download\s+and\s+install)\s+(.+)", t)
    if install_m and not any(w in t for w in ["update", "file"]):
        return {"intent": "install_software",
                "params": {"software": install_m.group(1).strip()}}

    # ── Wi-Fi / Bluetooth / Dark Mode ─────────────────────────────────────────
    wifi_m = re.match(r"(?:turn\s+)?(on|off|enable|disable)\s+wifi", t)
    if wifi_m:
        return {"intent": "toggle_wifi",
                "params": {"state": wifi_m.group(1) in ("on", "enable")}}
    bt_m = re.match(r"(?:turn\s+)?(on|off|enable|disable)\s+bluetooth", t)
    if bt_m:
        return {"intent": "toggle_bluetooth",
                "params": {"state": bt_m.group(1) in ("on", "enable")}}
    dm_m = re.match(r"(?:turn\s+)?(on|off|enable|disable)\s+dark\s*mode", t)
    if dm_m:
        return {"intent": "toggle_dark_mode",
                "params": {"state": dm_m.group(1) in ("on", "enable")}}

    # ── Git ───────────────────────────────────────────────────────────────────
    if any(p in t for p in ["git status", "repo status"]):
        return {"intent": "git_status", "params": {}}
    if any(p in t for p in ["git push", "push to github", "push code"]):
        return {"intent": "git_push", "params": {}}
    if any(p in t for p in ["git pull", "pull code", "pull latest"]):
        return {"intent": "git_pull", "params": {}}
    commit_m = re.match(r"(?:git commit|commit my changes|commit)\s+(.+)", t)
    if commit_m:
        return {"intent": "git_commit",
                "params": {"message": commit_m.group(1).strip()}}

    # ── Open GitHub ───────────────────────────────────────────────────────────
    if any(p in t for p in ["open github", "go to github"]):
        return {"intent": "open_website",
                "params": {"url": "https://www.github.com", "name": "GitHub"}}

    # ── WhatsApp ──────────────────────────────────────────────────────────────
    wa_m = re.search(r"(?:whatsapp|message|call)\s+(.+?)(?:\s+on\s+whatsapp)?$", t)
    if wa_m and ("whatsapp" in t or t.startswith("call ") or t.startswith("message ")):
        if "whatsapp" in t:
            target = wa_m.group(1).replace("on whatsapp", "").strip()
            if target:
                return {"intent": "whatsapp_action", "params": {"target": target}}

    # ── Code creation ─────────────────────────────────────────────────────────
    _CODE_TRIGGERS = [
        "write code", "write python", "generate code", "code for",
        "write a program", "write script", "build a calculator",
        "build a game", "create code", "create a script",
    ]
    if any(p in t for p in _CODE_TRIGGERS):
        return {"intent": "write_code_to_file",
                "params": {"description": text}}

    create_file_m = re.match(
        r"(?:create|make|new)\s+(?:a\s+)?file\s+(?:called|named)?\s*(\S+)", t)
    if create_file_m:
        return {"intent": "create_file",
                "params": {"filename": create_file_m.group(1).strip(), "location": ""}}

    # ── Chat history ──────────────────────────────────────────────────────────
    if any(p in t for p in ["clear chat history", "reset chat",
                             "clear conversation"]):
        return {"intent": "clear_chat_history", "params": {}}

    # ── Check Ollama ──────────────────────────────────────────────────────────
    if any(p in t for p in ["check ollama", "ollama status", "is ollama connected"]):
        return {"intent": "check_ollama", "params": {}}

    # ── Open website / app ────────────────────────────────────────────────────
    open_m = re.search(
        r"(?:open|go to|browse|navigate to|take me to)\s+(.+?)(?:\s+(?:website|site|page|app))?$",
        t
    )
    if open_m:
        target = open_m.group(1).strip()
        target_norm = APP_ALIASES.get(target, target)
        if target_norm in WEBSITE_MAP:
            return {"intent": "open_website",
                    "params": {"url": WEBSITE_MAP[target_norm], "name": target_norm}}
        if "." in target and " " not in target:
            url = target if target.startswith("http") else f"https://{target}"
            return {"intent": "open_website", "params": {"url": url, "name": target}}
        if target_norm in FOLDER_NAMES:
            return {"intent": "open_folder", "params": {"folder": target_norm}}
        return {"intent": "open_app", "params": {"app": target_norm}}

    # ── Launch / Start (generic) ──────────────────────────────────────────────
    launch_m = re.search(
        r"(?:launch|start|run|execute)\s+(.+?)(?:\s+(?:app|application|program))?$", t)
    if launch_m:
        app_name = APP_ALIASES.get(launch_m.group(1).strip(), launch_m.group(1).strip())
        return {"intent": "open_app", "params": {"app": app_name}}

    # ── Fallback: AI question ─────────────────────────────────────────────────
    return {"intent": "question", "params": {"query": text}}
