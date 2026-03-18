# -*- coding: utf-8 -*-
"""
NEXUS Bot — Upgraded AI Agency Telegram bridge.

Features:
  - SQLite conversation persistence (survives restarts)
  - UTF-8 safe subprocess calls
  - PID file to prevent duplicate instances
  - Per-agent system prompts via slash commands
  - BOUNTY scanner + ALPHA crypto monitor
  - Google Calendar / Gmail / Contacts (optional)
  - Background scheduler (daily digest, price alerts, morning briefing)

Usage:
  python nexus_bot.py

Setup:
  1. Set TELEGRAM_BOT_TOKEN and YOUR_TELEGRAM_USER_ID in agency/.env
  2. Optionally run:  python agents/google_agent.py --auth
  3. pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
"""

import subprocess
import json
import urllib.request
import urllib.parse
import urllib.error
import time
import sys
import os
import re

# ── Fix Windows terminal encoding ─────────────────────────────────────────────
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Ensure agency dir is importable ───────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# ── Local imports ─────────────────────────────────────────────────────────────
from config import BOT_TOKEN, API_BASE, OWNER_CHAT_ID, CLAUDE_TIMEOUT, AGENTS_DIR
from db import save_message, get_history, clear_history, save_alert, get_user_alerts

# ── PID guard — prevent multiple instances ────────────────────────────────────
PID_FILE = os.path.join(_HERE, "nexus.pid")

def _acquire_pid():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                old_pid = int(f.read().strip())
            # Check if that process is still running
            import psutil
            if psutil.pid_exists(old_pid):
                print(f"[NEXUS] Another instance running (PID {old_pid}). Exiting.")
                sys.exit(1)
        except (ImportError, ValueError, OSError):
            pass  # psutil not available or stale PID; proceed
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

def _release_pid():
    try:
        os.remove(PID_FILE)
    except OSError:
        pass

# ── Agent system prompts ──────────────────────────────────────────────────────

def _load_agent_prompt(agent_name: str) -> str:
    """Load AGENT.md for the given agent. Falls back to a generic prompt."""
    path = os.path.join(AGENTS_DIR, agent_name.lower(), "AGENT.md")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return f"You are {agent_name.upper()}, a specialist AI agent. Be concise and expert."


# Pre-load all agent prompts once at startup
AGENT_PROMPTS = {}
for _agent in ["nexus", "scout", "architect", "herald", "bounty", "atlas", "alpha", "forge"]:
    AGENT_PROMPTS[_agent] = _load_agent_prompt(_agent)

# ── Telegram helpers ──────────────────────────────────────────────────────────

def tg_get(method: str, params: dict = None) -> dict | None:
    url = f"{API_BASE}/{method}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as e:
        print(f"[TG GET error] {e}")
        return None


def tg_post(method: str, data: dict) -> dict | None:
    url = f"{API_BASE}/{method}"
    payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=payload,
                                  headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as e:
        print(f"[TG POST error] {e}")
        return None


def send_message(chat_id: int, text: str):
    if not text:
        text = "(no response)"
    text = str(text)
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        result = tg_post("sendMessage", {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        })
        if not result or not result.get("ok"):
            # Fallback to plain text if Markdown parse fails
            tg_post("sendMessage", {"chat_id": chat_id, "text": chunk})


def send_typing(chat_id: int):
    tg_post("sendChatAction", {"chat_id": chat_id, "action": "typing"})


# ── Claude CLI ────────────────────────────────────────────────────────────────

