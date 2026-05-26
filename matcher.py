"""
matcher.py — Uses Groq (LLaMA 3.3 70B) to score each job against the candidate profile.

Free tier: 14,400 requests/day — get key at https://console.groq.com
"""

import json
import logging
import time

from groq import Groq

from config import GROQ_API_KEY, CANDIDATE_PROFILE, MATCH_THRESHOLD

logger = logging.getLogger("job_agent")

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


_DEFAULT_ANALYSIS: dict = {
    "match_percent": 0,
    "matched_skills": [],
    "missing_skills": [],
    "reasoning": "Analysis unavailable",
    "company_hook": "",
}


def _build_match_prompt(job: dict) -> str:
    p = CANDIDATE_PROFILE
    skills_str = ", ".join(p["skills"])
    projects_str = "; ".join(p.get("notable_projects", []))
    return (
        f"Analyze if this job matches the candidate profile.\n\n"
        f"CANDIDATE: {p['name']}, {p['experience_years']}+ year(s) production experience\n"
        f"CURRENT ROLE: {p.get('current_role', '')}\n"
        f"SKILLS: {skills_str}\n"
        f"NOTABLE PROJECTS: {projects_str}\n\n"
        f"JOB TITLE: {job.get('title', 'N/A')}\n"
        f"COMPANY: {job.get('company', 'N/A')}\n"
        f"DESCRIPTION: {job.get('description', 'No description provided.')}\n\n"
        f"Return ONLY valid JSON, no markdown, no explanation:\n"
        f'{{\n'
        f'  "match_percent": <integer 0-100>,\n'
        f'  "matched_skills": [<list of matching skills, max 6>],\n'
        f'  "missing_skills": [<list of required skills candidate lacks, max 4>],\n'
        f'  "reasoning": "<one sentence explanation>",\n'
        f'  "company_hook": "<one specific sentence about this company that shows genuine interest, for use in email>"\n'
        f'}}'
    )


def _parse_json_response(raw: str, context: str = "") -> dict:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        text = inner.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error(f"JSON parse error{' (' + context + ')' if context else ''}: {exc}")
        logger.debug(f"Raw response was: {raw[:300]}")
        return dict(_DEFAULT_ANALYSIS)


def match_job(job: dict) -> dict:
    """Score a single job using Groq. Never raises; returns _DEFAULT_ANALYSIS on failure."""
    try:
        client = _get_client()
        prompt = _build_match_prompt(job)

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.choices[0].message.content or ""
        analysis = _parse_json_response(raw, context=f"{job.get('title')} @ {job.get('company')}")

        analysis.setdefault("match_percent", 0)
        analysis.setdefault("matched_skills", [])
        analysis.setdefault("missing_skills", [])
        analysis.setdefault("reasoning", "")
        analysis.setdefault("company_hook", "")
        analysis["match_percent"] = max(0, min(100, int(analysis["match_percent"])))

        time.sleep(0.5)
        return analysis

    except Exception as exc:
        logger.error(f"Groq error in match_job ({job.get('title')}): {exc}")

    return dict(_DEFAULT_ANALYSIS)


def is_match(job_analysis: dict, threshold: int = MATCH_THRESHOLD) -> bool:
    return int(job_analysis.get("match_percent", 0)) >= threshold
