"""
scraper.py — Async job scraping from multiple reliable public API sources.

Sources:
  • Remotive API     — remote tech jobs, free JSON API, no auth needed
  • Adzuna API       — large job board with India support, free tier available
  • The Muse API     — startup / tech jobs, free JSON API, no auth needed

Why APIs instead of HTML scraping:
  • Wellfound returns HTTP 403 (Cloudflare bot protection)
  • YC Work at a Startup requires JS rendering (React SPA)
  Both are unreliable with plain httpx + BeautifulSoup.

Design principles:
  • Each source isolated; one failure never affects others.
  • Results normalised to a shared schema.
  • Deduplicated by (company, title) before return.
"""

import asyncio
import logging
from typing import Optional

import httpx

from config import MAX_JOBS_PER_RUN

logger = logging.getLogger("job_agent")

# ── Constants ──────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html,*/*;q=0.8",
}

REQUEST_TIMEOUT = 20  # seconds

# ── Remotive API (free, no key needed) ────────────────────────────────────
# Docs: https://remotive.com/api/remote-jobs
REMOTIVE_URL = "https://remotive.com/api/remote-jobs"
REMOTIVE_PARAMS = {
    "category": "software-dev",
    "limit": 20,
}

# ── The Muse API (free, no key needed for basic use) ─────────────────────
# Docs: https://www.themuse.com/developers/api/v2
MUSE_URL = "https://www.themuse.com/api/public/jobs"
MUSE_PARAMS = {
    "category": "Computer and IT",
    "level": "Entry Level",
    "page": 0,
}

# ── Jobicy API (free, no key, remote jobs) ────────────────────────────────
# Docs: https://jobicy.com/jobs-rss-feed
JOBICY_URL = "https://jobicy.com/api/v2/remote-jobs"
JOBICY_PARAMS = {
    "count": 20,
    "tag": "software engineer",
}


# ── Utility ────────────────────────────────────────────────────────────────

def _truncate(text: str, max_chars: int = 500) -> str:
    """Return first max_chars of text, trimmed of whitespace."""
    if not text:
        return ""
    cleaned = " ".join(str(text).split())
    return cleaned[:max_chars]


def _dedup(jobs: list[dict]) -> list[dict]:
    """Remove duplicate jobs by (company lowercase + title lowercase) key."""
    seen: set[str] = set()
    unique: list[dict] = []
    for job in jobs:
        key = f"{job.get('company', '').lower()}::{job.get('title', '').lower()}"
        if key not in seen:
            seen.add(key)
            unique.append(job)
    return unique


# ── Remotive scraper ───────────────────────────────────────────────────────

