"""
Startup Commands — HEY CEO OS startup platform command handlers.

Each handler maps to a startup_* intent from nlp_parser.py.
Add new startup commands here without touching hey.py.

Intent → handler mapping:
  startup_hire               → handle_hire
  startup_generate_doc       → handle_generate_doc
  startup_review_contract    → handle_review_contract
  startup_compliance         → handle_compliance
  startup_risks              → handle_risks
  startup_pitch_deck         → handle_pitch_deck
  startup_search_investors   → handle_search_investors
  startup_deploy             → handle_deploy
  startup_open_page          → handle_open_page
  startup_dashboard_summary  → handle_dashboard_summary
  startup_research           → handle_research
"""
from __future__ import annotations

import logging
import time
import webbrowser
import urllib.parse
from typing import Callable

log = logging.getLogger("hey.startup_commands")


# ─── Page URL registry (edit here to add new pages) ──────────────────────────
PAGE_REGISTRY: dict[str, str] = {
    "dashboard":          "dashboard.html",
    "settings":           "settings.html",
    "knowledge_base":     "knowledge-base.html",
    "legal_chat":         "legal-chat.html",
    "contract_review":    "contract-review.html",
    "contracts":          "contract-review.html",
    "document_generator": "document-generator.html",
    "documents":          "document-generator.html",
    "compliance":         "compliance-tracker.html",
    "risk_analyzer":      "risk-analyzer.html",
    "risks":              "risk-analyzer.html",
    "hiring":             "hiring.html",
    "team":               "team.html",
    "analytics":          "analytics.html",
    "crm":                "crm.html",
    "finance":            "finance.html",
    "expenses":           "finance.html",
    "revenue":            "finance.html",
    "sales":              "analytics.html",
    "notifications":      "notifications.html",
    "messages":           "messages.html",
    "calendar":           "calendar.html",
    "email":              "messages.html",
    "roadmap":            "roadmap.html",
    "tasks":              "dashboard.html",
    "pitch":              "pitch-generator.html",
    "investors":          "investors.html",
}

# ─── Document type → display name registry ───────────────────────────────────
DOC_REGISTRY: dict[str, str] = {
    "nda":                  "Non-Disclosure Agreement",
    "founder_agreement":    "Founder Agreement",
    "employment_contract":  "Employment Contract",
    "privacy_policy":       "Privacy Policy",
    "terms_conditions":     "Terms and Conditions",
    "business_plan":        "Business Plan",
    "invoice":              "Invoice",
    "proposal":             "Proposal",
    "investor_update":      "Investor Update",
    "budget":               "Budget",
    "report":               "Report",
    "custom":               "Document",
}


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _open_page(page_key: str, fallback_url: str = "",
               update_hud_fn: Callable | None = None) -> None:
    """Open a local HTML page from PAGE_REGISTRY or fallback_url."""
    from commands.web_handler import open_html_page
    url = PAGE_REGISTRY.get(page_key, fallback_url or f"{page_key}.html")
    open_html_page(url, page_key.replace("_", " ").title())


def _hud_plan(steps: list[str], update_hud_fn: Callable | None) -> None:
    if update_hud_fn:
        update_hud_fn("PLAN_START", steps)


def _hud_active(idx: int, update_hud_fn: Callable | None) -> None:
    if update_hud_fn:
        update_hud_fn("PLAN_STEP_ACTIVE", idx)


def _hud_done(idx: int, update_hud_fn: Callable | None) -> None:
    if update_hud_fn:
        update_hud_fn("PLAN_STEP_COMPLETE", idx)


# ─── Handlers ─────────────────────────────────────────────────────────────────

def handle_hire(params: dict, update_hud_fn: Callable | None = None) -> tuple[bool, str]:
    """Open hiring page and search LinkedIn for the requested role."""
    role = params.get("role", "professional").strip()
    steps = [
        f"Open Hiring page",
        f"Search LinkedIn for {role}",
        "Display candidates",
    ]
    _hud_plan(steps, update_hud_fn)

    _hud_active(0, update_hud_fn)
    _open_page("hiring", update_hud_fn=update_hud_fn)
    time.sleep(0.8)
    _hud_done(0, update_hud_fn)

    _hud_active(1, update_hud_fn)
    from commands.web_handler import linkedin_search
    linkedin_search(role)
    time.sleep(0.5)
    _hud_done(1, update_hud_fn)

    _hud_done(2, update_hud_fn)
    return True, f"Searching LinkedIn for {role}."