def ask_claude(user_message: str, system_prompt: str, chat_id: int = None) -> str:
    """Call claude CLI with a system prompt. UTF-8 safe."""
    agent_label = "NEXUS" if system_prompt == AGENT_PROMPTS.get("nexus") else "Agent"
    print(f"[{agent_label}] {user_message[:80]}...")

    cmd = [
        "claude",
        "--system-prompt", system_prompt,
        "--output-format", "text",
        "-p", user_message,
        "--permission-mode", "dontAsk",
        "--dangerously-skip-permissions",
    ]

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=CLAUDE_TIMEOUT,
            env=env,
            cwd=_HERE,
        )
        stdout = result.stdout.decode("utf-8", errors="replace")
        stderr = result.stderr.decode("utf-8", errors="replace")

        if result.returncode == 0:
            response = stdout.strip()
            return response if response else "🧠 Processed but got an empty response. Try rephrasing."
        else:
            err = stderr.strip()
            print(f"[Claude error rc={result.returncode}] {err[:200]}")
            return f"⚠️ Error: {err[:200] if err else 'unknown error'}"

    except subprocess.TimeoutExpired:
        return f"⏱️ Timed out after {CLAUDE_TIMEOUT}s. Try a shorter query."
    except FileNotFoundError:
        return "❌ `claude` CLI not found. Make sure Claude Code is installed and in your PATH."
    except Exception as e:
        return f"❌ Unexpected error: {e}"


def ask_claude_with_history(chat_id: int, new_message: str,
                             agent: str = "nexus") -> str:
    """Build context from SQLite history + ask Claude."""
    history = get_history(chat_id, limit=12)
    system_prompt = AGENT_PROMPTS.get(agent, AGENT_PROMPTS["nexus"])

    if history:
        context_lines = ["[Conversation so far:]"]
        for h in history:
            prefix = "User" if h["role"] == "user" else agent.upper()
            context_lines.append(f"{prefix}: {h['content'][:400]}")
        context_lines.append(f"\n[New message:]\n{new_message}")
        prompt = "\n".join(context_lines)
    else:
        prompt = new_message

    response = ask_claude(prompt, system_prompt, chat_id)

    # Persist to DB
    save_message(chat_id, "user", new_message)
    save_message(chat_id, "assistant", response)

    return response


# ── Command handlers ──────────────────────────────────────────────────────────

def cmd_start(chat_id: int):
    send_message(chat_id,
        "🧠 *NEXUS  |  Agency Online*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "_Your AI agency. Running 24/7 on your machine._\n\n"
        "*🤖 Agents*\n"
        "`/scout`  [topic] — deep research\n"
        "`/architect`  [task] — business strategy\n"
        "`/herald`  [task] — marketing & content\n"
        "`/bounty` — live hackathon scanner\n"
        "`/alpha` — crypto & DeFi intel\n"
        "`/atlas today` — your calendar\n"
        "`/forge`  [task] — code & builds\n\n"
        "*⚡ Skills*\n"
        "`/news`  [topic] — latest headlines\n"
        "`/weather`  [city] — forecast\n"
        "`/remind`  30m  [message] — reminder\n"
        "`/status` — system health\n\n"
        "*🛠 Utility*\n"
        "`/alerts` — active price alerts\n"
        "`/clear` — reset context\n"
        "`/agents` — full agent list\n\n"
        "_Or just talk — NEXUS routes everything._"
    )


def cmd_agents(chat_id: int):
    send_message(chat_id,
        "🧠 *NEXUS  |  Agent Roster*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔭 *SCOUT* — Research, web intel, competitive analysis\n"
        "📐 *ARCHITECT* — Business plans, strategy, frameworks\n"
        "📣 *HERALD* — Marketing, content, brand messaging\n"
        "🏹 *BOUNTY* — Hackathons, grants, opportunities\n"
        "   └ auto-scan daily @ 09:00\n"
        "📅 *ATLAS* — Calendar, scheduling, Gmail\n"
        "   └ morning briefing @ 08:00\n"
        "⚡ *ALPHA* — Crypto, DeFi, price alerts\n"
        "   └ checks alerts every 2h\n"
        "🔨 *FORGE* — Code, builds, automation\n\n"
        "*Extra Skills:*\n"
        "📰 `/news` — live headlines\n"
        "🌤 `/weather` — weather forecast\n"
        "⏰ `/remind` — set reminders\n"
        "📊 `/status` — bot health\n\n"
        "_All agents powered by Claude Code locally._"
    )


