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


def send_photo(chat_id: int, image_url: str, caption: str = ""):
    """Send an image to Telegram by URL."""
    tg_post("sendPhoto", {
        "chat_id": chat_id,
        "photo": image_url,
        "caption": caption,
        "parse_mode": "Markdown",
    })


def download_file(file_id: str) -> bytes | None:
    """Download a file from Telegram servers."""
    info = tg_get("getFile", {"file_id": file_id})
    if not info or not info.get("ok"):
        return None
    file_path = info["result"]["file_path"]
    url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "NEXUS-Agency/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()
    except Exception as e:
        print(f"[Download error] {e}")
        return None


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
        "`/imagine`  [prompt] — generate an image\n"
        "`/browse`  [url] — read any webpage\n"
        "`/search`  [query] — search the web\n"
        "`/act`  [url] [task] — fill forms, click, navigate\n"
        "`/status` — system health\n\n"
        "_Send me any photo and I'll analyze it._\n\n"
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


def cmd_imagine(chat_id: int, prompt: str):
    """Generate an image via Pollinations.ai — free, no key needed."""
    if not prompt.strip():
        send_message(chat_id,
            "🎨 *FORGE  |  Image Generation*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Usage: `/imagine [description]`\n\n"
            "Examples:\n"
            "`/imagine futuristic Lagos skyline at night`\n"
            "`/imagine African developer coding in space`\n"
            "`/imagine neon cyberpunk Abuja marketplace`"
        )
        return

    send_typing(chat_id)
    send_message(chat_id, "🎨 Generating your image...")

    # Pollinations.ai — completely free, no auth
    encoded = urllib.parse.quote(prompt.strip())
    seed = int(time.time()) % 9999
    image_url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&seed={seed}&nologo=true"

    send_photo(chat_id, image_url, caption=f"🎨 _{prompt[:100]}_")
    print(f"[FORGE] Image generated: {prompt[:60]}")


def cmd_analyze_image(chat_id: int, file_id: str, caption: str = ""):
    """Download a Telegram image and analyze it with Claude."""
    send_typing(chat_id)
    send_message(chat_id, "👁 Analyzing your image...")

    img_bytes = download_file(file_id)
    if not img_bytes:
        send_message(chat_id, "⚠️ Could not download the image. Try again.")
        return

    # Save temporarily
    import tempfile
    tmp_path = os.path.join(_HERE, f"_tmp_img_{int(time.time())}.jpg")
    try:
        with open(tmp_path, "wb") as f:
            f.write(img_bytes)

        question = caption.strip() if caption.strip() else "Describe this image in detail. What do you see? If there is text, read it. If there is a chart or data, analyze it. If it is a document, summarize it."

        cmd = [
            "claude",
            "--system-prompt", "You are NEXUS, an expert image analyst. Analyze images thoroughly — read text, interpret charts, describe scenes, extract data. Be detailed and useful.",
            "--output-format", "text",
            "-p", question,
            "--permission-mode", "dontAsk",
            "--dangerously-skip-permissions",
        ]

        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        # Pass image path in the prompt since claude CLI supports file attachments
        prompt_with_image = f"[Image file: {tmp_path}]\n\n{question}"
        cmd[-1] = prompt_with_image

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=CLAUDE_TIMEOUT, env=env, cwd=_HERE)
        response = result.stdout.decode("utf-8", errors="replace").strip()

        if not response:
            response = "I can see the image but couldn't generate a detailed analysis. Try asking a specific question about it."

        send_message(chat_id,
            f"👁 *NEXUS  |  Image Analysis*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{response}"
        )
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


