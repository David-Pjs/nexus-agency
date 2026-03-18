# -*- coding: utf-8 -*-
"""
alpha_agent.py — ALPHA: Crypto & DeFi intelligence monitor.

Free APIs only:
  - CoinGecko (no key needed for basic tier)
  - DeFiLlama yields
  - Fear & Greed Index

Runs every 2 hours on background thread.
Checks price alerts and pushes actionable Telegram notifications.
"""

import urllib.request
import urllib.parse
import json
import time

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_active_alerts, deactivate_alert

TIMEOUT = 20
COINGECKO_BASE = "https://api.coingecko.com/api/v3"
DEFILLAMA_YIELDS = "https://yields.llama.fi/pools"
FEAR_GREED_URL = "https://api.alternative.me/fng/?limit=1"

# Map common symbols → CoinGecko IDs
SYMBOL_MAP = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
    "BNB": "binancecoin", "MATIC": "matic-network", "ARB": "arbitrum",
    "OP": "optimism", "AVAX": "avalanche-2", "LINK": "chainlink",
    "UNI": "uniswap", "AAVE": "aave", "CRV": "curve-dao-token",
    "DOGE": "dogecoin", "XRP": "ripple", "ADA": "cardano",
    "DOT": "polkadot", "ATOM": "cosmos", "NEAR": "near",
    "SUI": "sui", "APT": "aptos", "INJ": "injective-protocol",
}

DEFAULT_COINS = ["BTC", "ETH", "SOL", "BNB"]


def _fetch(url: str) -> dict | list | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "NEXUS-Agency/1.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as e:
        print(f"[ALPHA] fetch error {url[:80]}: {e}")
        return None


# ── CoinGecko ─────────────────────────────────────────────────────────────────

def get_prices(symbols: list = None) -> dict:
    """Returns {SYMBOL: {price, change_24h, market_cap}} for each symbol."""
    symbols = symbols or DEFAULT_COINS
    ids = ",".join(SYMBOL_MAP.get(s.upper(), s.lower()) for s in symbols)
    url = (f"{COINGECKO_BASE}/simple/price?ids={ids}"
           f"&vs_currencies=usd&include_24hr_change=true&include_market_cap=true")
    data = _fetch(url)
    if not data:
        return {}

    result = {}
    for sym in symbols:
        cg_id = SYMBOL_MAP.get(sym.upper(), sym.lower())
        if cg_id in data:
            d = data[cg_id]
            result[sym.upper()] = {
                "price": d.get("usd", 0),
                "change_24h": d.get("usd_24h_change", 0),
                "market_cap": d.get("usd_market_cap", 0),
            }
    return result


def get_coin_detail(symbol: str) -> dict | None:
    """Detailed info for one coin."""
    cg_id = SYMBOL_MAP.get(symbol.upper(), symbol.lower())
    url = f"{COINGECKO_BASE}/coins/{cg_id}?localization=false&tickers=false&community_data=false&developer_data=false"
    data = _fetch(url)
    if not data:
        return None
    md = data.get("market_data", {})
    return {
        "name": data.get("name"),
        "symbol": symbol.upper(),
        "price": md.get("current_price", {}).get("usd", 0),
        "change_24h": md.get("price_change_percentage_24h", 0),
        "change_7d": md.get("price_change_percentage_7d", 0),
        "ath": md.get("ath", {}).get("usd", 0),
        "ath_change": md.get("ath_change_percentage", {}).get("usd", 0),
        "market_cap": md.get("market_cap", {}).get("usd", 0),
        "rank": data.get("market_cap_rank", 0),
        "description": (data.get("description", {}).get("en", "") or "")[:200],
    }


# ── DeFiLlama ─────────────────────────────────────────────────────────────────

def get_top_yields(min_apy: float = 15.0, stablecoins_only: bool = True, limit: int = 8) -> list:
    """Get top yield pools from DeFiLlama."""
    data = _fetch(DEFILLAMA_YIELDS)
    if not data:
        return []

    pools = data.get("data", [])
    filtered = []
    for p in pools:
        apy = p.get("apy", 0) or 0
        if apy < min_apy:
            continue
        is_stable = p.get("stablecoin", False)
        if stablecoins_only and not is_stable:
            continue
        tvl = p.get("tvlUsd", 0) or 0
        if tvl < 1_000_000:  # Minimum $1M TVL for safety
            continue
        filtered.append({
            "pool": p.get("symbol", ""),
            "project": p.get("project", ""),
            "chain": p.get("chain", ""),
            "apy": round(apy, 2),
            "tvl": tvl,
            "stable": is_stable,
        })

    # Sort by APY descending
    filtered.sort(key=lambda x: x["apy"], reverse=True)
    return filtered[:limit]


# ── Fear & Greed ──────────────────────────────────────────────────────────────

def get_fear_greed() -> dict:
    data = _fetch(FEAR_GREED_URL)
    if not data:
        return {"value": "N/A", "label": "Unknown"}
    entry = (data.get("data") or [{}])[0]
    return {
        "value": entry.get("value", "N/A"),
        "label": entry.get("value_classification", "Unknown"),
        "timestamp": entry.get("timestamp", ""),
    }