def cmd_clear(chat_id: int):
    clear_history(chat_id)
    send_message(chat_id, "🧹 Conversation cleared. Fresh start!")


def cmd_bounty(chat_id: int, args: str):
    send_typing(chat_id)
    if args.strip().lower() == "live":
        from agents.bounty_agent import get_live_report
        send_message(chat_id, get_live_report(10))
    else:
        send_message(chat_id, "🏹 Scanning opportunities... (this takes ~20 seconds)")
        send_typing(chat_id)
        from agents.bounty_agent import run_scan, format_digest
        run_scan()
        send_message(chat_id, format_digest(10))


def cmd_alpha(chat_id: int, args: str):
    send_typing(chat_id)
    parts = args.strip().split()

    if not parts or parts[0] == "":
        from agents.alpha_agent import format_snapshot
        send_message(chat_id, format_snapshot())

    elif parts[0].lower() == "yields":
        from agents.alpha_agent import format_yields
        send_message(chat_id, format_yields())

    elif parts[0].lower() == "fear":
        from agents.alpha_agent import format_fear_greed
        send_message(chat_id, format_fear_greed())

    elif parts[0].lower() == "alert" and len(parts) >= 4:
        # /alpha alert BTC 100000 above
        symbol = parts[1].upper()
        try:
            target = float(parts[2].replace(",", ""))
        except ValueError:
            send_message(chat_id, "⚠️ Invalid price. Usage: `/alpha alert BTC 100000 above`")
            return
        direction = parts[3].lower()
        if direction not in ("above", "below"):
            send_message(chat_id, "⚠️ Direction must be `above` or `below`.")
            return
        alert_id = save_alert(chat_id, symbol, target, direction)
        send_message(chat_id,
            f"⚡ Alert set! I'll ping you when *{symbol}* goes {direction} ${target:,.2f}\n"
            f"Alert ID: {alert_id} | Use `/alerts` to see all active alerts."
        )

    elif parts[0].upper() in ("BTC", "ETH", "SOL", "BNB", "MATIC", "ARB", "OP",
                               "AVAX", "LINK", "UNI", "AAVE", "DOGE", "XRP"):
        from agents.alpha_agent import get_coin_detail
        detail = get_coin_detail(parts[0])
        if detail:
            chg_em = "🟢" if detail["change_24h"] >= 0 else "🔴"
            mc_b = detail["market_cap"] / 1e9
            send_message(chat_id,
                f"⚡ *{detail['name']} ({detail['symbol']})*\n\n"
                f"Price: *${detail['price']:,.2f}*\n"
                f"{chg_em} 24h: {detail['change_24h']:+.2f}% | 7d: {detail['change_7d']:+.2f}%\n"
                f"Market Cap: ${mc_b:.2f}B | Rank: #{detail['rank']}\n"
                f"ATH: ${detail['ath']:,.2f} ({detail['ath_change']:+.1f}% from ATH)"
            )
        else:
            send_message(chat_id, f"⚠️ Could not fetch data for {parts[0]}.")
    else:
        # Route to ALPHA agent via Claude
        response = ask_claude_with_history(chat_id, f"/alpha {args}", agent="alpha")
        send_message(chat_id, response)


def cmd_atlas(chat_id: int, args: str):
    send_typing(chat_id)
    try:
        from agents.google_agent import (
            google_available, format_today_schedule, format_tomorrow_schedule,
            format_inbox, create_event
        )
    except ImportError:
        send_message(chat_id, "📅 Google integration not available. Install: `pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client`")
        return

    if not google_available():
        send_message(chat_id,
            "📅 *ATLAS — Google not connected*\n\n"
            "To connect Google Calendar/Gmail:\n"
            "1. Create credentials.json at `agency/credentials/credentials.json`\n"
            "2. Run: `python agents/google_agent.py --auth`\n"
            "3. Try `/atlas today` again"
        )
        return

    sub = args.strip().lower()
    if sub in ("today", ""):
        send_message(chat_id, format_today_schedule())
    elif sub == "tomorrow":
        send_message(chat_id, format_tomorrow_schedule())
    elif sub == "inbox" or sub.startswith("gmail"):
        send_message(chat_id, format_inbox())
    else:
        # Ask ATLAS agent via Claude with calendar context
        response = ask_claude_with_history(chat_id, f"/atlas {args}", agent="atlas")
        send_message(chat_id, response)


