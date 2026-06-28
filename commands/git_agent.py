"""
Git Agent — Voice-controlled Git and GitHub operations.

Commands:
  "Show git status"                       → git status (spoken summary)
  "Commit my changes with message [msg]"  → git add -A && git commit -m "[msg]"
  "Push to GitHub"                        → git push
  "Pull latest"                           → git pull
  "Create branch [name]"                  → git checkout -b [name]
  "Switch to branch [name]"               → git checkout [name]
  "Show git log"                          → Last 5 commits spoken
  "Initialize git"                        → git init
  "Clone [url]"                           → git clone
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

log = logging.getLogger("jarvis.git")


def _run_git(args: list[str], cwd: str | None = None, timeout: int = 30) -> tuple[int, str, str]:
    """Run a git command. Returns (returncode, stdout, stderr)."""
    cmd = ["git"] + args
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=cwd, timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return 1, "", "Git is not installed or not in PATH."
    except subprocess.TimeoutExpired:
        return 1, "", "Git command timed out."
    except Exception as e:
        return 1, "", str(e)


def _get_repo_root() -> str | None:
    """Find the nearest git repo root from the current working directory."""
    from commands.memory import _load
    # Check if user has a preferred project path in memory
    data = _load()
    for key in ["current project", "active project", "working directory"]:
        if key in data:
            p = data[key]["value"]
            rc, _, _ = _run_git(["rev-parse", "--git-dir"], cwd=p)
            if rc == 0:
                return p

    # Try Desktop, Documents, Projects
    user = os.environ.get("USERPROFILE", str(Path.home()))
    search_dirs = [
        os.path.join(user, "Projects"),
        os.path.join(user, "Desktop"),
        os.path.join(user, "Documents"),
    ]
    for d in search_dirs:
        if os.path.isdir(d):
            rc, _, _ = _run_git(["rev-parse", "--git-dir"], cwd=d)
            if rc == 0:
                return d

    # Check current working dir
    rc, _, _ = _run_git(["rev-parse", "--git-dir"])
    if rc == 0:
        return os.getcwd()

    return None


def git_status() -> tuple[bool, str]:
    """Get a spoken summary of git status."""
    cwd = _get_repo_root()
    rc, out, err = _run_git(["status", "--short"], cwd=cwd)
    if rc != 0:
        return False, f"Git status failed: {err or 'Not a git repository.'}"

    if not out:
        rc2, branch, _ = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
        branch = branch if rc2 == 0 else "unknown"
        return True, f"Working tree is clean on branch {branch}."

    lines = out.splitlines()
    modified = [l for l in lines if l.startswith(" M") or l.startswith("M")]
    added    = [l for l in lines if l.startswith("A") or l.startswith("??")]
    deleted  = [l for l in lines if l.startswith(" D") or l.startswith("D")]

    parts = []
    if modified:
        parts.append(f"{len(modified)} modified file{'s' if len(modified) > 1 else ''}")
    if added:
        parts.append(f"{len(added)} untracked file{'s' if len(added) > 1 else ''}")
    if deleted:
        parts.append(f"{len(deleted)} deleted file{'s' if len(deleted) > 1 else ''}")

    return True, "Git status: " + ", ".join(parts) + "." if parts else "Working tree is clean."


def git_commit(message: str) -> tuple[bool, str]:
    """Stage all changes and commit with a message."""
    cwd = _get_repo_root()
    if not cwd:
        return False, "I couldn't find a git repository to commit to."

    # Stage all
    rc, _, err = _run_git(["add", "-A"], cwd=cwd)
    if rc != 0:
        return False, f"Git add failed: {err}"

    # Commit
    rc, out, err = _run_git(["commit", "-m", message], cwd=cwd)
    if rc != 0:
        if "nothing to commit" in err or "nothing to commit" in out:
            return True, "Nothing to commit. Working tree is clean."
        return False, f"Git commit failed: {err}"

    # Count files changed
    lines = out.splitlines()
    summary = lines[0] if lines else f"Committed: {message}"
    return True, f"Committed successfully. {summary}"


def git_push() -> tuple[bool, str]:
    """Push to the remote origin."""
    cwd = _get_repo_root()
    if not cwd:
        return False, "I couldn't find a git repository to push."

    rc, out, err = _run_git(["push"], cwd=cwd, timeout=60)
    if rc != 0:
        if "upstream" in err:
            # Try to push with set-upstream
            rc2, out2, err2 = _run_git(
                ["push", "--set-upstream", "origin", "HEAD"],
                cwd=cwd, timeout=60
            )
            if rc2 == 0:
                return True, "Pushed and set upstream tracking branch."
            return False, f"Push failed: {err2}"
        return False, f"Push failed: {err or out}"

    return True, "Pushed to GitHub successfully."


def git_pull() -> tuple[bool, str]:
    """Pull latest from remote."""
    cwd = _get_repo_root()
    if not cwd:
        return False, "I couldn't find a git repository to pull."

    rc, out, err = _run_git(["pull"], cwd=cwd, timeout=60)
    if rc != 0:
        return False, f"Pull failed: {err or out}"

    if "Already up to date" in out:
        return True, "Already up to date."
    return True, "Pulled latest changes successfully."


def git_create_branch(name: str) -> tuple[bool, str]:
    """Create and switch to a new branch."""
    cwd = _get_repo_root()
    if not cwd:
        return False, "No git repository found."

    branch = name.strip().replace(" ", "-").lower()
    rc, _, err = _run_git(["checkout", "-b", branch], cwd=cwd)
    if rc != 0:
        return False, f"Could not create branch '{branch}': {err}"
    return True, f"Created and switched to branch '{branch}'."


def git_switch_branch(name: str) -> tuple[bool, str]:
    """Switch to an existing branch."""
    cwd = _get_repo_root()
    if not cwd:
        return False, "No git repository found."

    branch = name.strip().replace(" ", "-").lower()
    rc, _, err = _run_git(["checkout", branch], cwd=cwd)
    if rc != 0:
        return False, f"Could not switch to branch '{branch}': {err}"
    return True, f"Switched to branch '{branch}'."


def git_log() -> tuple[bool, str]:
    """Speak the last 5 commit messages."""
    cwd = _get_repo_root()
    if not cwd:
        return False, "No git repository found."

    rc, out, err = _run_git(
        ["log", "--oneline", "-5", "--format=%h %s"],
        cwd=cwd
    )
    if rc != 0:
        return False, f"Git log failed: {err}"
    if not out:
        return True, "No commits yet."

    lines = out.splitlines()
    spoken = "Last commits: " + ". ".join(lines) + "."
    return True, spoken


def git_init() -> tuple[bool, str]:
    """Initialize a git repository in the current directory."""
    rc, out, err = _run_git(["init"])
    if rc != 0:
        return False, f"Git init failed: {err}"
    return True, "Git repository initialized."


def git_clone(url: str) -> tuple[bool, str]:
    """Clone a remote repository."""
    from commands.memory import get_projects_root
    dest = str(get_projects_root())
    rc, out, err = _run_git(["clone", url.strip()], cwd=dest, timeout=120)
    if rc != 0:
        return False, f"Clone failed: {err or out}"
    return True, f"Repository cloned to {dest}."