def handle_generate_doc(params: dict,
                        update_hud_fn: Callable | None = None) -> tuple[bool, str]:
    """Open document generator and prepare the requested document."""
    doc_type = params.get("doc_type", "custom")
    doc_name = params.get("doc_name",
                          DOC_REGISTRY.get(doc_type, "Document"))

    steps = [
        "Open Document Generator",
        f"Generate {doc_name}",
        "Fill template",
        "Show preview",
    ]
    _hud_plan(steps, update_hud_fn)

    _hud_active(0, update_hud_fn)
    _open_page("document_generator", update_hud_fn=update_hud_fn)
    time.sleep(0.8)
    _hud_done(0, update_hud_fn)

    _hud_active(1, update_hud_fn)
    time.sleep(1.0)
    _hud_done(1, update_hud_fn)

    _hud_active(2, update_hud_fn)
    time.sleep(0.8)
    _hud_done(2, update_hud_fn)

    _hud_done(3, update_hud_fn)
    return True, f"Creating your {doc_name}."


def handle_review_contract(params: dict,
                            update_hud_fn: Callable | None = None) -> tuple[bool, str]:
    """Open contract review page and start analysis."""
    steps = [
        "Open Contract Review",
        "Analyzing risks",
        "Highlighting dangerous clauses",
        "Report ready",
    ]
    _hud_plan(steps, update_hud_fn)

    _hud_active(0, update_hud_fn)
    _open_page("contract_review", update_hud_fn=update_hud_fn)
    time.sleep(0.8)
    _hud_done(0, update_hud_fn)

    _hud_active(1, update_hud_fn)
    time.sleep(1.2)
    _hud_done(1, update_hud_fn)

    _hud_active(2, update_hud_fn)
    time.sleep(0.8)
    _hud_done(2, update_hud_fn)

    _hud_done(3, update_hud_fn)
    return True, "Reviewing your contract."


def handle_compliance(params: dict,
                      update_hud_fn: Callable | None = None) -> tuple[bool, str]:
    """Open compliance tracker and run analysis."""
    steps = [
        "Open Compliance Tracker",
        "Analyzing company compliance",
        "Generating warnings",
    ]
    _hud_plan(steps, update_hud_fn)

    _hud_active(0, update_hud_fn)
    _open_page("compliance", update_hud_fn=update_hud_fn)
    time.sleep(0.8)
    _hud_done(0, update_hud_fn)

    _hud_active(1, update_hud_fn)
    time.sleep(1.0)
    _hud_done(1, update_hud_fn)

    _hud_done(2, update_hud_fn)
    return True, "Opening Compliance Tracker."


def handle_risks(params: dict,
                 update_hud_fn: Callable | None = None) -> tuple[bool, str]:
    """Open risk analyzer and generate recommendations."""
    steps = [
        "Open Risk Analyzer",
        "Generating business risks",
        "Preparing recommendations",
    ]
    _hud_plan(steps, update_hud_fn)

    _hud_active(0, update_hud_fn)
    _open_page("risk_analyzer", update_hud_fn=update_hud_fn)
    time.sleep(0.8)
    _hud_done(0, update_hud_fn)

    _hud_active(1, update_hud_fn)
    time.sleep(1.0)
    _hud_done(1, update_hud_fn)

    _hud_done(2, update_hud_fn)
    return True, "Analyzing startup risks."


def handle_pitch_deck(params: dict,
                      update_hud_fn: Callable | None = None) -> tuple[bool, str]:
    """Open pitch deck generator."""
    steps = ["Open Pitch Generator", "Loading templates"]
    _hud_plan(steps, update_hud_fn)

    _hud_active(0, update_hud_fn)
    _open_page("pitch", update_hud_fn=update_hud_fn)
    time.sleep(0.8)
    _hud_done(0, update_hud_fn)
    _hud_done(1, update_hud_fn)

    return True, "Opening pitch deck generator."


