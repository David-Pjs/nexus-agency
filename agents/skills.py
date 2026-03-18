# -*- coding: utf-8 -*-
"""
skills.py — Extra skills for NEXUS: /news, /weather, /remind, /status

All free, zero API keys required.
"""

import urllib.request
import urllib.parse
import json
import time
import threading
import xml.etree.ElementTree as ET
from datetime import datetime

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TIMEOUT = 15

# ── Pending reminders (in-memory, survives as long as bot runs) ───────────────
_reminders = []  # list of {chat_id, message, fire_at}
_reminder_lock = threading.Lock()


def _fetch(url: str, headers: dict = None) -> bytes:
    try:
        req = urllib.request.Request(url, headers=headers or {"User-Agent": "NEXUS-Agency/1.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read()
    except Exception as e:
        print(f"[Skills] fetch error: {e}")
        return b""


# ── /news ─────────────────────────────────────────────────────────────────────

NEWS_FEEDS = [
    ("Crypto", "https://cointelegraph.com/rss"),
    ("Tech",   "https://feeds.feedburner.com/TechCrunch"),
    ("Web3",   "https://decrypt.co/feed"),
]


def get_news(topic: str = "", limit: int = 6) -> str:
    topic_lower = topic.lower()

    # Pick feed based on topic
    if any(w in topic_lower for w in ["crypto", "btc", "eth", "defi", "web3", "token"]):
        feeds = [("Crypto", NEWS_FEEDS[0][1]), ("Web3", NEWS_FEEDS[2][1])]
    elif any(w in topic_lower for w in ["tech", "ai", "startup"]):
        feeds = [("Tech", NEWS_FEEDS[1][1])]
    else:
        feeds = NEWS_FEEDS

    items = []
    for label, url in feeds:
        raw = _fetch(url)
        if not raw:
            continue
        try:
            root = ET.fromstring(raw.decode("utf-8", errors="replace"))
            channel = root.find("channel") or root
            for item in channel.findall("item")[:4]:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub = (item.findtext("pubDate") or "").strip()[:16]
                if title and link:
                    items.append({"title": title, "link": link, "pub": pub, "source": label})
        except Exception as e:
            print(f"[Skills] RSS parse error: {e}")

    if not items:
        return "📰 *NEWS* — Could not fetch feeds right now. Try again in a moment."

    # If topic specified, filter
    if topic_lower:
        filtered = [i for i in items if topic_lower in i["title"].lower()]
        if filtered:
            items = filtered

    items = items[:limit]
    now = datetime.now().strftime("%b %d, %H:%M")
    lines = [
        f"📰 *NEWS  |  {'#' + topic if topic else 'Latest'}*",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"_{now}_\n",
    ]
    for i, item in enumerate(items, 1):
        lines.append(
            f"*{i}.* [{item['title'][:65]}]({item['link']})\n"
            f"   _{item['source']} · {item['pub']}_\n"
        )
    lines.append("_/news crypto · /news tech · /news ai_")
    return "\n".join(lines)


# ── /weather ──────────────────────────────────────────────────────────────────

def get_weather(city: str = "Lagos") -> str:
    """Uses wttr.in — free, no key needed."""
    encoded = urllib.parse.quote(city)
    url = f"https://wttr.in/{encoded}?format=j1"
    raw = _fetch(url)
    if not raw:
        return f"🌤 *Weather* — Could not fetch for {city}."

    try:
        data = json.loads(raw.decode("utf-8", errors="replace"))
        current = data["current_condition"][0]
        area = data["nearest_area"][0]
        area_name = area["areaName"][0]["value"]
        country = area["country"][0]["value"]

        temp_c = current["temp_C"]
        feels_c = current["FeelsLikeC"]
        desc = current["weatherDesc"][0]["value"]
        humidity = current["humidity"]
        wind_kmph = current["windspeedKmph"]

        # 3-day forecast
        forecast_lines = []
        for day in data.get("weather", [])[:3]:
            date = day["date"]
            max_c = day["maxtempC"]
            min_c = day["mintempC"]
            desc_d = day["hourly"][4]["weatherDesc"][0]["value"]
            forecast_lines.append(f"  {date}: {desc_d}, {min_c}°–{max_c}°C")

        forecast = "\n".join(forecast_lines)

        # Pick emoji
        desc_low = desc.lower()
        em = ("⛈" if "thunder" in desc_low else "🌧" if "rain" in desc_low
              else "🌥" if "cloud" in desc_low else "🌤" if "partly" in desc_low
              else "☀️" if "sunny" in desc_low or "clear" in desc_low else "🌡")

        return (
            f"{em} *Weather  |  {area_name}, {country}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Now: *{temp_c}°C* (feels {feels_c}°C)\n"
            f"Conditions: {desc}\n"
            f"Humidity: {humidity}%  ·  Wind: {wind_kmph} km/h\n\n"
            f"*3-Day Forecast:*\n{forecast}\n\n"
            f"_/weather [city] for any location_"
        )
    except Exception as e:
        print(f"[Skills] Weather parse error: {e}")
        return f"🌤 Could not parse weather for {city}."


# ── /remind ───────────────────────────────────────────────────────────────────

def parse_duration(text: str) -> int | None:
    """Parse '30m', '2h', '1h30m' etc → seconds. Returns None if unparseable."""
    import re
    text = text.strip().lower()
    total = 0
    for val, unit in re.findall(r"(\d+)\s*([mhs])", text):
        val = int(val)
        if unit == "h":   total += val * 3600
        elif unit == "m": total += val * 60
        elif unit == "s": total += val
    return total if total > 0 else None


def set_reminder(chat_id: int, duration_str: str, message: str) -> str:
    secs = parse_duration(duration_str)
    if not secs:
        return (
            "⏰ *Remind* — I didn't understand that time.\n\n"
            "Examples:\n"
            "`/remind 30m Check the oven`\n"
            "`/remind 2h Review proposal`\n"
            "`/remind 1h30m Call back David`"
        )

    fire_at = time.time() + secs
    with _reminder_lock:
        _reminders.append({"chat_id": chat_id, "message": message, "fire_at": fire_at})

    mins = secs // 60
    hrs = mins // 60
    if hrs > 0:
        time_str = f"{hrs}h {mins % 60}m" if mins % 60 else f"{hrs}h"
    else:
        time_str = f"{mins}m"

    fire_time = datetime.fromtimestamp(fire_at).strftime("%H:%M")
    return (
        f"⏰ *Reminder set!*\n\n"
        f"I'll ping you in *{time_str}* (at {fire_time})\n"
        f"Message: _{message}_"
    )


def check_reminders() -> list:
    """Return fired reminders and remove them from the list."""
    now = time.time()
    fired = []
    with _reminder_lock:
        remaining = []
        for r in _reminders:
            if r["fire_at"] <= now:
                fired.append(r)
            else:
                remaining.append(r)
        _reminders.clear()
        _reminders.extend(remaining)
    return fired


def format_reminder_alert(reminder: dict) -> str:
    return (
        f"⏰ *REMINDER*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{reminder['message']}"
    )


# ── /status ───────────────────────────────────────────────────────────────────

_start_time = time.time()


def get_status(active_alerts: int = 0, opp_count: int = 0) -> str:
    uptime_secs = int(time.time() - _start_time)
    h = uptime_secs // 3600
    m = (uptime_secs % 3600) // 60

    uptime_str = f"{h}h {m}m" if h > 0 else f"{m}m"
    now = datetime.now().strftime("%b %d, %H:%M")

    return (
        f"🧠 *NEXUS  |  System Status*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Status:     🟢 Online\n"
        f"Uptime:     {uptime_str}\n"
        f"Time:       {now}\n\n"
        f"*Background Jobs:*\n"
        f"🏹 BOUNTY scanner   — daily @ 09:00\n"
        f"⚡ ALPHA monitor    — every 2h\n"
        f"📅 ATLAS briefing   — daily @ 08:00\n"
        f"📧 Gmail monitor    — every 30m\n\n"
        f"*Data:*\n"
        f"Price alerts:   {active_alerts} active\n"
        f"Opportunities:  {opp_count} in DB\n\n"
        f"_Powered by Claude Code + SQLite_\n"
        f"_/agents to see all commands_"
    )
