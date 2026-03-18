# -*- coding: utf-8 -*-
"""
bounty_agent.py — BOUNTY: Hackathon/grant/opportunity scanner.

Sources:
  - Devpost public API
  - DoraHacks public API
  - Gitcoin Grants Stack GraphQL indexer
  - Superteam Earn RSS

Runs on a background thread daily at 09:00.
Saves new opportunities to SQLite and pushes digest to Telegram.
"""

import urllib.request
import urllib.error
import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import save_opportunity, get_top_opportunities, mark_notified
from config import score_opportunity

TIMEOUT = 20


def _fetch(url: str, headers=None) -> dict | list | None:
    try:
        req = urllib.request.Request(url, headers=headers or {
            "User-Agent": "NEXUS-Agency/1.0"
        })
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as e:
        print(f"[BOUNTY] fetch error {url[:60]}: {e}")
        return None


def _fetch_text(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "NEXUS-Agency/1.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"[BOUNTY] text fetch error {url[:60]}: {e}")
        return ""


# ── Devpost ───────────────────────────────────────────────────────────────────

def scan_devpost() -> int:
    """Scan Devpost open hackathons. Returns count of new opportunities."""
    print("[BOUNTY] Scanning Devpost...")
    data = _fetch("https://devpost.com/api/hackathons?status=open&order_by=prize_amount&per_page=20")
    if not data:
        return 0

    hackathons = data.get("hackathons", [])
    count = 0
    for h in hackathons:
        title = h.get("title", "Unknown")
        url = h.get("url", "")
        if not url:
            continue
        prize = h.get("prize_amount", "")
        try:
            prize_str = f"${int(prize):,}" if prize else "TBD"
        except (ValueError, TypeError):
            prize_str = str(prize) if prize else "TBD"
        deadline_raw = h.get("submission_period_dates", "")
        fit = score_opportunity(title, h.get("themes", [{}])[0].get("name", "") if h.get("themes") else "")
        if save_opportunity(title, url, prize_str, deadline_raw, fit, "Devpost"):
            count += 1

    print(f"[BOUNTY] Devpost: {count} new")
    return count


# ── DoraHacks ─────────────────────────────────────────────────────────────────

def scan_dorahacks() -> int:
    print("[BOUNTY] Scanning DoraHacks...")
    data = _fetch("https://dorahacks.io/api/hackathon/list?status=open&limit=20")
    if not data:
        return 0

    items = data if isinstance(data, list) else data.get("data", data.get("list", []))
    count = 0
    for h in items:
        if not isinstance(h, dict):
            continue
        title = h.get("title") or h.get("name", "Unknown")
        # DoraHacks uses slug-based URLs
        slug = h.get("slug") or h.get("id", "")
        url = f"https://dorahacks.io/hackathon/{slug}" if slug else ""
        if not url:
            continue
        prize = h.get("prize", h.get("total_prize", "TBD"))
        prize_str = str(prize) if prize else "TBD"
        deadline = h.get("end_time", h.get("deadline", ""))
        fit = score_opportunity(title)
        if save_opportunity(title, url, prize_str, str(deadline), fit, "DoraHacks"):
            count += 1

    print(f"[BOUNTY] DoraHacks: {count} new")
    return count


# ── Gitcoin ───────────────────────────────────────────────────────────────────

def scan_gitcoin() -> int:
    print("[BOUNTY] Scanning Gitcoin...")
    query = """
    {
      rounds(filter: {strategyName: "allov2.DonationVotingMerkleDistributionDirectTransferStrategy"},
             orderBy: CREATED_AT_DESC, first: 10) {
        nodes {
          roundMetadata
          donationsStartTime
          donationsEndTime
          chainId
          id
        }
      }
    }
    """
    url = "https://grants-stack-indexer-v2.gitcoin.co/graphql"
    try:
        payload = json.dumps({"query": query}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={
            "Content-Type": "application/json",
            "User-Agent": "NEXUS-Agency/1.0"
        })
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as e:
        print(f"[BOUNTY] Gitcoin error: {e}")
        return 0

    rounds = (data.get("data", {}).get("rounds", {}) or {}).get("nodes", [])
    count = 0
    for r in rounds:
        meta = r.get("roundMetadata") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        title = meta.get("name", "Gitcoin Round")
        chain = r.get("chainId", "")
        round_id = r.get("id", "")
        url_link = f"https://grants.gitcoin.co/#/round/{chain}/{round_id}"
        deadline = r.get("donationsEndTime", "")
        fit = score_opportunity(title)
        if save_opportunity(title, url_link, "Quadratic Funding Pool", str(deadline), fit, "Gitcoin"):
            count += 1

    print(f"[BOUNTY] Gitcoin: {count} new")
    return count


# ── Superteam Earn RSS ────────────────────────────────────────────────────────

def scan_superteam() -> int:
    print("[BOUNTY] Scanning Superteam Earn...")
    text = _fetch_text("https://earn.superteam.fun/api/listings/rss/")
    if not text:
        return 0

    count = 0
    try:
        root = ET.fromstring(text)
        channel = root.find("channel")
        if channel is None:
            return 0
        for item in channel.findall("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            desc = (item.findtext("description") or "").strip()
            if not link:
                continue
            fit = score_opportunity(title, desc)
            if save_opportunity(title, link, "See listing", "", fit, "Superteam"):
                count += 1
    except Exception as e:
        print(f"[BOUNTY] Superteam RSS parse error: {e}")

    print(f"[BOUNTY] Superteam: {count} new")
    return count


# ── Main scan ─────────────────────────────────────────────────────────────────

def run_scan() -> int:
    """Run all source scans. Returns total new opportunities found."""
    total = 0
    for fn in [scan_devpost, scan_dorahacks, scan_gitcoin, scan_superteam]:
        try:
            total += fn()
        except Exception as e:
            print(f"[BOUNTY] Scan error in {fn.__name__}: {e}")
    print(f"[BOUNTY] Total new opportunities: {total}")
    return total


def _fit_bar(score: int) -> str:
    filled = score
    empty = 10 - score
    return "▓" * filled + "░" * empty


def _fit_label(score: int) -> str:
    if score >= 9: return "🔥 Perfect"
    if score >= 7: return "✅ Strong"
    if score >= 5: return "👍 Good"
    return "📌 Low"


def format_digest(limit: int = 5) -> str:
    today = datetime.now().strftime("%B %d, %Y")
    opps = get_top_opportunities(limit=limit)

    if not opps:
        return (
            f"🏹 *BOUNTY  |  Daily Report*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"_{today}_\n\n"
            f"No opportunities in DB yet.\n"
            f"Use /bounty to trigger a live scan."
        )

    lines = [
        f"🏹 *BOUNTY  |  Daily Report*",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"_{today}  ·  Top {len(opps)} opportunities_\n",
    ]
    for i, opp in enumerate(opps, 1):
        prize = opp.get("prize") or "TBD"
        deadline = (opp.get("deadline") or "Open")[:30]
        fit = opp.get("fit_score", 5)
        source = opp.get("source", "")
        bar = _fit_bar(fit)
        label = _fit_label(fit)
        lines.append(
            f"*{i}. {opp['title']}*\n"
            f"   💰 {prize}  ·  📅 {deadline}\n"
            f"   `[{bar}]` {label}  _{source}_\n"
            f"   🔗 [Open]({opp['url']})\n"
        )
        mark_notified(opp["id"])

    lines.append("_/bounty live  to see all  ·  refreshes daily @ 9AM_")
    return "\n".join(lines)


def get_live_report(limit: int = 10) -> str:
    opps = get_top_opportunities(limit=limit)
    today = datetime.now().strftime("%B %d, %Y")

    if not opps:
        return (
            f"🏹 *BOUNTY  |  Live DB*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Nothing stored yet. Run /bounty to scan."
        )

    lines = [
        f"🏹 *BOUNTY  |  All Opportunities*",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"_{today}  ·  {len(opps)} results_\n",
    ]
    for i, opp in enumerate(opps, 1):
        prize = opp.get("prize") or "TBD"
        fit = opp.get("fit_score", 5)
        bar = _fit_bar(fit)
        lines.append(
            f"*{i}. {opp['title']}*\n"
            f"   💰 {prize}  `[{bar}]` {fit}/10\n"
            f"   [View]({opp['url']})\n"
        )
    return "\n".join(lines)
