# I Built a Personal AI Agency for $20. Here's Exactly How.

**By David Pjs · Lagos, Nigeria**

---

Most people using AI are renting intelligence by the word.

Every message to ChatGPT, every Claude API call, every GPT-4 request costs money. Not a lot per message. But it adds up — and for developers in Nigeria, Ghana, Kenya, and across Africa, dollar-denominated API bills hit differently. $50/month in API costs is ₦80,000. That's real money.

I got tired of it. So I built something different.

I built a personal AI agency that costs $0 per message to run. Seven specialist agents. Live crypto monitoring. Daily hackathon scanning. Google Calendar integration. Image generation. Browser automation. All running from my laptop, all accessible from my phone via Telegram.

This is how I did it — and how you can too.

---

## The Insight That Changes Everything

Most AI applications work like this:

```
Your app → OpenAI/Anthropic API → pay per token → response
```

Every single message costs money. The more you use it, the more you pay.

I noticed something. Claude Code — Anthropic's developer tool for coding — runs as a command-line program on your computer. You call it like this:

```bash
claude -p "your message here"
```

And it responds using your subscription. Flat monthly rate. Unlimited messages.

So instead of calling the API, I call the CLI:

```python
# What everyone else does — costs money every time
response = anthropic.Anthropic().messages.create(...)

# What NEXUS does — costs nothing per message
result = subprocess.run(["claude", "-p", message], ...)
```

That one substitution is the entire economic engine of NEXUS. Everything else is built on top of it.

---

## What I Built

I call it NEXUS. It's a personal AI agency — multiple specialist agents working together, accessible from Telegram, running 24/7 on my machine.

Here's the full roster:

**SCOUT** searches the web live, reads actual pages, and gives me real intelligence reports — not just what Claude knew from training data. Ask it to research a company, a market, a competitor. It goes and finds the current information.

**BOUNTY** wakes up every morning at 9AM, scans Devpost, Gitcoin, DoraHacks, and Superteam Earn for open hackathons and grants. It scores each opportunity 1-10 based on my interests (web3, AI, Nigeria/Africa) and pushes the top results straight to my Telegram. I find out about opportunities before most people know they exist.

**ALPHA** monitors crypto prices every two hours. I set price alerts — "ping me when BTC drops below $65k" — and it does exactly that. It also tracks DeFi yields, shows the Fear and Greed index, and gives me a market snapshot on demand.

**ATLAS** connects to Google Calendar and Gmail. Every morning at 8AM I get my day's schedule without opening a single app. Every 30 minutes it checks my inbox and flags anything urgent.

**FORGE** writes code. ARCHITECT builds business strategies. HERALD writes marketing copy. SCOUT does live research.

And NEXUS itself — the orchestrator — decides which agent to use when I just talk to it naturally. "Find me a hackathon I can win" routes to BOUNTY. "What's happening in DeFi today" goes to ALPHA. "Research my competitor" goes to SCOUT.

---

## The Architecture (Plain English)

Three layers. Simple.

**Layer 1: Telegram**
My phone. I send a message. NEXUS responds. That's it — the interface is an app I already use every day, on the device already in my pocket. No new app to install, no new URL to remember.

**Layer 2: The Bot (Running on My Laptop)**
A Python script that polls Telegram for new messages, routes them to the right agent, calls Claude via CLI subprocess, and sends the response back. It also runs four background threads — the daily BOUNTY scan, the ALPHA price checker, the morning ATLAS briefing, and the Gmail monitor.

**Layer 3: Storage**
SQLite. One file. Stores conversation history (so NEXUS remembers context across restarts), price alerts, opportunities found, and user preferences. No cloud database. No configuration. One file on my hard drive.

The whole thing runs on a ₦350,000 laptop. Or an Android phone with Termux installed.

---

## What It Can Actually Do Right Now

**Browse the web:**
```
/browse https://techcabal.com
```
NEXUS reads the page, summarizes it, extracts what matters.

```
/search Nigeria fintech funding 2025
```
Live DuckDuckGo results. No API key. No cost.

**Act on websites:**
```
/act https://ethglobal.com/events register for this hackathon
```
NEXUS opens the page, reads the form, shows me exactly what it plans to fill in and click — and waits for my approval before doing anything. Full audit log. Screenshots after every action.

**Generate images:**
```
/imagine futuristic Lagos skyline at night with neon lights
```
Real AI-generated image, delivered in Telegram. Free.

**Analyze photos:**
Send any photo to the bot. A chart, a document, a contract, a screenshot. NEXUS reads it and tells you what it says.

**Monitor prices:**
```
/alpha alert BTC 95000 below
```
I get a ping the moment it happens.

**Research anything:**
```
/scout deep tech opportunities for African developers in 2025
```
SCOUT searches the web, reads the top sources, and writes a structured intelligence report with TL;DR, key findings, and recommended actions.

---

## Why This Matters for African Developers

The AI revolution is real. But so is the access gap.