def send_photo_local(chat_id: int, image_url: str, caption: str = "", local_path: str = ""):
    """Send a photo from local file path or URL."""
    if local_path and os.path.exists(local_path):
        url = f"{API_BASE}/sendPhoto"
        import io
        with open(local_path, "rb") as f:
            img_data = f.read()
        boundary = "----NexusBoundary"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="chat_id"\r\n\r\n'
            f"{chat_id}\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="caption"\r\n\r\n'
            f"{caption}\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="photo"; filename="screen.png"\r\n'
            f"Content-Type: image/png\r\n\r\n"
        ).encode() + img_data + f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(url, data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        try:
            urllib.request.urlopen(req, timeout=30)
        except Exception as e:
            print(f"[send_photo_local error] {e}")
    elif image_url:
        send_photo(chat_id, image_url, caption)


def cmd_act(chat_id: int, args: str):
    """Plan an agentic browser task — shows plan before doing anything."""
    parts = args.strip().split(None, 1)
    if len(parts) < 2:
        send_message(chat_id,
            "🤖 *NEXUS  |  Agent Browser*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Usage: `/act [url] [task]`\n\n"
            "Examples:\n"
            "`/act https://ethglobal.com/events register for the hackathon`\n"
            "`/act https://forms.google.com/xyz fill out the form`\n"
            "`/act https://example.com click the sign up button`\n\n"
            "_I will show you a full plan before doing anything._"
        )
        return

    url = parts[0].strip()
    task = parts[1].strip()

    if not url.startswith("http"):
        url = "https://" + url

    send_typing(chat_id)
    send_message(chat_id, f"🤖 Reading `{url[:60]}`...\n_Building your action plan..._")

    from agent_browser import (
        read_page_for_planning, build_plan, format_plan,
        store_pending, _is_dangerous
    )

    page_info = read_page_for_planning(url)

    if "error" in page_info:
        send_message(chat_id,
            f"⚠️ Could not open that page.\n\n"
            f"Error: `{page_info['error'][:100]}`\n\n"
            f"Make sure Playwright is installed:\n"
            f"`pip install playwright`\n"
            f"`playwright install chromium`"
        )
        return

    # Send screenshot of the page
    ss = page_info.get("screenshot_path", "")
    if ss and os.path.exists(ss):
        send_photo_local(chat_id, None, caption=f"Current state of {url[:50]}", local_path=ss)
        try:
            os.remove(ss)
        except Exception:
            pass

    # Build plan
    steps = build_plan(task, page_info)
    dangerous = _is_dangerous(steps)

    # Store pending
    store_pending(chat_id, task, url, steps, dangerous)

    # Show plan
    plan_text = format_plan(task, url, steps)
    send_message(chat_id, plan_text)


def cmd_confirm(chat_id: int, args: str):
    """Execute a pending action plan after user confirmation."""
    from agent_browser import pop_pending, _is_dangerous, execute_plan

    pending = pop_pending(chat_id)
    if not pending:
        send_message(chat_id, "⚠️ No pending action, or it expired (5 min limit). Run `/act` again.")
        return

    # Double-check dangerous actions
    if pending["is_dangerous"] and args.strip().upper() != "DANGEROUS":
        send_message(chat_id,
            "🚨 *This plan includes high-risk actions.*\n\n"
            "To confirm, type exactly:\n`/confirm DANGEROUS`\n\n"
            "Or `/cancel` to abort."
        )
        # Put it back
        from agent_browser import store_pending
        store_pending(chat_id, pending["task"], pending["url"],
                      pending["steps"], pending["is_dangerous"])
        return

    send_message(chat_id,
        f"🤖 *Executing plan...*\n"
        f"Task: _{pending['task']}_\n"
        f"Steps: {len(pending['steps'])}\n\n"
        f"_I'll send you a screenshot after each action._"
    )

    result = execute_plan(
        chat_id,
        pending["steps"],
        pending["url"],
        send_message,
        send_photo_local
    )
    send_message(chat_id, result)


def cmd_cancel(chat_id: int):
    """Cancel a pending action plan."""
    from agent_browser import cancel_pending, has_pending
    if has_pending(chat_id):
        cancel_pending(chat_id)
        send_message(chat_id, "✅ Action cancelled. Nothing was executed.")
    else:
        send_message(chat_id, "Nothing to cancel.")


def cmd_browse(chat_id: int, args: str):
    """Read any URL and summarize it."""
    parts = args.strip().split(None, 1)
    if not parts:
        send_message(chat_id,
            "🌐 *Browse* — Usage:\n\n"
            "`/browse https://example.com`\n"
            "`/browse https://example.com what is their pricing?`\n\n"
            "_Reads any webpage and summarizes it._"
        )
        return

    url = parts[0].strip()
    question = parts[1].strip() if len(parts) > 1 else ""

    send_typing(chat_id)
    send_message(chat_id, f"🌐 Reading `{url[:60]}`...")

    from browser import read_page, format_page_summary
    content = read_page(url)

    if not content or content.startswith("Could not"):
        send_message(chat_id, f"⚠️ Could not read that page. Try `/search` instead.")
        return

    prompt = format_page_summary(url, content, question)
    send_typing(chat_id)
    response = ask_claude(prompt, AGENT_PROMPTS.get("scout", AGENT_PROMPTS["nexus"]))
    save_message(chat_id, "user", f"/browse {args}")
    save_message(chat_id, "assistant", response)
    send_message(chat_id,
        f"🌐 *Browse  |  {url[:50]}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{response}"
    )


def cmd_search(chat_id: int, args: str):
    """Search the web via DuckDuckGo."""
    query = args.strip()
    if not query:
        send_message(chat_id,
            "🔍 *Search* — Usage:\n\n"
            "`/search Nigeria tech ecosystem 2025`\n"
            "`/search best DeFi protocols on Base`\n"
            "`/search Claude Code alternatives`"
        )
        return

    send_typing(chat_id)
    from browser import search_web, format_search_results
    results = search_web(query)
    send_message(chat_id, format_search_results(query, results))


def cmd_scout(chat_id: int, topic: str):
    """SCOUT — research with live web search built in."""
    if not topic.strip():
        send_message(chat_id, "🔭 *SCOUT* — What do you want me to research?\n\nExample: `/scout Nigeria fintech ecosystem 2025`")
        return

    send_typing(chat_id)
    send_message(chat_id, f"🔭 *SCOUT* searching the web for: _{topic}_...")

    # Step 1 — search the web
    from browser import search_web, read_page
    results = search_web(topic, num_results=4)

    # Step 2 — read top 2 results for depth
    web_context = ""
    if results:
        web_context = "**Live web search results:**\n"
        for i, r in enumerate(results, 1):
            web_context += f"{i}. {r['title']} - {r['url']}\n   {r['snippet']}\n\n"

        # Deep-read top result
        top_url = results[0]["url"]
        send_message(chat_id, f"🔭 Reading top source...")
        page_content = read_page(top_url)
        if page_content and len(page_content) > 300:
            web_context += f"\n**Full content from top source ({top_url}):**\n{page_content[:3000]}\n"

    # Step 3 — ask Claude with real web data
    prompt = (
        f"Research task: {topic}\n\n"
        f"{web_context}\n\n"
        f"Using the live web data above, write a detailed intelligence report with:\n"
        f"1. TL;DR (3 bullet points)\n"
        f"2. Key Findings\n"
        f"3. What this means for a Nigerian/African developer/builder\n"
        f"4. Recommended Actions\n\n"
        f"Be specific, cite the sources, and include current data where available."
    )

    send_typing(chat_id)
    response = ask_claude(prompt, AGENT_PROMPTS.get("scout", AGENT_PROMPTS["nexus"]))
    save_message(chat_id, "user", f"/scout {topic}")
    save_message(chat_id, "assistant", response)
    send_message(chat_id,
        f"🔭 *SCOUT  |  {topic[:50]}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{response}"
    )


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
    if text == "/cancel":
        return cmd_cancel(chat_id)

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
        if cmd == "imagine":
            return cmd_imagine(chat_id, args)
        if cmd == "browse":
            return cmd_browse(chat_id, args)
        if cmd == "search":
            return cmd_search(chat_id, args)
        if cmd == "act":
            return cmd_act(chat_id, args)
        if cmd == "confirm":
            return cmd_confirm(chat_id, args)
        if cmd == "scout":
            return cmd_scout(chat_id, args)
        if cmd in ("architect", "herald", "forge"):
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
                photos = msg.get("photo")

                # Optional: only accept messages from owner
                if OWNER_CHAT_ID and chat_id != OWNER_CHAT_ID:
                    send_message(chat_id, "⛔ Unauthorized. This is a private NEXUS instance.")
                    continue

                try:
                    # Photo message — analyze it
                    if photos:
                        best = max(photos, key=lambda p: p.get("file_size", 0))
                        caption = msg.get("caption", "").strip()
                        cmd_analyze_image(chat_id, best["file_id"], caption)
                        continue

                    if not text:
                        continue

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
