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