async def _scrape_remotive(client: httpx.AsyncClient) -> list[dict]:
    """
    Fetch software dev jobs from Remotive's public JSON API.
    Returns list of job dicts; returns [] on any error.
    """
    jobs: list[dict] = []
    try:
        logger.info("Fetching Remotive API…")
        resp = await client.get(
            REMOTIVE_URL,
            params=REMOTIVE_PARAMS,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        for item in data.get("jobs", []):
            try:
                jobs.append({
                    "title": item.get("title", ""),
                    "company": item.get("company_name", "Unknown"),
                    "location": item.get("candidate_required_location", "Remote"),
                    "description": _truncate(item.get("description", "")),
                    "url": item.get("url", ""),
                    "source": "Remotive",
                    "email": "",
                })
            except Exception as exc:
                logger.debug(f"Remotive item parse error (skipping): {exc}")

        logger.info(f"Remotive: fetched {len(jobs)} job(s).")

    except httpx.HTTPStatusError as exc:
        logger.error(f"Remotive HTTP {exc.response.status_code}: {exc}")
    except httpx.RequestError as exc:
        logger.error(f"Remotive request failed: {exc}")
    except Exception as exc:
        logger.error(f"Remotive unexpected error: {exc}")

    return jobs


# ── The Muse scraper ───────────────────────────────────────────────────────

async def _scrape_muse(client: httpx.AsyncClient) -> list[dict]:
    """
    Fetch tech jobs from The Muse's public JSON API.
    Returns list of job dicts; returns [] on any error.
    """
    jobs: list[dict] = []
    try:
        logger.info("Fetching The Muse API…")
        resp = await client.get(
            MUSE_URL,
            params=MUSE_PARAMS,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        for item in data.get("results", []):
            try:
                # Location: list of dicts with "name" key
                locations = item.get("locations", [])
                location = locations[0].get("name", "Remote") if locations else "Remote"

                # Levels: list of dicts with "name" key
                levels = item.get("levels", [])
                level_str = ", ".join(lv.get("name", "") for lv in levels)

                company = item.get("company", {}).get("name", "Unknown")
                ref_url = item.get("refs", {}).get("landing_page", "")

                jobs.append({
                    "title": item.get("name", ""),
                    "company": company,
                    "location": location,
                    "description": _truncate(f"{level_str} | {item.get('contents', '')}"),
                    "url": ref_url,
                    "source": "The Muse",
                    "email": "",
                })
            except Exception as exc:
                logger.debug(f"The Muse item parse error (skipping): {exc}")

        logger.info(f"The Muse: fetched {len(jobs)} job(s).")

    except httpx.HTTPStatusError as exc:
        logger.error(f"The Muse HTTP {exc.response.status_code}: {exc}")
    except httpx.RequestError as exc:
        logger.error(f"The Muse request failed: {exc}")
    except Exception as exc:
        logger.error(f"The Muse unexpected error: {exc}")

    return jobs


# ── Jobicy scraper ─────────────────────────────────────────────────────────

async def _scrape_jobicy(client: httpx.AsyncClient) -> list[dict]:
    """
    Fetch remote software jobs from Jobicy's public JSON API.
    Returns list of job dicts; returns [] on any error.
    """
    jobs: list[dict] = []
    try:
        logger.info("Fetching Jobicy API…")
        resp = await client.get(
            JOBICY_URL,
            params=JOBICY_PARAMS,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        for item in data.get("jobs", []):
            try:
                jobs.append({
                    "title": item.get("jobTitle", ""),
                    "company": item.get("companyName", "Unknown"),
                    "location": item.get("jobGeo", "Remote"),
                    "description": _truncate(item.get("jobExcerpt", "")),
                    "url": item.get("url", ""),
                    "source": "Jobicy",
                    "email": "",
                })
            except Exception as exc:
                logger.debug(f"Jobicy item parse error (skipping): {exc}")

        logger.info(f"Jobicy: fetched {len(jobs)} job(s).")

    except httpx.HTTPStatusError as exc:
        logger.error(f"Jobicy HTTP {exc.response.status_code}: {exc}")
    except httpx.RequestError as exc:
        logger.error(f"Jobicy request failed: {exc}")
    except Exception as exc:
        logger.error(f"Jobicy unexpected error: {exc}")

    return jobs


# ── Public entry point ─────────────────────────────────────────────────────

async def scrape_all_jobs() -> list[dict]:
    """
    Fetch jobs from all sources concurrently, deduplicate, and cap at MAX_JOBS_PER_RUN.
    This is the only function other modules need to call.
    """
    async with httpx.AsyncClient(follow_redirects=True) as client:
        remotive_jobs, muse_jobs, jobicy_jobs = await asyncio.gather(
            _scrape_remotive(client),
            _scrape_muse(client),
            _scrape_jobicy(client),
        )

    all_jobs = remotive_jobs + muse_jobs + jobicy_jobs
    unique_jobs = _dedup(all_jobs)
    capped = unique_jobs[:MAX_JOBS_PER_RUN]

    logger.info(
        f"Total scraped: {len(all_jobs)}, after dedup: {len(unique_jobs)}, "
        f"capped at {MAX_JOBS_PER_RUN}: {len(capped)}"
    )
    return capped