def handle_search_investors(params: dict,
                             update_hud_fn: Callable | None = None) -> tuple[bool, str]:
    """Open investor search on AngelList."""
    steps = ["Opening investor search", "Loading AngelList"]
    _hud_plan(steps, update_hud_fn)

    _hud_active(0, update_hud_fn)
    from commands.web_handler import search_investors
    search_investors()
    time.sleep(0.5)
    _hud_done(0, update_hud_fn)
    _hud_done(1, update_hud_fn)

    return True, "Searching investors on AngelList."


def handle_deploy(params: dict,
                  update_hud_fn: Callable | None = None) -> tuple[bool, str]:
    """Open Vercel for deployment."""
    steps = ["Opening deployment platform", "Loading Vercel"]
    _hud_plan(steps, update_hud_fn)

    _hud_active(0, update_hud_fn)
    from commands.web_handler import open_website
    open_website("https://vercel.com", "Vercel")
    time.sleep(0.5)
    _hud_done(0, update_hud_fn)
    _hud_done(1, update_hud_fn)

    return True, "Opening Vercel for deployment."


def handle_open_page(params: dict,
                     update_hud_fn: Callable | None = None) -> tuple[bool, str]:
    """Navigate to a specific startup platform page."""
    page    = params.get("page", "dashboard")
    url     = params.get("url", "")
    label   = page.replace("_", " ").title()

    steps = [f"Opening {label}"]
    _hud_plan(steps, update_hud_fn)
    _hud_active(0, update_hud_fn)

    if url:
        from commands.web_handler import open_html_page
        open_html_page(url, label)
    else:
        _open_page(page, update_hud_fn=update_hud_fn)

    time.sleep(0.4)
    _hud_done(0, update_hud_fn)
    return True, f"Opening {label}."


def handle_dashboard_summary(params: dict,
                              update_hud_fn: Callable | None = None) -> tuple[bool, str]:
    """Open dashboard and summarize today's tasks."""
    steps = ["Open Dashboard", "Reading today's data"]
    _hud_plan(steps, update_hud_fn)

    _hud_active(0, update_hud_fn)
    _open_page("dashboard", update_hud_fn=update_hud_fn)
    time.sleep(0.8)
    _hud_done(0, update_hud_fn)
    _hud_done(1, update_hud_fn)

    return True, "Opening dashboard. Summarizing today's tasks."


def handle_research(params: dict,
                    update_hud_fn: Callable | None = None) -> tuple[bool, str]:
    """Run a web research query based on type."""
    query       = params.get("query", "startup research")
    res_type    = params.get("type", "general")
    steps       = [f"Researching {query}"]
    _hud_plan(steps, update_hud_fn)
    _hud_active(0, update_hud_fn)

    from commands.web_handler import market_research
    market_research(query)
    time.sleep(0.4)
    _hud_done(0, update_hud_fn)

    return True, f"Researching {query}."


# ─── Master dispatcher ────────────────────────────────────────────────────────

_HANDLER_MAP: dict[str, Callable] = {
    "startup_hire":              handle_hire,
    "startup_generate_doc":      handle_generate_doc,
    "startup_review_contract":   handle_review_contract,
    "startup_compliance":        handle_compliance,
    "startup_risks":             handle_risks,
    "startup_pitch_deck":        handle_pitch_deck,
    "startup_search_investors":  handle_search_investors,
    "startup_deploy":            handle_deploy,
    "startup_open_page":         handle_open_page,
    "startup_dashboard_summary": handle_dashboard_summary,
    "startup_research":          handle_research,
}


def handle_startup_intent(intent: str, params: dict,
                          update_hud_fn: Callable | None = None) -> tuple[bool, str]:
    """
    Main entry point called by hey.py for all startup_* intents.
    Returns (success, spoken_response).
    """
    handler = _HANDLER_MAP.get(intent)
    if handler is None:
        log.warning("No handler for startup intent: %s", intent)
        return False, f"No handler registered for {intent}."
    try:
        return handler(params, update_hud_fn=update_hud_fn)
    except Exception as e:
        log.error("Startup command failed [%s]: %s", intent, e)
        return False, f"Command failed: {e}"
