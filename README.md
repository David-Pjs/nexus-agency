# 🧠 NEXUS — Personal AI Agency

> A fully autonomous AI agency running on your local machine, accessible via Telegram.
> **Zero API costs. Zero cloud dependency. Powered by Claude Code.**

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Claude](https://img.shields.io/badge/Powered%20by-Claude%20Code-orange?style=flat-square)
![Telegram](https://img.shields.io/badge/Interface-Telegram-blue?style=flat-square)
![Cost](https://img.shields.io/badge/API%20Cost-$0-brightgreen?style=flat-square)

---

## What is NEXUS?

NEXUS is a personal AI agency you control via Telegram. It runs entirely on your laptop or phone — no expensive API calls per message, no cloud lock-in. As long as you have a Claude Code subscription, every agent call is free.

Most people building AI agents pay $0.01–$0.10 per message. **NEXUS pays $0.**

---

## Agents

| Agent | Command | What it does |
|-------|---------|-------------|
| 🧠 NEXUS | _(just talk)_ | Master orchestrator — routes everything |
| 🔭 SCOUT | `/scout [topic]` | Deep research, web intelligence |
| 📐 ARCHITECT | `/architect [task]` | Business plans, strategy, frameworks |
| 📣 HERALD | `/herald [task]` | Marketing copy, content, campaigns |
| 🏹 BOUNTY | `/bounty` | Live hackathon & grant scanner |
| ⚡ ALPHA | `/alpha` | Crypto prices, DeFi yields, alerts |
| 📅 ATLAS | `/atlas today` | Google Calendar & Gmail integration |
| 🔨 FORGE | `/forge [task]` | Code generation & technical execution |

## Skills

| Skill | Command | What it does |
|-------|---------|-------------|
| 📰 News | `/news [topic]` | Live crypto & tech headlines |
| 🌤 Weather | `/weather [city]` | Forecast anywhere on earth |
| ⏰ Remind | `/remind 30m [msg]` | Personal reminders |
| 📊 Status | `/status` | Bot health & uptime |

---

## Architecture

```
You (Telegram)
      │
      ▼
nexus_bot.py ──── Message Router
      │                 │
      │         ┌───────┼───────┐
      │       BOUNTY  ALPHA  ATLAS  ...
      │
      ▼
Claude Code CLI  ←── Local intelligence (free)
      │
      ▼
SQLite (nexus.db) ←── Persistent memory

Background Threads (24/7):
  ├── BOUNTY scanner    → 09:00 daily
  ├── ALPHA monitor     → every 2h
  ├── ATLAS briefing    → 08:00 daily
  └── Gmail monitor     → every 30min
```

**Key insight:** Instead of calling the Anthropic API (paid per token), NEXUS calls the `claude` CLI subprocess — which uses your existing Claude Code subscription. Unlimited intelligence, flat monthly cost.

---

## Quick Start

### Prerequisites
- Python 3.10+
- [Claude Code](https://claude.ai/code) installed and authenticated
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

### 1. Clone
```bash
git clone https://github.com/yourusername/nexus-agency.git
cd nexus-agency
```

### 2. Configure
```bash
cp .env.example .env
```
Edit `.env`:
```env
TELEGRAM_BOT_TOKEN=your_token_from_botfather
YOUR_TELEGRAM_USER_ID=your_telegram_user_id
```

**Get your Telegram User ID:** Message [@userinfobot](https://t.me/userinfobot) on Telegram.

### 3. Run
```bash
python nexus_bot.py
```

### 4. Talk to it
Open Telegram → find your bot → send `/start`

---

## Google Calendar & Gmail (Optional)

```bash
# 1. Install Google libraries
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client

# 2. Add credentials.json to agency/credentials/
# (Download from Google Cloud Console → APIs & Services → Credentials)

# 3. Authenticate once
python agents/google_agent.py --auth
```

Then `/atlas today` shows your calendar. `/gmail read` shows your inbox.

---

## Running on Android (Termux)

Run NEXUS from your phone — no laptop needed:

```bash
# Install Termux from F-Droid (not Play Store)
pkg update && pkg upgrade -y
pkg install python git nodejs -y
npm install -g @anthropic-ai/claude-code
claude  # authenticate once
git clone https://github.com/yourusername/nexus-agency.git
cd nexus-agency
python nexus_bot.py
```

---

## Example Interactions

```
You: /bounty
NEXUS: 🏹 BOUNTY | Daily Report
       ━━━━━━━━━━━━━━━━━━━━━━━━━━
       1. ETHGlobal Bangkok
          💰 $100,000 | 📅 Apr 15
          [▓▓▓▓▓▓▓▓▓░] Perfect
          🔗 Open

You: /alpha
NEXUS: ⚡ ALPHA | Market Pulse
       ━━━━━━━━━━━━━━━━━━━━━━━━━━
       🟢 ₿ BTC    $71,881.00  +2.1%
       🔴 Ξ ETH     $2,221.49  -4.8%
       😨 Fear & Greed: [██░░░░░░░░] 26/100

You: Find me a web3 hackathon I can win before April
NEXUS: [Routes to BOUNTY + SCOUT, returns ranked opportunities]

You: /remind 2h Review the proposal
NEXUS: ⏰ Reminder set! Pinging you at 16:30
```

---

## Why This Matters for Africa

Developers in Nigeria and across Africa face two barriers to using AI seriously:

1. **Dollar-denominated API costs** — $50/month in API fees hits differently at ₦80k
2. **Unreliable internet** — cloud-dependent tools break on bad connections

NEXUS solves both. The intelligence runs locally via Claude Code's flat subscription. The only network calls are to free public APIs (CoinGecko, Devpost, wttr.in). You can run it on a ₦50k Android phone with Termux.

**AI agency shouldn't be a luxury. This makes it accessible.**

---

## File Structure

```
nexus-agency/
├── nexus_bot.py          # Main bot — message routing, Telegram polling
├── db.py                 # SQLite wrapper — history, alerts, opportunities
├── config.py             # Central config — loads .env, scoring
├── scheduler.py          # Background threads — daily jobs
├── agents/
│   ├── bounty_agent.py   # Hackathon/grant scanner
│   ├── alpha_agent.py    # Crypto monitor
│   ├── google_agent.py   # Calendar/Gmail/Contacts
│   ├── skills.py         # News, weather, reminders, status
│   ├── bounty/AGENT.md   # BOUNTY system prompt
│   ├── alpha/AGENT.md    # ALPHA system prompt
│   └── .../AGENT.md      # Other agent prompts
├── credentials/          # Google OAuth (gitignored)
├── .env                  # Your secrets (gitignored)
└── nexus.db              # SQLite database (gitignored)
```

---

## Important Warnings

### Terms of Service
Claude Code's subscription is designed for interactive developer use. Using it as an automated backend via subprocess is a grey area in Anthropic's ToS. Some users have reported account flags for similar patterns.

**Safer alternatives that work with the same architecture:**
- Anthropic API directly (`pip install anthropic`) — pay per token, no ToS risk
- Ollama — fully local, fully free, no account needed
- Groq free tier — fast, generous free limits

To swap backends, only `ask_claude()` in `nexus_bot.py` needs to change. Everything else stays identical.

### Security
- Set `YOUR_TELEGRAM_USER_ID` in `.env` — this locks the bot to only you
- Never commit `.env` to GitHub (already gitignored)
- Never share your bot token
- Review every `/act` plan carefully before typing `/confirm`
- The `agent_audit.log` records every browser action taken

### This is a personal tool
NEXUS is designed for one user. It is not multi-tenant. Every person who wants their own NEXUS should deploy their own instance with their own credentials.

---

## Contributing

Pull requests welcome. Ideas:
- WhatsApp bridge via Baileys
- RAG memory layer
- MCP tool integrations
- More opportunity sources (Replit bounties, InnoCentive)
- Voice message support

---

## License

MIT — use it, fork it, build on it.

---

## Author

Built with Claude Code. Inspired by the belief that powerful AI tools should be accessible everywhere — including Lagos.

⭐ Star this if it helped you. Share it if you think others need it.