Every major AI tool — GPT-4, Claude API, Gemini Pro — is priced in dollars. When your currency is losing value against the dollar, when a $100 API bill is three weeks of groceries, you don't experiment freely. You don't build boldly. You ration every token.

NEXUS doesn't fix the global economic system. But it demonstrates something important: **the expensive part of AI — the intelligence itself — can be decoupled from per-usage billing.**

A Claude Code subscription at $20/month is a fixed cost. Once you have it, every agent call, every research task, every hackathon scan, every price alert is free. Unlimited usage, known cost, no surprises on your credit card statement.

And the whole system runs on hardware you already own. No AWS. No GCP. No managed databases. No cloud budget. Your laptop — or your Android phone with Termux — is your server.

This isn't just a personal tool. It's an architecture pattern. Any developer can take this and build on it.

---

## What's Coming Next

The current NEXUS is v1. Here's where it goes from here:

**RAG (Retrieval-Augmented Generation)** — NEXUS will store everything it learns in a searchable memory. "What hackathons did you find last month?" will return actual results from its own history, not a guess.

**MCP (Model Context Protocol)** — Anthropic's standard for connecting AI to tools. Instead of writing wrapper code for every API, Claude will call tools directly. Cleaner, faster, more capable.

**A2A (Agent-to-Agent)** — Google's protocol for agents talking to each other. NEXUS could delegate tasks to specialized external agents, aggregate their results, and report back.

**X402 Payments** — The emerging standard for AI agents that can pay for things autonomously. NEXUS could access premium data APIs, pay the tiny fee in crypto, and continue — all without my involvement.

**24/7 deployment** — Right now it runs on my laptop. The next version runs on a small VPS or a Raspberry Pi and never turns off.

---

## The Numbers

| What | Cost |
|------|------|
| Claude Code subscription | $20/month |
| Telegram Bot API | Free |
| CoinGecko prices | Free |
| DeFiLlama yields | Free |
| Devpost/Gitcoin/DoraHacks data | Free |
| Weather (wttr.in) | Free |
| Web search (DuckDuckGo) | Free |
| Image generation (Pollinations) | Free |
| SQLite database | Free |
| Web browsing (Playwright) | Free |
| **Cost per message** | **$0** |
| **Total monthly** | **$20 flat** |

Compare that to running the same capability on APIs: at moderate usage (1,000 messages/month with Claude Opus), you're looking at $100-300/month. Variable. Unpredictable. Scaling with usage.

NEXUS: $20. Always.

---

## Get It

The full code is on GitHub. MIT license. Full setup guide. Works on Windows, Mac, Linux, and Android (Termux).

**github.com/David-Pjs/nexus-agency**

Setup takes about 10 minutes:
1. Clone the repo
2. Get a Telegram bot token from @BotFather
3. Add your token to `.env`
4. Run `python nexus_bot.py`

That's it. Your agency is live.

---

## The Honest Downsides

I'm not going to pretend this is perfect. Here's what you need to know before building it.

**The Terms of Service grey area — this is the big one.**
Claude Code's subscription is designed for interactive developer use. Running it as a 24/7 automated backend via subprocess is not what Anthropic built it for. Some developers have reported account flags or bans for similar patterns. For personal, low-volume use the risk is low — but it is real, and you should know about it.

The fix is straightforward: swap the `ask_claude()` function to use the Anthropic API directly. At personal usage levels (50-100 messages/day) that costs $3-15/month. The entire rest of the architecture stays identical.

**It stops when your laptop stops.**
No VPS means no 24/7. When your machine sleeps, NEXUS sleeps. The 9AM BOUNTY digest only fires if you're running. This is solvable with a cheap VPS or an Android phone running Termux — but it takes extra setup.

**Browser automation is powerful and requires care.**
The `/act` command can fill forms and click buttons on your behalf. It has a confirmation system and audit log, but you are responsible for what you approve. Read every action plan before you type `/confirm`.

**It is a personal tool, not a product.**
NEXUS is locked to one Telegram user ID by design. It is not multi-user. It is not for sharing access with others. Every instance someone builds should be their own, with their own credentials.

**The right alternatives:**
- **Anthropic API directly** — same intelligence, pay per use, no ToS risk
- **Ollama** — fully local, fully free, slightly less capable
- **Groq free tier** — fast, generous limits, no subscription needed

The architecture in this article works with any of these backends. The Claude Code CLI is one implementation, not the only one.

---

## Final Thought

I am a developer in Lagos. I built this in one session, for the cost of a monthly subscription I was already paying.

The intelligence was already on my machine. The phone was already in my pocket. The Telegram account was already active.

The only thing missing was the architecture to connect them.

Now I have an AI agency that finds me opportunities, monitors markets, reads the web, fills forms, and thinks with me — running 24/7, costing nothing extra per message.

If you are a developer anywhere — but especially if you are a developer in Africa navigating dollar-denominated AI costs — this architecture is yours to take, adapt, and build on responsibly.

The code is open. The approach is documented. The risks are disclosed.

The only thing left is to build.

---

*David Pjs is an independent developer based in Lagos, Nigeria.*
*github.com/David-Pjs/nexus-agency*
