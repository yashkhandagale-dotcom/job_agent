# Automated Job Application Agent

A Python CLI tool that scrapes software-engineer job listings from **Wellfound** and **YC Work at a Startup**, scores each against your profile using **Claude AI**, and automatically sends personalised cold emails — or saves drafts when no email is available.

---

## Features

- Scrapes two job boards concurrently (async)
- AI-powered match scoring (0–100%) via Claude
- Generates bespoke cold emails per job
- Sends via Gmail SMTP or saves as drafts
- Deduplication — never applies to the same job twice
- Full logging to console + `agent.log`
- Schedulable via cron or `watch` mode

---

## Prerequisites

- **Python 3.10+**
- A **Gmail account** with an App Password (see below)
- An **Anthropic API key**

---

## Installation

```bash
# 1. Clone or download this folder
cd job_agent

# 2. (Recommended) Create a virtual environment
python3 -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Getting Your Anthropic API Key

1. Go to [console.anthropic.com](https://console.anthropic.com/account/keys)
2. Sign up or log in
3. Click **Create Key** and copy it
4. Paste it into your `.env` file as `ANTHROPIC_API_KEY=sk-ant-...`

> **Cost note:** Each run uses ~40 Claude API calls at most (20 matches + 20 emails). Typical cost is well under $0.10 per run at Sonnet pricing.

---

## Setting Up Gmail App Password

Your regular Gmail password will **not** work. You need a dedicated App Password:

1. Visit [myaccount.google.com](https://myaccount.google.com) → **Security**
2. Scroll to **2-Step Verification** and enable it (required)
3. Back on Security page, search for **App passwords**
4. Click **Create** → choose **Mail** + **Other (custom name)** → name it `job-agent`
5. Google shows a 16-character code — **copy it immediately** (shown once)
6. Paste it into your `.env` as `GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx` (spaces are fine)

---

## Configuration

```bash
cp .env.example .env
```

Open `.env` and fill in at minimum:

```dotenv
ANTHROPIC_API_KEY=sk-ant-...          # Required — AI scoring + email writing
GMAIL_ADDRESS=you@gmail.com           # Required to send emails
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx # Required to send emails

MATCH_THRESHOLD=40      # Only apply to jobs scoring >= 40%
MAX_JOBS_PER_RUN=20     # Cap total jobs scraped per run
```

Edit `CANDIDATE_NAME`, `CANDIDATE_EMAIL`, `CANDIDATE_SKILLS`, etc. to match your own profile, or edit `config.py` directly for full control.

---

## Running the Agent

### Run once

```bash
python main.py run
```

The agent will:
1. Scrape Wellfound + YC
2. Score every new job with Claude
3. For matches ≥ 40%: generate and send (or draft) personalised emails
4. Log everything and save state to `jobs_applied.json`

### Watch mode (runs every day at 09:00)

```bash
python main.py watch
```

Runs immediately, then wakes at 09:00 each day. Press `Ctrl+C` to stop.

---

## Setting Up as a Daily Cron Job (Mac / Linux)

```bash
crontab -e
```

Add this line (adjust the path):

```
0 9 * * * cd /path/to/job_agent && /path/to/venv/bin/python main.py run >> cron.log 2>&1
```

To find your Python path: `which python` (inside the venv).

---

## Output Files

| File | Purpose |
|------|---------|
| `jobs_applied.json` | Tracks all applied jobs + run history |
| `agent.log` | Full debug log of every run |
| `drafts/` | Unsent emails (when no `email` field found) |
| `cron.log` | Cron output (if using cron) |

---

## Troubleshooting

**`ANTHROPIC_API_KEY is not set`**
→ Make sure `.env` exists in the same directory as `main.py` and the key is filled in.

**Gmail authentication failed**
→ Double-check that 2-Step Verification is ON and you're using an App Password (not your login password). Remove spaces from the App Password if present.

**No jobs found**
→ The job board HTML may have changed. Check `agent.log` for scraper warnings. The scraper will still run; it just returns an empty list with a log message. Open an issue or update the CSS selectors in `scraper.py`.

**Match scores are all 0%**
→ Claude may be returning an unexpected response format. Check `agent.log` for JSON parse errors and inspect the raw response in the DEBUG lines.

**Drafts folder fills up but no emails are sent**
→ No email addresses were found on the scraped listings. This is common — most job boards don't show recruiter emails. Review drafts and send manually, or add email addresses to the job dicts before the emailer step.

**Rate limit errors from Anthropic**
→ Reduce `MAX_JOBS_PER_RUN` in `.env`, or increase the `time.sleep()` values in `matcher.py` and `emailer.py`.

---

## Customising for a Different Candidate

Edit `config.py` (the `CANDIDATE_PROFILE` dict) or override via `.env`:

```dotenv
CANDIDATE_NAME=Jane Smith
CANDIDATE_EXPERIENCE_YEARS=3
CANDIDATE_EMAIL=jane@example.com
CANDIDATE_SKILLS=Python,FastAPI,PostgreSQL,AWS,Terraform
CANDIDATE_PORTFOLIO=janesmith.dev
```

---

## Architecture

```
main.py          CLI + orchestration loop
scraper.py       Async httpx + BeautifulSoup scraping
matcher.py       Claude AI job scoring (JSON output)
emailer.py       Claude AI email writing + Gmail SMTP
storage.py       JSON-backed deduplication + run logs
config.py        Centralised config from .env
```