# ── Alert checking ────────────────────────────────────────────────────────────

def check_alerts() -> list:
    """
    Check active price alerts against current prices.
    Returns list of triggered alerts: {alert, price}.
    """
    alerts = get_active_alerts()
    if not alerts:
        return []

    symbols = list({a["symbol"] for a in alerts})
    prices = get_prices(symbols)
    triggered = []

    for alert in alerts:
        sym = alert["symbol"]
        current = prices.get(sym, {}).get("price")
        if current is None:
            continue
        target = alert["target"]
        direction = alert["direction"]

        hit = False
        if direction == "above" and current >= target:
            hit = True
        elif direction == "below" and current <= target:
            hit = True

        if hit:
            triggered.append({"alert": alert, "price": current})
            deactivate_alert(alert["id"])

    return triggered


# ── Formatters ────────────────────────────────────────────────────────────────

def _bar(value: int, total: int = 100, width: int = 10) -> str:
    filled = int((value / total) * width)
    return "█" * filled + "░" * (width - filled)


def format_snapshot(symbols: list = None) -> str:
    symbols = symbols or DEFAULT_COINS
    prices = get_prices(symbols)
    fg = get_fear_greed()

    if not prices:
        return "⚡ *ALPHA* — CoinGecko rate-limited. Try again in 60s."

    coin_em = {"BTC": "₿", "ETH": "Ξ", "SOL": "◎", "BNB": "🔶",
               "MATIC": "💜", "ARB": "🔵", "OP": "🔴", "AVAX": "🔺"}

    from datetime import datetime
    now = datetime.now().strftime("%H:%M")

    lines = [f"⚡ *ALPHA  |  Market Pulse*", f"━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    for sym, d in prices.items():
        price = d["price"]
        chg = d["change_24h"]
        dot = "🟢" if chg >= 0 else "🔴"
        em = coin_em.get(sym, "◆")
        lines.append(f"{dot} {em} *{sym}*    `${price:>12,.2f}`  {chg:+.1f}%")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")

    try:
        v = int(str(fg["value"]).replace("N/A", "50"))
        bar = _bar(v)
        mood = ("😱 Extreme Fear" if v < 25 else "😨 Fear" if v < 45
                else "😐 Neutral" if v < 55 else "😏 Greed" if v < 75
                else "🤑 Extreme Greed")
        lines.append(f"{mood}  `[{bar}]` {v}/100")
    except Exception:
        lines.append(f"Fear & Greed: {fg['label']}")

    lines.append(f"\n_Updated {now} · /alpha BTC for detail · /alpha yields_")
    return "\n".join(lines)


def format_yields() -> str:
    pools = get_top_yields()
    if not pools:
        return "⚡ *ALPHA Yields* — Nothing above 15% APY with $1M+ TVL right now."

    lines = ["⚡ *ALPHA  |  Top Stablecoin Yields*", "━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    for i, p in enumerate(pools, 1):
        tvl_m = p["tvl"] / 1_000_000
        bar = _bar(min(int(p["apy"]), 100), 100, 8)
        lines.append(
            f"*{i}. {p['pool']}*  _{p['project']} · {p['chain']}_\n"
            f"   `[{bar}]` *{p['apy']}% APY*  TVL ${tvl_m:.1f}M\n"
        )
    lines.append("_Min: 15% APY · $1M TVL · Stablecoins only_")
    return "\n".join(lines)


def format_fear_greed() -> str:
    fg = get_fear_greed()
    val = fg["value"]
    label = fg["label"]
    try:
        v = int(val)
        bar = _bar(v)
        zones = "😱Panic  😨Fear  😐Meh  😏Greed  🤑Mania"
        signal = (
            "Historically a *buy zone* — market is oversold" if v < 25
            else "Caution — sentiment weak" if v < 45
            else "Balanced — no strong signal" if v < 55
            else "Watch out — FOMO territory" if v < 75
            else "*Danger zone* — consider taking profits"
        )
        pointer = " " * int(v / 10) + "▲"
        return (
            f"⚡ *ALPHA  |  Fear & Greed*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"`[{bar}]`\n"
            f"`{pointer}`\n"
            f"Score: *{v}/100* — {label}\n\n"
            f"Signal: {signal}\n\n"
            f"_{zones}_"
        )
    except (ValueError, TypeError):
        return f"⚡ Fear & Greed: {label}"


def format_alert_trigger(alert: dict, current_price: float) -> str:
    sym = alert["symbol"]
    target = alert["target"]
    direction = alert["direction"]
    arrow = "📈" if direction == "above" else "📉"
    diff_pct = ((current_price - target) / target) * 100
    return (
        f"🚨 *ALPHA ALERT TRIGGERED*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{arrow} *{sym}* crossed your target\n\n"
        f"Target:   `${target:>12,.2f}`\n"
        f"Current:  `${current_price:>12,.2f}`  ({diff_pct:+.1f}%)\n\n"
        f"_Alert deactivated. Set a new one with /alpha alert_"
    )
