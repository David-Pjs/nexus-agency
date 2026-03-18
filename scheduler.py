# -*- coding: utf-8 -*-
"""
scheduler.py — Background job runner for NEXUS agency.

Pure Python threading — no external dependencies.
All background threads write results to SQLite and push to Telegram
via the shared send_message() function injected at startup.
"""

import threading
import time
from datetime import datetime

_send_fn = None  # Injected by nexus_bot.py
_owner_chat_id = 0

def init(send_message_fn, owner_chat_id: int):
    """Call this from nexus_bot.py before starting threads."""
    global _send_fn, _owner_chat_id
    _send_fn = send_message_fn
    _owner_chat_id = owner_chat_id


def _push(text: str):
    if _send_fn and _owner_chat_id:
        try:
            _send_fn(_owner_chat_id, text)
        except Exception as e:
            print(f"[Scheduler] push error: {e}")


def _wait_until_hour(target_hour: int):
    """Block until the next occurrence of target_hour:00."""
    now = datetime.now()
    target = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
    if target <= now:
        # Already past; schedule for tomorrow
        from datetime import timedelta
        target = target + timedelta(days=1)
    delta = (target - now).total_seconds()
    print(f"[Scheduler] Next {target_hour:02d}:00 in {delta/3600:.1f}h")
    time.sleep(delta)


# ── BOUNTY thread ─────────────────────────────────────────────────────────────

def _bounty_loop():
    from config import BOUNTY_SCAN_HOUR
    from agents.bounty_agent import run_scan, format_digest

    print("[Scheduler] BOUNTY thread started")
    while True:
        try:
            _wait_until_hour(BOUNTY_SCAN_HOUR)
            print("[Scheduler] Running BOUNTY daily scan...")
            run_scan()
            digest = format_digest(limit=5)
            _push(digest)
        except Exception as e:
            print(f"[Scheduler] BOUNTY error: {e}")
            time.sleep(300)  # 5 min backoff


# ── ALPHA thread ──────────────────────────────────────────────────────────────

def _alpha_loop():
    from config import ALPHA_INTERVAL_HOURS
    from agents.alpha_agent import check_alerts, format_alert_trigger

    print("[Scheduler] ALPHA thread started")
    interval = ALPHA_INTERVAL_HOURS * 3600

    while True:
        try:
            triggered = check_alerts()
            for t in triggered:
                msg = format_alert_trigger(t["alert"], t["price"])
                _push(msg)
        except Exception as e:
            print(f"[Scheduler] ALPHA error: {e}")

        time.sleep(interval)


# ── ATLAS morning briefing thread ─────────────────────────────────────────────

def _atlas_loop():
    from config import ATLAS_BRIEFING_HOUR

    print("[Scheduler] ATLAS briefing thread started")
    while True:
        try:
            _wait_until_hour(ATLAS_BRIEFING_HOUR)
            print("[Scheduler] Running ATLAS morning briefing...")
            try:
                from agents.google_agent import format_morning_briefing, google_available
                if google_available():
                    msg = format_morning_briefing()
                    _push(msg)
                else:
                    print("[Scheduler] ATLAS: Google not configured, skipping briefing")
            except Exception as e:
                print(f"[Scheduler] ATLAS briefing error: {e}")
        except Exception as e:
            print(f"[Scheduler] ATLAS loop error: {e}")
            time.sleep(300)


# ── Gmail monitor thread ──────────────────────────────────────────────────────

def _gmail_loop():
    from config import GMAIL_INTERVAL_MINS

    print("[Scheduler] Gmail monitor thread started")
    interval = GMAIL_INTERVAL_MINS * 60
    last_seen_ids = set()

    while True:
        try:
            from agents.google_agent import get_unread_emails, google_available
            if google_available():
                emails = get_unread_emails(max_results=5)
                new_ids = {e["id"] for e in emails}
                new_emails = [e for e in emails if e["id"] not in last_seen_ids]

                if new_emails and last_seen_ids:  # Don't alert on first run
                    count = len(new_emails)
                    subjects = "\n".join(f"• {e['subject'][:50]}" for e in new_emails[:3])
                    msg = f"📧 *{count} new email{'s' if count > 1 else ''}*\n\n{subjects}"
                    if count > 3:
                        msg += f"\n...and {count - 3} more"
                    msg += "\n\nUse `/gmail read` to view details."
                    _push(msg)

                last_seen_ids = new_ids
        except Exception as e:
            print(f"[Scheduler] Gmail monitor error: {e}")

        time.sleep(interval)


# ── Start all threads ─────────────────────────────────────────────────────────

def start_all():
    threads = [
        threading.Thread(target=_bounty_loop, name="bounty_scanner", daemon=True),
        threading.Thread(target=_alpha_loop,  name="alpha_monitor",  daemon=True),
        threading.Thread(target=_atlas_loop,  name="atlas_briefing", daemon=True),
        threading.Thread(target=_gmail_loop,  name="gmail_monitor",  daemon=True),
    ]
    for t in threads:
        t.start()
        print(f"[Scheduler] Started: {t.name}")
    return threads
