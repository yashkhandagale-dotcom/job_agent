"""
main.py — CLI entry point for the Automated Job Application Agent.

Usage:
  python main.py run    # Run the pipeline once immediately
  python main.py watch  # Run now, then repeat every day at 09:00
"""

import asyncio
import sys
import time
import logging

# ── Bootstrap config + logging before other local imports ─────────────────
from config import setup_logging, validate_config, MATCH_THRESHOLD

logger = setup_logging()

# ── Local module imports ───────────────────────────────────────────────────
from scraper import scrape_all_jobs
from matcher import match_job, is_match, is_experience_fit
from emailer import generate_email, send_email, save_draft
from email_hunter import hunt_email
from storage import (
    load_applied,
    save_applied,
    is_already_applied,
    mark_applied,
    save_run_log,
)

# Run counter (persists within a single process)
_run_number: int = 0


# ── Core pipeline ──────────────────────────────────────────────────────────

def run_agent() -> None:
    """Execute the full job-application pipeline end-to-end."""
    global _run_number
    _run_number += 1
    logger.info(f"{'='*55}")
    logger.info(f"Agent starting run #{_run_number}")
    logger.info(f"{'='*55}")

    # ── 1. Load previously applied jobs ───────────────────────────────────
    applied: set = load_applied()
    logger.info(f"Loaded {len(applied)} previously applied job(s) from storage.")

    # ── 2. Scrape jobs ─────────────────────────────────────────────────────
    try:
        jobs = asyncio.run(scrape_all_jobs())
    except Exception as exc:
        logger.error(f"Fatal scraping error: {exc}")
        jobs = []

    logger.info(f"Found {len(jobs)} job(s) across all sources.")

    if not jobs:
        logger.warning("No jobs found this run — check scraper logs for errors.")
        save_run_log(0, 0, 0, 0)
        return

    # ── 3. Process each job ────────────────────────────────────────────────
    jobs_found    = len(jobs)
    jobs_matched  = 0
    jobs_emailed  = 0
    jobs_drafted  = 0

    for job in jobs:
        # Each job is wrapped in its own try/except so one failure never
        # aborts the whole run.
        try:
            title   = job.get("title", "Unknown Role")
            company = job.get("company", "Unknown Company")
            source  = job.get("source", "")

            # ── a. Skip already-applied ────────────────────────────────────
            if is_already_applied(job, applied):
                logger.info(f"Skipping {title} @ {company} — already applied.")
                continue

            # ── b. Score with Claude ───────────────────────────────────────
            logger.info(f"Analysing: {title} @ {company} [{source}]")
            analysis = match_job(job)
            pct      = analysis.get("match_percent", 0)
            reason   = analysis.get("reasoning", "")
            logger.info(f"  Score: {pct}% — {reason}")

            # ── c. Filter by threshold ─────────────────────────────────────
            if not is_match(analysis, MATCH_THRESHOLD):
                logger.info(
                    f"  SKIP {pct}% — {title} @ {company} "
                    f"(below {MATCH_THRESHOLD}% threshold)"
                )
                continue

            # ── d2. Filter by experience requirement ───────────────────────
            exp_req = analysis.get("exp_required_years", 0)
            if not is_experience_fit(analysis):
                logger.info(
                    f"  SKIP {title} @ {company} "
                    f"— requires {exp_req}+ yrs experience (candidate has 1 yr)"
                )
                continue

            # ── d. It's a match! ───────────────────────────────────────────
            jobs_matched += 1
            logger.info(f"  MATCH {pct}% — {title} @ {company}")

            # ── e. Generate personalised email ─────────────────────────────
            email_content = generate_email(job, analysis)
            subject = email_content.get("subject", "Application")
            body    = email_content.get("body", "")

            # ── f. Hunt for email if not already in job data ──────────────
            to_email = job.get("email", "").strip()
            if not to_email:
                to_email = hunt_email(job) or ""

            # ── g. Send or draft ───────────────────────────────────────────
            if to_email:
                logger.info(f"  Sending email to {to_email}…")
                sent = send_email(to_email, subject, body)
                if sent:
                    jobs_emailed += 1
                else:
                    logger.warning(
                        f"  Send failed — falling back to draft for {title} @ {company}"
                    )
                    save_draft(job, subject, body)
                    jobs_drafted += 1
            else:
                logger.info(
                    f"  No email found after deep hunt — saving draft."
                )
                save_draft(job, subject, body)
                jobs_drafted += 1

            # ── g. Mark as applied ─────────────────────────────────────────
            applied = mark_applied(job, applied)

        except Exception as exc:
            # Catch-all: log and continue with next job
            logger.error(
                f"Unhandled error processing {job.get('title')} @ "
                f"{job.get('company')}: {exc}",
                exc_info=True,
            )
            continue

    # ── 4. Persist updated applied set ────────────────────────────────────
    save_applied(applied)

    # ── 5. Persist run summary ─────────────────────────────────────────────
    save_run_log(jobs_found, jobs_matched, jobs_emailed, jobs_drafted)

    # ── 6. Print summary ───────────────────────────────────────────────────
    logger.info(f"{'='*55}")
    logger.info(
        f"Run complete.  Found: {jobs_found}  |  "
        f"Matched: {jobs_matched}  |  "
        f"Emailed: {jobs_emailed}  |  "
        f"Drafted: {jobs_drafted}"
    )
    logger.info(f"{'='*55}")


# ── Watch mode ─────────────────────────────────────────────────────────────

def watch() -> None:
    """Run agent immediately, then schedule it every day at 09:00."""
    try:
        import schedule
    except ImportError:
        logger.error("'schedule' package not installed. Run: pip install schedule")
        sys.exit(1)

    logger.info("Watch mode enabled — running now, then daily at 09:00.")
    run_agent()  # immediate first run

    schedule.every().day.at("09:00").do(run_agent)
    logger.info("Scheduler armed. Next run at 09:00 tomorrow. Press Ctrl+C to stop.")

    while True:
        schedule.run_pending()
        time.sleep(60)


# ── CLI ────────────────────────────────────────────────────────────────────

def _print_usage() -> None:
    print(
        "\nUsage:\n"
        "  python main.py run    — run the agent once\n"
        "  python main.py watch  — run now, then daily at 09:00\n"
    )


def main() -> None:
    if len(sys.argv) < 2:
        _print_usage()
        sys.exit(1)

    command = sys.argv[1].lower()

    # Warn about missing config but don't block execution
    validate_config(logger)

    if command == "run":
        run_agent()
    elif command == "watch":
        try:
            watch()
        except KeyboardInterrupt:
            logger.info("Watch mode stopped by user.")
    else:
        logger.error(f"Unknown command: '{command}'")
        _print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()