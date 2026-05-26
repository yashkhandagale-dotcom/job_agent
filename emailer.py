"""
emailer.py — Generate personalised cold emails via Groq (LLaMA 3.3 70B), send via Gmail SMTP.

Free tier: 14,400 requests/day — get key at https://console.groq.com
"""

import json
import logging
import os
import re
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from groq import Groq

from config import (
    GROQ_API_KEY,
    CANDIDATE_PROFILE,
    DRAFTS_DIR,
    GMAIL_ADDRESS,
    GMAIL_APP_PASSWORD,
)

logger = logging.getLogger("job_agent")

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


_DEFAULT_EMAIL: dict = {
    "subject": "Application for Software Engineer role",
    "body": (
        "Hi,\n\n"
        "I'm interested in joining your team as a software engineer. "
        "Please find my portfolio at yashkhandagale.in.\n\n"
        "Best regards,\nYash Khandagale"
    ),
}


def _parse_json(raw: str, context: str = "") -> dict:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        text = inner.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error(f"Email JSON parse error{' (' + context + ')' if context else ''}: {exc}")
        logger.debug(f"Raw: {raw[:300]}")
        return {}


def _build_email_prompt(job: dict, analysis: dict) -> str:
    p = CANDIDATE_PROFILE
    matched = ", ".join(analysis.get("matched_skills", [])[:3]) or "relevant skills"
    hook = analysis.get("company_hook", "")
    projects = "; ".join(p.get("notable_projects", [])[:2])
    return (
        f"Write a cold job application email for {p['name']}.\n\n"
        f"ROLE: {job.get('title', 'Software Engineer')} at {job.get('company', 'your company')}\n"
        f"CANDIDATE CURRENT ROLE: {p.get('current_role', '')}\n"
        f"MATCHED SKILLS: {matched}\n"
        f"NOTABLE PROJECTS: {projects}\n"
        f"COMPANY HOOK: {hook}\n"
        f"PORTFOLIO: {p['portfolio']}\n"
        f"GITHUB: {p.get('github', '')}\n"
        f"LINKEDIN: {p.get('linkedin', '')}\n"
        f"CANDIDATE EMAIL: {p['email']}\n"
        f"CANDIDATE PHONE: {p['phone']}\n\n"
        f"Rules:\n"
        f"- Subject line must be compelling and specific to the role\n"
        f"- Email body under 150 words\n"
        f"- Mention 3 specific skills that match\n"
        f"- Reference one notable project naturally if relevant\n"
        f"- Include the company hook naturally\n"
        f"- End with portfolio link and contact info\n"
        f"- NO generic phrases like 'I hope this email finds you well'\n"
        f"- Sound like a real human, not a template\n\n"
        f'Return ONLY valid JSON, no markdown:\n'
        f'{{"subject": "<email subject>", "body": "<full email body>"}}'
    )


def generate_email(job: dict, analysis: dict) -> dict:
    """Use Groq to generate a personalised cold email. Falls back to default on error."""
    try:
        client = _get_client()
        prompt = _build_email_prompt(job, analysis)

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.choices[0].message.content or ""
        result = _parse_json(raw, context=f"{job.get('title')} @ {job.get('company')}")

        if result.get("subject") and result.get("body"):
            time.sleep(0.5)
            return result

        logger.warning("generate_email: incomplete JSON from Groq — using default.")

    except Exception as exc:
        logger.error(f"Groq error in generate_email: {exc}")

    return dict(_DEFAULT_EMAIL)


def _safe_filename(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", text.strip().lower())[:60]


def save_draft(job: dict, subject: str, body: str) -> str:
    os.makedirs(DRAFTS_DIR, exist_ok=True)
    company_slug = _safe_filename(job.get("company", "unknown"))
    title_slug = _safe_filename(job.get("title", "role"))
    filepath = os.path.join(DRAFTS_DIR, f"{company_slug}_{title_slug}.txt")

    try:
        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write(f"To: (fill in manually)\n")
            fh.write(f"Subject: {subject}\n")
            fh.write(f"Job URL: {job.get('url', 'N/A')}\n")
            fh.write(f"Source: {job.get('source', 'N/A')}\n")
            fh.write("-" * 60 + "\n\n")
            fh.write(body)
        logger.info(f"Draft saved → {filepath}")
    except OSError as exc:
        logger.error(f"Could not save draft to {filepath}: {exc}")

    return filepath


def send_email(to_email: str, subject: str, body: str) -> bool:
    """Send via Gmail SMTP SSL. Returns True on success, False on failure."""
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        logger.error("Gmail credentials not configured — cannot send email.")
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = GMAIL_ADDRESS
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(msg)

        logger.info(f"✓ Email sent to {to_email}")
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error("Gmail authentication failed. Check GMAIL_ADDRESS and GMAIL_APP_PASSWORD.")
    except smtplib.SMTPRecipientsRefused as exc:
        logger.error(f"Recipient refused: {exc}")
    except smtplib.SMTPException as exc:
        logger.error(f"SMTP error: {exc}")
    except OSError as exc:
        logger.error(f"Network error sending email: {exc}")
    except Exception as exc:
        logger.error(f"Unexpected error in send_email: {exc}")

    return False
