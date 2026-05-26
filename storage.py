"""
storage.py — JSON-backed persistence.

Tracks every job the agent has already applied to so nothing is applied twice.
All operations are safe: a missing file is treated as an empty state.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from config import STORAGE_FILE

logger = logging.getLogger("job_agent")

# ── Internal helpers ───────────────────────────────────────────────────────

def _job_key(job: dict) -> str:
    """Stable deduplication key: lowercase 'company::title'."""
    company = job.get("company", "").strip().lower()
    title = job.get("title", "").strip().lower()
    return f"{company}::{title}"


def _load_json() -> dict:
    """Load the full JSON storage file. Returns empty structure on any error."""
    if not os.path.exists(STORAGE_FILE):
        return {"applied": [], "runs": []}
    try:
        with open(STORAGE_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        # Ensure expected top-level keys exist
        data.setdefault("applied", [])
        data.setdefault("runs", [])
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.error(f"Failed to read {STORAGE_FILE}: {exc} — starting fresh.")
        return {"applied": [], "runs": []}


def _save_json(data: dict) -> None:
    """Persist the full data dict to disk, creating parent dirs if needed."""
    try:
        dir_name = os.path.dirname(STORAGE_FILE)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(STORAGE_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
    except OSError as exc:
        logger.error(f"Failed to write {STORAGE_FILE}: {exc}")


# ── Public API ─────────────────────────────────────────────────────────────

def load_applied() -> set:
    """
    Return the set of 'company::title' keys for every previously applied job.
    """
    data = _load_json()
    return set(data["applied"])


def save_applied(applied: set) -> None:
    """
    Persist the full applied set, preserving any existing run logs.
    """
    data = _load_json()
    data["applied"] = sorted(applied)  # sorted for readable diffs
    _save_json(data)


def is_already_applied(job: dict, applied: set) -> bool:
    """Return True if this job's key exists in the applied set."""
    return _job_key(job) in applied


def mark_applied(job: dict, applied: set) -> set:
    """Add job to the applied set and return the updated set (immutable-style)."""
    new_set = set(applied)
    new_set.add(_job_key(job))
    return new_set


def save_run_log(
    jobs_found: int,
    jobs_matched: int,
    jobs_emailed: int,
    jobs_drafted: int,
) -> None:
    """
    Append a summary of this agent run to the 'runs' array in storage.
    Useful for auditing how the agent has performed over time.
    """
    data = _load_json()
    run_entry: dict[str, Any] = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "jobs_found": jobs_found,
        "jobs_matched": jobs_matched,
        "jobs_emailed": jobs_emailed,
        "jobs_drafted": jobs_drafted,
    }
    data["runs"].append(run_entry)
    _save_json(data)
    logger.debug(f"Run log saved: {run_entry}")
