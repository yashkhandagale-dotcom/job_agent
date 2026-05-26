"""
email_hunter.py — Deep email hunting pipeline for a given company + job.

Hunt chain (stops as soon as an email is found):
  Step 1 — Job listing URL itself         (scrape the page we already have)
  Step 2 — Company careers page           (search Google → scrape /careers /jobs)
  Step 3 — Company main website           (scrape homepage contact/about pages)
  Step 4 — Hunter.io public search        (free, no key, domain email patterns)
  Step 5 — Founder / hiring manager hunt  (search "{company} founder CEO LinkedIn email")
  Step 6 — Give up → return None          (caller will save a draft)

Each step is isolated; failure never blocks the next step.
"""

import logging
import re
import time
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("job_agent")

# ── Constants ──────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
}

TIMEOUT = 12  # seconds per request

# Regex that matches most real email addresses
EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)

# Emails we never want (generic/noreply noise)
IGNORE_DOMAINS = {
    "example.com", "sentry.io", "wixpress.com", "cloudflare.com",
    "google.com", "googleapis.com", "github.com", "amazonaws.com",
    "noreply", "no-reply", "mailer", "bounce", "notifications",
}

# Career-page path hints — tried in order on the company domain
CAREER_PATHS = [
    "/careers", "/jobs", "/work-with-us", "/join-us",
    "/about/careers", "/company/careers", "/en/careers",
    "/open-roles", "/hiring", "/team/join",
]

# Contact-page path hints
CONTACT_PATHS = [
    "/contact", "/contact-us", "/about", "/about-us",
    "/team", "/people", "/hello",
]


# ── Helpers ────────────────────────────────────────────────────────────────

def _clean_emails(raw: list[str], prefer_domain: str = "") -> list[str]:
    """
    De-dup and filter noise from a raw list of email strings.
    If prefer_domain is set, emails matching it are sorted first.
    """
    seen: set[str] = set()
    result: list[str] = []
    for email in raw:
        e = email.lower().strip()
        if e in seen:
            continue
        seen.add(e)
        # Skip if any ignore token appears anywhere in the address
        if any(bad in e for bad in IGNORE_DOMAINS):
            continue
        # Skip obviously fake / templated addresses
        if "example" in e or "yourdomain" in e or "domain.com" in e:
            continue
        result.append(e)

    if prefer_domain:
        pd = prefer_domain.lower()
        result.sort(key=lambda e: (0 if pd in e else 1))

    return result


def _extract_emails_from_html(html: str) -> list[str]:
    """Pull all email-like strings out of raw HTML."""
    return EMAIL_RE.findall(html)


def _fetch(url: str, client: httpx.Client) -> str | None:
    """Fetch a URL and return raw HTML, or None on any error."""
    try:
        resp = client.get(url, headers=HEADERS, timeout=TIMEOUT, follow_redirects=True)
        resp.raise_for_status()
        return resp.text
    except Exception as exc:
        logger.debug(f"  Fetch failed [{url}]: {exc}")
        return None


def _google_search_first_url(query: str, client: httpx.Client) -> str | None:
    """
    Hit DuckDuckGo HTML search (no API key needed) and return the first
    organic result URL, or None.
    """
    try:
        resp = client.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={**HEADERS, "Accept": "text/html"},
            timeout=TIMEOUT,
            follow_redirects=True,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        # DDG wraps results in <a class="result__url"> or <a class="result__a">
        for a in soup.select("a.result__a, a.result__url"):
            href = a.get("href", "")
            if href.startswith("http") and "duckduckgo" not in href:
                return href
        return None
    except Exception as exc:
        logger.debug(f"  DuckDuckGo search failed: {exc}")
        return None


def _domain_from_url(url: str) -> str:
    """Extract bare domain (no scheme/path) from a URL."""
    try:
        parsed = urlparse(url)
        return parsed.netloc.lstrip("www.")
    except Exception:
        return ""


# ── Hunt Steps ─────────────────────────────────────────────────────────────

def _step1_job_page(job: dict, client: httpx.Client) -> str | None:
    """Step 1 — scrape the job listing URL we already have."""
    url = job.get("url", "")
    if not url:
        return None
    logger.debug(f"  [Hunter S1] Scraping job page: {url}")
    html = _fetch(url, client)
    if not html:
        return None
    emails = _clean_emails(_extract_emails_from_html(html))
    if emails:
        logger.info(f"  [Hunter S1] Found email on job page: {emails[0]}")
        return emails[0]
    return None


