"""
config.py — Load all configuration from environment variables via .env file.
All other modules import from here; never read os.environ directly elsewhere.
"""

import os
import logging
from dotenv import load_dotenv

# Load .env file from the same directory as this script
load_dotenv()

# ── Anthropic ──────────────────────────────────────────────────────────────
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
# ── Gmail SMTP ─────────────────────────────────────────────────────────────
GMAIL_ADDRESS: str = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD: str = os.getenv("GMAIL_APP_PASSWORD", "")

# ── Agent behaviour ────────────────────────────────────────────────────────
MATCH_THRESHOLD: int = int(os.getenv("MATCH_THRESHOLD", "40"))
MAX_JOBS_PER_RUN: int = int(os.getenv("MAX_JOBS_PER_RUN", "20"))

# ── Target job titles ──────────────────────────────────────────────────────
# Jobs whose title does NOT match at least one of these keywords (case-insensitive)
# will be filtered out before being sent to the LLM matcher, saving API calls.
# Add or remove titles freely; partial matches work (e.g. "react" matches "React Developer").
TARGET_JOB_TITLES: list[str] = [
    # Generic software roles
    "software engineer",
    "software developer",
    "software development engineer",
    "sde",
    "swe",
    "junior developer",
    "junior engineer",
    "associate engineer",
    "associate developer",
    "graduate engineer",
    "entry level engineer",
    # Levelled variants
    "sde 1",
    "sde i",
    "sde-1",
    "engineer 1",
    "engineer i",
    "l3",
    "l4",
    # .NET / C# specific
    ".net developer",
    ".net engineer",
    "dotnet developer",
    "dotnet engineer",
    "asp.net",
    "c# developer",
    "c# engineer",
    # Full-stack
    "full stack",
    "fullstack",
    "full-stack",
    # Backend
    "backend developer",
    "backend engineer",
    "back end developer",
    "back-end developer",
    "back-end engineer",
    "api developer",
    "api engineer",
    "node.js developer",
    "nodejs developer",
    "python developer",
    "python engineer",
    "django developer",
    "flask developer",
    # Frontend
    "frontend developer",
    "frontend engineer",
    "front end developer",
    "front-end developer",
    "front-end engineer",
    "react developer",
    "react engineer",
    "ui developer",
    "ui engineer",
    "typescript developer",
    # DevOps / cloud adjacent
    "devops engineer",
    "cloud engineer",
    "platform engineer",
    "site reliability engineer",
    "sre",
    # Microservices / distributed systems
    "microservices",
    "distributed systems",
    # IoT / embedded (for ESP32 / firmware work)
    "embedded engineer",
    "iot engineer",
    "firmware engineer",
    # AI / ML adjacent
    "ai engineer",
    "ml engineer",
    "machine learning engineer",
    # Generic catch-alls that often appear in entry-level listings
    "software",        # e.g. "Software Intern", "Software Trainee"
    "developer",
    "engineer",
]

# ── Storage / logging ──────────────────────────────────────────────────────
STORAGE_FILE: str = os.getenv("STORAGE_FILE", "jobs_applied.json")
LOG_FILE: str = os.getenv("LOG_FILE", "agent.log")
DRAFTS_DIR: str = "drafts"

# ── Candidate profile ──────────────────────────────────────────────────────
# Override individual fields via .env (CANDIDATE_NAME, CANDIDATE_EMAIL, etc.)
# or edit this dict directly for a quick start.
CANDIDATE_PROFILE: dict = {
    "name": os.getenv("CANDIDATE_NAME", "Yash Khandagale"),
    "location": os.getenv("CANDIDATE_LOCATION", "Mumbai, India"),
    "experience_years": int(os.getenv("CANDIDATE_EXPERIENCE_YEARS", "1")),

    # Current role
    "current_role": "Software Engineer at Wonderbiz Technologies",

    # All skills drawn directly from resume
    "skills": [
        s.strip()
        for s in os.getenv(
            "CANDIDATE_SKILLS",
            # Languages
            "C#,.NET Core,TypeScript,JavaScript,Python,C++,Java,SQL,"
            # Backend
            "ASP.NET Core,REST APIs,Clean Architecture,EF Core,ADO.NET,Node.js,Django,Flask,"
            # Frontend
            "React,Tailwind CSS,shadcn/ui,Recharts,Axios,Vite,"
            # Databases
            "SQL Server,InfluxDB,Qdrant,MongoDB,MySQL,"
            # Messaging & Protocols
            "RabbitMQ,Modbus TCP,Modbus RTU,OPC-UA,SignalR,WebSockets,"
            # DevOps
            "Docker,Docker Compose,Kubernetes,GitHub Actions,CI/CD,Helm,NGINX,"
            # Observability
            "OpenTelemetry,Jaeger,Swagger,k6,Postman,"
            # Embedded / IoT
            "ESP32,Raspberry Pi,PlatformIO,OTA Firmware,"
            # AI / ML
            "LLaMA,Gemini,XGBoost,Scikit-learn,NLP,PyPDF2,"
            # Concepts
            "Microservices,Event-Driven Architecture,SOLID,JWT,RBAC,Polly,Distributed Systems",
        ).split(",")
        if s.strip()
    ],

    # Key projects for email personalisation hooks
    "notable_projects": [
        "AI Resume Screening & Job Matching (MERN + Flask + NLP)",
        "CodeReview AI — React SPA on Cloudflare Workers",
        "Kubernetes CI/CD Deployment Pipeline (Helm + GitHub Actions)",
        "Credit Risk ML model — 86% ROC-AUC with XGBoost",
        "ESP32 Edge Gateway firmware with Modbus TCP/OPC-UA + OTA updates",
    ],

    "education": "B.E. Computer Engineering, Watumull Institute, Mumbai (CGPA 7.92)",
    "certifications": "Google Data Analytics Professional Certification (Coursera, Dec 2024)",

    "portfolio": os.getenv("CANDIDATE_PORTFOLIO", "yashkhandagale.in"),
    "github":    os.getenv("CANDIDATE_GITHUB",    "github.com/yashkhandagale"),
    "linkedin":  os.getenv("CANDIDATE_LINKEDIN",  "linkedin.com/in/yashkhandagale"),
    "email":     os.getenv("CANDIDATE_EMAIL",     "yashkhandagale9619@gmail.com"),
    "phone":     os.getenv("CANDIDATE_PHONE",     "+91-9619036483"),
}

# ── Logging setup ──────────────────────────────────────────────────────────
def setup_logging() -> logging.Logger:
    """Configure root logger to write to both console and LOG_FILE."""
    logger = logging.getLogger("job_agent")
    if logger.handlers:
        # Already configured (e.g. called twice in watch mode)
        return logger

    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        fmt="[%(asctime)s] %(levelname)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # File handler
    try:
        fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError as exc:
        logger.warning(f"Could not open log file {LOG_FILE}: {exc}")

    return logger


def validate_config(logger: logging.Logger) -> bool:
    """Warn about missing critical config values. Returns False if fatal."""
    ok = True
    if not GROQ_API_KEY:
        logger.error("GROQ_API_KEY is not set — AI features will fail.")
        ok = False
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        logger.warning(
            "GMAIL_ADDRESS or GMAIL_APP_PASSWORD not set — emails will not be sent."
        )
    return ok