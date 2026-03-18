# -*- coding: utf-8 -*-
"""
config.py — Central config loader for NEXUS agency.
Reads from .env file in the same directory.
"""

import os

# ── Load .env ─────────────────────────────────────────────────────────────────
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

def _load_env():
    if not os.path.exists(_env_path):
        return
    with open(_env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and val and key not in os.environ and not val.startswith("your_"):
                os.environ[key] = val

_load_env()

# ── Telegram ──────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8253905687:AAF7sGc-HEBvVCkV8YIoByG-NuMgIWVF-vE")
_raw_owner = os.environ.get("YOUR_TELEGRAM_USER_ID", "0")
OWNER_CHAT_ID = int(_raw_owner) if _raw_owner.isdigit() else 0
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ── Claude CLI ────────────────────────────────────────────────────────────────
CLAUDE_TIMEOUT = 120  # seconds

# ── Scheduling ────────────────────────────────────────────────────────────────
BOUNTY_SCAN_HOUR = 9    # 9:00 AM daily
ATLAS_BRIEFING_HOUR = 8  # 8:00 AM daily
ALPHA_INTERVAL_HOURS = 2
GMAIL_INTERVAL_MINS = 30

# ── Google ────────────────────────────────────────────────────────────────────
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/contacts.readonly",
]
CREDENTIALS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials")
CREDENTIALS_JSON = os.path.join(CREDENTIALS_DIR, "credentials.json")
TOKEN_JSON = os.path.join(CREDENTIALS_DIR, "token.json")

# ── Agents dir ────────────────────────────────────────────────────────────────
AGENTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agents")

# ── Fit score keywords (BOUNTY) ───────────────────────────────────────────────
FIT_KEYWORDS_HIGH = ["web3", "ai", "artificial intelligence", "fintech", "blockchain",
                     "nigeria", "africa", "defi", "solidity", "python", "crypto"]
FIT_KEYWORDS_MEDIUM = ["mobile", "app", "developer", "open source", "hackathon",
                       "grant", "startup", "innovation"]

def score_opportunity(title: str, description: str = "") -> int:
    text = (title + " " + description).lower()
    score = 5
    for kw in FIT_KEYWORDS_HIGH:
        if kw in text:
            score = min(10, score + 1)
    for kw in FIT_KEYWORDS_MEDIUM:
        if kw in text:
            score = min(10, score + 0.5)
    return max(1, int(score))
