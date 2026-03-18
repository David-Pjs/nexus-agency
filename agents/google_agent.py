# -*- coding: utf-8 -*-
"""
google_agent.py — ATLAS: Google Calendar + Gmail + Contacts integration.

Requires one-time OAuth setup:
  1. Create Google Cloud project at console.cloud.google.com
  2. Enable Calendar, Gmail, People APIs
  3. Create OAuth 2.0 credentials (Desktop app type)
  4. Download as agency/credentials/credentials.json
  5. Run `python google_agent.py --auth` once to authenticate

After that, token.json persists and no re-auth is needed.
"""

import os
import sys
import json
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CREDENTIALS_DIR, CREDENTIALS_JSON, TOKEN_JSON, GOOGLE_SCOPES

# Try to import Google libraries; graceful fallback if not installed
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request as GRequest
    import googleapiclient.discovery as gdiscovery
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False


def google_available() -> bool:
    return GOOGLE_AVAILABLE and os.path.exists(CREDENTIALS_JSON)


def get_credentials():
    """Load or refresh OAuth credentials. Triggers browser auth if needed."""
    if not GOOGLE_AVAILABLE:
        return None

    creds = None
    if os.path.exists(TOKEN_JSON):
        creds = Credentials.from_authorized_user_file(TOKEN_JSON, GOOGLE_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(GRequest())
        else:
            if not os.path.exists(CREDENTIALS_JSON):
                return None
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_JSON, GOOGLE_SCOPES)
            creds = flow.run_local_server(port=0)
        os.makedirs(CREDENTIALS_DIR, exist_ok=True)
        with open(TOKEN_JSON, "w") as f:
            f.write(creds.to_json())

    return creds


def run_auth():
    """One-time interactive auth flow. Call with --auth flag."""
    if not GOOGLE_AVAILABLE:
        print("Google libraries not installed. Run:")
        print("  pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
        return False
    if not os.path.exists(CREDENTIALS_JSON):
        print(f"credentials.json not found at: {CREDENTIALS_JSON}")
        print("Download it from Google Cloud Console → APIs & Services → Credentials")
        return False
    creds = get_credentials()
    if creds:
        print("✅ Google auth successful! Token saved to:", TOKEN_JSON)
        return True
    return False


# ── Calendar ──────────────────────────────────────────────────────────────────

def get_calendar_service():
    creds = get_credentials()
    if not creds:
        return None
    return gdiscovery.build("calendar", "v3", credentials=creds, cache_discovery=False)


def get_events_today() -> list:
    svc = get_calendar_service()
    if not svc:
        return []

    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    end = now.replace(hour=23, minute=59, second=59, microsecond=0).isoformat()

    try:
        result = svc.events().list(
            calendarId="primary",
            timeMin=start, timeMax=end,
            maxResults=20, singleEvents=True,
            orderBy="startTime"
        ).execute()
        return result.get("items", [])
    except Exception as e:
        print(f"[ATLAS] Calendar error: {e}")
        return []


def get_events_tomorrow() -> list:
    svc = get_calendar_service()
    if not svc:
        return []

    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    start = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    end = tomorrow.replace(hour=23, minute=59, second=59, microsecond=0).isoformat()

    try:
        result = svc.events().list(
            calendarId="primary",
            timeMin=start, timeMax=end,
            maxResults=20, singleEvents=True,
            orderBy="startTime"
        ).execute()
        return result.get("items", [])
    except Exception as e:
        print(f"[ATLAS] Calendar error: {e}")
        return []


def create_event(title: str, start_dt: str, end_dt: str = None,
                 description: str = "", attendees: list = None) -> dict | None:
    """
    Create a calendar event.
    start_dt / end_dt: ISO format strings with timezone e.g. '2026-03-18T10:00:00+01:00'
    """
    svc = get_calendar_service()
    if not svc:
        return None

    if not end_dt:
        # Default 1 hour duration
        from dateutil.parser import parse as dtparse
        try:
            dt = dtparse(start_dt)
            end_dt = (dt + timedelta(hours=1)).isoformat()
        except Exception:
            end_dt = start_dt

    body = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start_dt},
        "end": {"dateTime": end_dt},
    }
    if attendees:
        body["attendees"] = [{"email": a} for a in attendees]

    try:
        event = svc.events().insert(calendarId="primary", body=body).execute()
        return event
    except Exception as e:
        print(f"[ATLAS] Create event error: {e}")
        return None


