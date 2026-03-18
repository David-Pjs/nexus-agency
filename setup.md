# Agency Setup Guide — Do This In Order

## STEP 1 — Install OpenClaw (run in terminal)

```bash
# Windows PowerShell (run as admin)
iwr -useb https://openclaw.ai/install.ps1 | iex

# OR with npm directly
npm install -g openclaw@latest
```

Verify:
```bash
openclaw --version
```

---

## STEP 2 — Get Your Free Groq API Key

1. Go to https://console.groq.com
2. Sign up (free, no credit card)
3. Click "Create API Key"
4. Copy the key
5. Paste it in `.env` file → `GROQ_API_KEY=your_key_here`

Free tier: Llama 3.3 70B, 14,400 requests/day

---

## STEP 3 — Create Telegram Bot

1. Open Telegram, search `@BotFather`
2. Send `/newbot`
3. Give it a name: `My Agency`
4. Give it a username: `myagency_bot` (must end in _bot)
5. Copy the token BotFather gives you
6. Paste in `.env` → `TELEGRAM_BOT_TOKEN=your_token`

Get your user ID:
1. Search `@userinfobot` on Telegram
2. Send `/start`
3. Copy your ID → paste in `.env` → `YOUR_TELEGRAM_USER_ID=your_id`

---

## STEP 4 — Create Discord Bot

1. Go to https://discord.com/developers/applications
2. Click "New Application" → name it "Agency"
3. Go to "Bot" tab → "Add Bot"
4. Copy token → paste in `.env` → `DISCORD_BOT_TOKEN=your_token`
5. Go to OAuth2 → URL Generator → check: bot, applications.commands
6. Bot Permissions: Send Messages, Read Messages, Use Slash Commands
7. Copy the generated URL → open it → add bot to your server
8. Get server ID: right-click your server → Copy Server ID
9. Paste in `.env` → `YOUR_DISCORD_SERVER_ID=your_id`

---

## STEP 5 — Copy Config to OpenClaw Home

```bash
# Copy config
cp agency/openclaw.json ~/.openclaw/openclaw.json

# Load env vars
cp agency/.env ~/.openclaw/.env
```

---

## STEP 6 — Start OpenClaw

```bash
openclaw onboard --install-daemon
openclaw channels login
openclaw gateway start
```

Open dashboard: http://localhost:18789

---

## STEP 7 — (Optional) Install Ollama for Local Fallback

```bash
# Download from https://ollama.com
# Then pull a model:
ollama pull llama3.3
```

---

## Project Structure

```
agency/
├── .env                    ← your API keys (never commit this)
├── openclaw.json           ← main config (all 8 agents)
├── ARCHITECTURE.md         ← full system diagram
├── setup.md                ← this file
└── agents/
    ├── nexus/AGENT.md      ← orchestrator instructions
    ├── scout/AGENT.md      ← research agent
    ├── architect/AGENT.md  ← business plans
    ├── herald/AGENT.md     ← marketing
    ├── bounty/AGENT.md     ← opportunities
    ├── atlas/AGENT.md      ← meetings/calendar
    ├── alpha/AGENT.md      ← web3 intelligence
    └── forge/AGENT.md      ← code/build
```