def cmd_gmail(chat_id: int, args: str):
    send_typing(chat_id)
    try:
        from agents.google_agent import google_available, format_inbox, send_email
    except ImportError:
        send_message(chat_id, "📧 Google integration not installed.")
        return

    if not google_available():
        send_message(chat_id, "📧 Google not connected. Run: `python agents/google_agent.py --auth`")
        return

    sub = args.strip().lower()
    if sub in ("", "read", "inbox"):
        send_message(chat_id, format_inbox())
    else:
        # Route to agent
        response = ask_claude_with_history(chat_id, f"/gmail {args}", agent="atlas")
        send_message(chat_id, response)


def cmd_alerts(chat_id: int):
    alerts = get_user_alerts(chat_id)
    if not alerts:
        send_message(chat_id,
            "⚡ *ALPHA  |  Price Alerts*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "No active alerts.\n\n"
            "_Set one: `/alpha alert BTC 95000 below`_"
        )
        return
    lines = [
        "⚡ *ALPHA  |  Active Alerts*",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]
    for a in alerts:
        arrow = "📈" if a["direction"] == "above" else "📉"
        lines.append(f"{arrow} *{a['symbol']}*  {a['direction']}  `${a['target']:,.2f}`  _#{a['id']}_")
    lines.append("\n_Checks every 2h · /alpha alert to add more_")
    send_message(chat_id, "\n".join(lines))


def cmd_news(chat_id: int, args: str):
    send_typing(chat_id)
    from agents.skills import get_news
    send_message(chat_id, get_news(args.strip()))


def cmd_weather(chat_id: int, args: str):
    send_typing(chat_id)
    from agents.skills import get_weather
    city = args.strip() or "Lagos"
    send_message(chat_id, get_weather(city))


def cmd_remind(chat_id: int, args: str):
    from agents.skills import set_reminder
    parts = args.strip().split(None, 1)
    if len(parts) < 2:
        send_message(chat_id,
            "⏰ *Remind* — Usage:\n\n"
            "`/remind 30m Check the oven`\n"
            "`/remind 2h Review proposal`\n"
            "`/remind 1h30m Call back David`"
        )
        return
    send_message(chat_id, set_reminder(chat_id, parts[0], parts[1]))


def cmd_status(chat_id: int):
    from agents.skills import get_status
    from db import get_top_opportunities, get_active_alerts as _ga
    alert_count = len(_ga())
    opp_count = len(get_top_opportunities(limit=9999))
    send_message(chat_id, get_status(alert_count, opp_count))


def cmd_agent_route(chat_id: int, agent: str, user_input: str, original_text: str):
    """Route a slash command to a named agent via Claude."""
    send_typing(chat_id)
    response = ask_claude_with_history(chat_id, original_text, agent=agent)
    send_message(chat_id, response)


# ── Message router ────────────────────────────────────────────────────────────