def _format_event(event: dict) -> str:
    summary = event.get("summary", "No title")
    start = event.get("start", {})
    time_str = start.get("dateTime", start.get("date", ""))
    if "T" in time_str:
        try:
            dt = datetime.fromisoformat(time_str)
            time_str = dt.strftime("%I:%M %p")
        except Exception:
            pass
    location = event.get("location", "")
    loc_str = f" @ {location}" if location else ""
    return f"• {time_str} — *{summary}*{loc_str}"


def format_today_schedule() -> str:
    events = get_events_today()
    today = datetime.now().strftime("%A, %B %d")

    if not events:
        return f"📅 *ATLAS — {today}*\n\nNo events scheduled today. 🌅"

    lines = [f"📅 *ATLAS — {today}*\n"]
    for e in events:
        lines.append(_format_event(e))
    return "\n".join(lines)


def format_tomorrow_schedule() -> str:
    events = get_events_tomorrow()
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%A, %B %d")

    if not events:
        return f"📅 *ATLAS — {tomorrow}*\n\nNo events scheduled tomorrow."

    lines = [f"📅 *ATLAS — {tomorrow}*\n"]
    for e in events:
        lines.append(_format_event(e))
    return "\n".join(lines)


def format_morning_briefing() -> str:
    return format_today_schedule()


# ── Gmail ─────────────────────────────────────────────────────────────────────

def get_gmail_service():
    creds = get_credentials()
    if not creds:
        return None
    return gdiscovery.build("gmail", "v1", credentials=creds, cache_discovery=False)


def get_unread_emails(max_results: int = 10) -> list:
    svc = get_gmail_service()
    if not svc:
        return []

    try:
        result = svc.users().messages().list(
            userId="me",
            q="is:unread in:inbox",
            maxResults=max_results
        ).execute()
        message_ids = result.get("messages", [])
        emails = []
        for m in message_ids:
            msg = svc.users().messages().get(
                userId="me", id=m["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"]
            ).execute()
            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            emails.append({
                "id": m["id"],
                "from": headers.get("From", "Unknown"),
                "subject": headers.get("Subject", "(no subject)"),
                "date": headers.get("Date", ""),
                "snippet": msg.get("snippet", ""),
            })
        return emails
    except Exception as e:
        print(f"[ATLAS] Gmail error: {e}")
        return []


def send_email(to: str, subject: str, body: str) -> bool:
    """Send an email via Gmail API."""
    import base64
    from email.mime.text import MIMEText

    svc = get_gmail_service()
    if not svc:
        return False

    msg = MIMEText(body)
    msg["to"] = to
    msg["subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    try:
        svc.users().messages().send(userId="me", body={"raw": raw}).execute()
        return True
    except Exception as e:
        print(f"[ATLAS] Send email error: {e}")
        return False


def format_inbox() -> str:
    emails = get_unread_emails(10)
    if not emails:
        return "📧 *ATLAS — Gmail*\n\nNo unread emails. Inbox zero! 🎉"

    lines = [f"📧 *ATLAS — Unread Emails ({len(emails)})*\n"]
    for i, e in enumerate(emails, 1):
        sender = e["from"].split("<")[0].strip()[:30]
        subject = e["subject"][:50]
        lines.append(f"{i}. *{subject}*\n   From: {sender}\n   {e['snippet'][:80]}...\n")
    return "\n".join(lines)


# ── Contacts ─────────────────────────────────────────────────────────────────

def get_contacts_service():
    creds = get_credentials()
    if not creds:
        return None
    return gdiscovery.build("people", "v1", credentials=creds, cache_discovery=False)


def load_contacts(max_results: int = 200) -> list:
    svc = get_contacts_service()
    if not svc:
        return []

    try:
        result = svc.people().connections().list(
            resourceName="people/me",
            pageSize=max_results,
            personFields="names,emailAddresses,phoneNumbers"
        ).execute()

        contacts = []
        for person in result.get("connections", []):
            names = person.get("names", [])
            emails = person.get("emailAddresses", [])
            name = names[0].get("displayName", "") if names else ""
            email = emails[0].get("value", "") if emails else ""
            if name or email:
                contacts.append({"name": name, "email": email})
        return contacts
    except Exception as e:
        print(f"[ATLAS] Contacts error: {e}")
        return []


def find_contact(query: str, contacts: list) -> dict | None:
    """Find a contact by name or email (fuzzy)."""
    query_lower = query.lower()
    for c in contacts:
        if query_lower in c["name"].lower() or query_lower in c["email"].lower():
            return c
    return None


# ── CLI auth helper ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--auth" in sys.argv:
        success = run_auth()
        sys.exit(0 if success else 1)
    else:
        print("Usage: python google_agent.py --auth")
        print("This runs the OAuth flow to authenticate with Google.")