def _step2_careers_page(company: str, job_url: str, client: httpx.Client) -> str | None:
    """
    Step 2 — find the company careers page via:
      a) guessing paths on the domain we already know from job_url
      b) DuckDuckGo search fallback
    """
    # a) Try known domain first
    domain = _domain_from_url(job_url)
    if domain:
        for path in CAREER_PATHS:
            url = f"https://{domain}{path}"
            logger.debug(f"  [Hunter S2a] Trying careers path: {url}")
            html = _fetch(url, client)
            if html:
                emails = _clean_emails(_extract_emails_from_html(html), domain)
                if emails:
                    logger.info(f"  [Hunter S2a] Found email on careers page: {emails[0]}")
                    return emails[0]
        time.sleep(0.5)

    # b) DuckDuckGo fallback
    query = f"{company} careers jobs hiring email site:jobs OR site:careers OR site:{domain}"
    logger.debug(f"  [Hunter S2b] DDG search: {query}")
    url = _google_search_first_url(query, client)
    if url:
        html = _fetch(url, client)
        if html:
            emails = _clean_emails(_extract_emails_from_html(html), domain)
            if emails:
                logger.info(f"  [Hunter S2b] Found email via DDG careers: {emails[0]}")
                return emails[0]
    return None


def _step3_company_website(company: str, job_url: str, client: httpx.Client) -> str | None:
    """
    Step 3 — scrape the company homepage + contact/about pages.
    """
    domain = _domain_from_url(job_url)

    # If no domain yet, search for the company website
    if not domain:
        query = f"{company} official website"
        logger.debug(f"  [Hunter S3] DDG search for company site: {query}")
        found_url = _google_search_first_url(query, client)
        if found_url:
            domain = _domain_from_url(found_url)

    if not domain:
        return None

    for path in [""] + CONTACT_PATHS:
        url = f"https://{domain}{path}"
        logger.debug(f"  [Hunter S3] Trying contact path: {url}")
        html = _fetch(url, client)
        if html:
            emails = _clean_emails(_extract_emails_from_html(html), domain)
            if emails:
                logger.info(f"  [Hunter S3] Found email on company site: {emails[0]}")
                return emails[0]
        time.sleep(0.3)

    return None


def _step4_hunter_io(company: str, job_url: str, client: httpx.Client) -> str | None:
    """
    Step 4 — Hunter.io domain search (public, no auth for pattern).
    Hits the public-facing search page and scrapes visible email patterns.
    """
    domain = _domain_from_url(job_url)
    if not domain:
        return None

    url = f"https://hunter.io/search/{domain}"
    logger.debug(f"  [Hunter S4] Hunter.io: {url}")
    html = _fetch(url, client)
    if not html:
        return None

    emails = _clean_emails(_extract_emails_from_html(html), domain)
    if emails:
        logger.info(f"  [Hunter S4] Found email via Hunter.io: {emails[0]}")
        return emails[0]

    # Also try to extract a pattern like {first}.{last}@domain.com
    pattern_re = re.search(r"\{[\w.]+\}@" + re.escape(domain), html)
    if pattern_re:
        logger.info(f"  [Hunter S4] Email pattern found: {pattern_re.group()} (cannot resolve name — skipping)")

    return None


def _step5_founder_search(company: str, client: httpx.Client) -> str | None:
    """
    Step 5 — search for the founder / CTO / hiring manager email via DDG.
    Tries several queries and scrapes the first result of each.
    """
    queries = [
        f"{company} founder CEO email contact",
        f"{company} CTO engineering hiring manager email",
        f'"{company}" hiring engineer email site:linkedin.com OR site:twitter.com OR site:crunchbase.com',
    ]

    for query in queries:
        logger.debug(f"  [Hunter S5] Founder search: {query}")
        url = _google_search_first_url(query, client)
        if not url:
            continue
        html = _fetch(url, client)
        if not html:
            continue
        emails = _clean_emails(_extract_emails_from_html(html))
        if emails:
            logger.info(f"  [Hunter S5] Found founder/hiring email: {emails[0]}")
            return emails[0]
        time.sleep(0.5)

    return None


# ── Public entry point ─────────────────────────────────────────────────────

def hunt_email(job: dict) -> str | None:
    """
    Run the full hunt chain for a job dict.
    Returns the best email found, or None if all steps fail.

    Chain:
      S1 → job page
      S2 → careers page
      S3 → company website
      S4 → Hunter.io
      S5 → founder/hiring manager search
    """
    company = job.get("company", "Unknown")
    title   = job.get("title", "Role")
    logger.info(f"  [Hunter] Starting email hunt for {title} @ {company}…")

    with httpx.Client(follow_redirects=True) as client:

        email = _step1_job_page(job, client)
        if email:
            return email

        email = _step2_careers_page(company, job.get("url", ""), client)
        if email:
            return email

        email = _step3_company_website(company, job.get("url", ""), client)
        if email:
            return email

        email = _step4_hunter_io(company, job.get("url", ""), client)
        if email:
            return email

        email = _step5_founder_search(company, client)
        if email:
            return email

    logger.info(f"  [Hunter] No email found after all steps — will save draft.")
    return None