def handle_message(chat_id: int, text: str, username: str):
    text = text.strip()
    print(f"[{username}@{chat_id}] {text[:80]}")

    # ── Built-in commands ──────────────────────────────────────────────────────
    if text == "/start":
        return cmd_start(chat_id)
    if text == "/agents":
        return cmd_agents(chat_id)
    if text == "/clear":
        return cmd_clear(chat_id)
    if text == "/alerts":
        return cmd_alerts(chat_id)

    # ── Agent slash commands ───────────────────────────────────────────────────
    cmd_match = re.match(r"^/(\w+)(?:\s+(.*))?$", text, re.DOTALL)
    if cmd_match:
        cmd = cmd_match.group(1).lower()
        args = (cmd_match.group(2) or "").strip()

        if cmd == "bounty":
            return cmd_bounty(chat_id, args)
        if cmd == "alpha":
            return cmd_alpha(chat_id, args)
        if cmd == "atlas":
            return cmd_atlas(chat_id, args)
        if cmd == "gmail":
            return cmd_gmail(chat_id, args)
        if cmd == "news":
            return cmd_news(chat_id, args)
        if cmd == "weather":
            return cmd_weather(chat_id, args)
        if cmd == "remind":
            return cmd_remind(chat_id, args)
        if cmd == "status":
            return cmd_status(chat_id)
        if cmd in ("scout", "architect", "herald", "forge"):
            return cmd_agent_route(chat_id, cmd, args, text)

        # Unknown slash command → NEXUS handles it
        send_message(chat_id, f"Unknown command `/{cmd}`. Use /start to see available commands.")
        return

    # ── Regular message → NEXUS orchestrator ──────────────────────────────────
    send_typing(chat_id)
    response = ask_claude_with_history(chat_id, text, agent="nexus")
    send_message(chat_id, response)
    print(f"   → Replied ({len(response)} chars)")


# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    _acquire_pid()
    import atexit
    atexit.register(_release_pid)

    print("=" * 50)
    print("  NEXUS Agency Bot — Starting up")
    print("=" * 50)
    print(f"  Token:     {'set' if BOT_TOKEN else 'MISSING!'}")
    print(f"  Owner ID:  {OWNER_CHAT_ID or 'not set (all users accepted)'}")
    print(f"  DB:        nexus.db (SQLite)")

    # Check claude CLI
    try:
        test = subprocess.run(["claude", "--version"], capture_output=True, timeout=5)
        ver = test.stdout.decode("utf-8", errors="replace").strip()
        print(f"  Claude:    OK — {ver}")
    except Exception as e:
        print(f"  Claude:    WARNING — {e}")

    # Start background scheduler
    try:
        import scheduler
        scheduler.init(send_message, OWNER_CHAT_ID)
        scheduler.start_all()
        print("  Scheduler: All background threads started")
    except Exception as e:
        print(f"  Scheduler: WARNING — {e}")

    print("\n  Polling for messages...\n")

    if OWNER_CHAT_ID:
        send_message(OWNER_CHAT_ID, "🧠 *NEXUS Online* — All systems nominal. Type /start for help.")

    offset = 0
    backoff = 1

    while True:
        try:
            result = tg_get("getUpdates", {"offset": offset, "timeout": 20, "limit": 10})
            if not result or not result.get("ok"):
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)
                continue

            backoff = 1  # Reset on success
            updates = result.get("result", [])

            # Fire any pending reminders
            try:
                from agents.skills import check_reminders, format_reminder_alert
                for reminder in check_reminders():
                    send_message(reminder["chat_id"], format_reminder_alert(reminder))
            except Exception:
                pass

            for update in updates:
                offset = update["update_id"] + 1
                msg = update.get("message")
                if not msg:
                    continue

                chat_id = msg["chat"]["id"]
                text = msg.get("text", "").strip()
                username = msg.get("from", {}).get("username", "user")

                if not text:
                    continue

                # Optional: only accept messages from owner
                if OWNER_CHAT_ID and chat_id != OWNER_CHAT_ID:
                    send_message(chat_id, "⛔ Unauthorized. This is a private NEXUS instance.")
                    continue

                try:
                    handle_message(chat_id, text, username)
                except Exception as e:
                    print(f"[Message handler error] {e}")
                    send_message(chat_id, f"⚠️ Something went wrong: {str(e)[:100]}")

        except KeyboardInterrupt:
            print("\nNEXUS Bot stopped by user.")
            _release_pid()
            sys.exit(0)
        except Exception as e:
            print(f"[Poll loop error] {e}")
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)


if __name__ == "__main__":
    main()
