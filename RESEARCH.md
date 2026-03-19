# NEXUS: A Zero-Marginal-Cost Personal AI Agency Architecture Using Subscription-Based LLM Orchestration

**David Pjs**
Independent Researcher · Lagos, Nigeria
github.com/David-Pjs/nexus-agency

---

## Abstract

The proliferation of large language model APIs has unlocked powerful AI capabilities, yet per-token pricing creates a structural barrier to adoption - particularly in emerging markets where dollar-denominated costs represent a disproportionate economic burden. This paper presents NEXUS, a personal AI agency architecture that achieves zero marginal inference cost by routing all LLM calls through a locally installed CLI tool (Claude Code) operating under a flat monthly subscription, rather than through direct API access. Built entirely in Python using standard library components, NEXUS delivers multi-agent orchestration, persistent memory, real-time data integration, and proactive background monitoring - accessible via Telegram from any personal computer or Android phone. We describe the system architecture, key implementation decisions, cost analysis, and the broader implications for AI accessibility in resource-constrained environments. NEXUS demonstrates that sophisticated AI agency does not require cloud infrastructure or variable API budgets: a $20/month subscription, a laptop, and a Telegram account are sufficient.

**Keywords:** AI agents, multi-agent systems, LLM orchestration, emerging markets, personal AI, zero-cost inference, Telegram bots, Africa

---

## 1. Introduction

Large language models have demonstrated capability across a wide range of tasks: research, code generation, strategic reasoning, creative work, and decision support. Commercial access to frontier models - via APIs from Anthropic, OpenAI, Google, and others - has enabled a new class of AI-powered applications. However, the dominant API pricing model creates compounding barriers to adoption:

- **Variable cost at scale.** Per-token pricing means costs grow with usage, making experimentation expensive and production unpredictable.
- **Currency asymmetry.** Dollar-denominated pricing imposes exchange rate risk on developers in non-USD economies. A $50/month API budget represents approximately ₦80,000 in Nigeria as of 2024 - a meaningful fraction of a junior developer's monthly salary.
- **Infrastructure dependency.** Most AI agent frameworks assume cloud deployment, adding complexity and cost beyond the model itself.

Nigeria exemplifies this challenge at scale. With an estimated 700,000+ developers and one of Africa's fastest-growing technology sectors, Nigeria's AI community faces structural disadvantage not from lack of talent or ambition, but from the economics of access.

NEXUS addresses this through a single architectural insight: **the Claude Code subscription, designed for software development, provides effectively unlimited LLM access at a flat monthly rate**. By treating the Claude Code CLI as an infrastructure component and invoking it via subprocess rather than through direct API calls, NEXUS eliminates marginal inference costs entirely while retaining full frontier model capability.

The result is a personal AI agency - seven specialist agents, real-time data integrations, persistent SQLite memory, and a background scheduler - running on a personal laptop or Android phone, accessible anywhere via Telegram, at zero cost per interaction.

---

## 2. Related Work

### 2.1 Multi-Agent LLM Systems

Early multi-agent frameworks demonstrated that decomposing tasks across specialist agents improves performance on complex, multi-step problems. AutoGPT [1] and BabyAGI [2] showed that LLMs could iteratively plan and execute goals autonomously. LangChain [3] provided abstractions for chaining LLM calls with tool use. Microsoft's AutoGen [4] formalized agent-to-agent communication protocols. These systems share a common dependency: direct, paid API access. Cost accumulates rapidly for long-horizon tasks, limiting practical use for individual developers without institutional budgets.

### 2.2 Personal AI Assistants

Consumer AI products (Replika, Character.ai, various GPT wrappers) provide conversational AI but lack agent specialization, tool integration, and local execution. They optimize for user retention rather than user capability. Productivity-focused products (Notion AI, GitHub Copilot) are domain-specific and cloud-dependent.

### 2.3 Local LLM Execution

Ollama, LM Studio, and llama.cpp enable fully local model execution with zero ongoing costs. The tradeoff is capability: locally runnable models remain significantly behind frontier models on complex reasoning, research, and code generation tasks. NEXUS takes a distinct approach - it retains frontier model capability by leveraging an existing subscription rather than running degraded models locally.

### 2.4 Telegram as AI Interface

Telegram's Bot API has been used as a lightweight interface for AI systems due to its cross-platform support, reliability, and free tier. Previous implementations have wrapped API-based chatbots in Telegram interfaces. NEXUS extends this pattern to a full multi-agent architecture with persistent state and background automation - demonstrating that Telegram is viable not just as a chat interface but as a complete AI agency control surface.

### 2.5 Positioning

NEXUS occupies a gap between fully local models (free but limited) and cloud-hosted API agents (capable but expensive). It achieves frontier capability at flat cost by exploiting the economics of developer tool subscriptions - an approach not previously documented in the literature.

---

## 3. System Architecture

### 3.1 Core Design Principle

The fundamental substitution that enables zero marginal cost is replacing direct API invocation with CLI subprocess invocation:

```
Standard approach:
User → Agent Framework → Anthropic API → pay($0.01–$0.10/msg)

NEXUS approach:
User → nexus_bot.py → claude CLI subprocess → pay($0.00/msg)
```

In code, this replaces:
```python
# Standard: billed per token
client = anthropic.Anthropic()
response = client.messages.create(model="claude-opus-4-6", ...)
```

With:
```python
# NEXUS: flat subscription, zero marginal cost
result = subprocess.run(
    ["claude", "--system-prompt", prompt, "-p", message],
    stdout=PIPE, stderr=PIPE, env=env, timeout=120
)
```

This single substitution is the architecture. Everything else - agents, scheduler, persistence, integrations - is built on top of it.

### 3.2 System Components

**Figure 1: NEXUS Architecture**
```
┌─────────────────────────────────────────────────────────┐
│                    User Interface                        │
│                   Telegram Bot API                       │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│                   nexus_bot.py                          │
│              Message Router + Command Handler            │
└────┬──────────┬──────────┬──────────┬──────────┬────────┘
     │          │          │          │          │
  BOUNTY     ALPHA      ATLAS      SCOUT      FORGE ...
  Agent      Agent      Agent      Agent      Agent
     │          │          │          │          │
     └──────────┴──────────┴──────────┴──────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│                  Claude Code CLI                         │
│         Local inference · Flat subscription             │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│                    SQLite (nexus.db)                     │
│      conversations · alerts · opportunities · profile    │
└─────────────────────────────────────────────────────────┘

Background Scheduler (daemon threads):
  BOUNTY scanner  ──── 09:00 daily
  ALPHA monitor   ──── every 2 hours
  ATLAS briefing  ──── 08:00 daily
  Gmail monitor   ──── every 30 minutes
```

#### 3.2.1 Interface Layer

`nexus_bot.py` polls the Telegram Bot API using long-polling (20s timeout). Incoming messages are parsed by a regex-based router. Slash commands route to specific agent handlers; natural language routes to the NEXUS orchestrator, which selects the appropriate specialist agent.

#### 3.2.2 Agent Layer

Eight agents each maintain a distinct system prompt loaded from Markdown files at startup:

| Agent | Domain | Primary Commands |
|-------|--------|-----------------|
| NEXUS | Orchestration | _(natural language)_ |
| SCOUT | Research & Intelligence | `/scout [topic]` |
| ARCHITECT | Strategy & Planning | `/architect [task]` |
| HERALD | Marketing & Content | `/herald [task]` |
| BOUNTY | Opportunities & Grants | `/bounty` |
| ALPHA | Crypto & DeFi | `/alpha` |
| ATLAS | Calendar & Email | `/atlas today` |
| FORGE | Code & Engineering | `/forge [task]` |

Each agent call passes its domain-specific system prompt to the Claude CLI, enabling context-appropriate responses without a separate model per agent.

#### 3.2.3 Persistence Layer

SQLite provides zero-dependency persistent storage with the following schema:

```sql
conversations(id, chat_id, role, content, timestamp)
alerts(id, chat_id, type, symbol, target, direction, active, created_at)
opportunities(id, title, url, prize, deadline, fit_score, source, seen_at, notified)
user_profile(key, value)
```

Conversation history is retrieved per session (last 12 messages) and prepended to each new prompt, providing continuity across process restarts. This is a meaningful improvement over in-memory approaches, which lose context whenever the bot stops.

#### 3.2.4 Scheduler

Four daemon threads run background jobs independently of the main polling loop:

```python
Thread: bounty_scanner  → _wait_until_hour(9),  run daily
Thread: alpha_monitor   → time.sleep(7200),      run every 2h
Thread: atlas_briefing  → _wait_until_hour(8),   run daily
Thread: gmail_monitor   → time.sleep(1800),       run every 30min
```

All threads write results to SQLite and push to Telegram via the shared `send_message()` function.

#### 3.2.5 Data Integration

All external data sources use free, unauthenticated public APIs:

| Source | Endpoint | Consumer |
|--------|----------|----------|
| CoinGecko | `/simple/price` | ALPHA prices |
| DeFiLlama | `/pools` | ALPHA yields |
| Alternative.me | `/fng` | Fear & Greed index |
| Devpost | `/api/hackathons` | BOUNTY scanner |
| DoraHacks | `/api/hackathon/list` | BOUNTY scanner |
| Gitcoin | GraphQL indexer | BOUNTY scanner |
| Superteam Earn | RSS feed | BOUNTY scanner |
| wttr.in | JSON format | Weather skill |
| CoinTelegraph RSS | RSS feed | News skill |

Zero additional API costs. Zero authentication overhead.

### 3.3 Opportunity Scoring

BOUNTY evaluates each opportunity against a keyword corpus tuned to the user's domain:

```python
FIT_KEYWORDS_HIGH   = ["web3", "ai", "fintech", "blockchain",
                        "nigeria", "africa", "defi", "python"]
FIT_KEYWORDS_MEDIUM = ["mobile", "developer", "open source", "startup"]
```

Scores range 1–10. New opportunities are deduplicated by URL in SQLite and ranked by fit score before delivery. This intentionally simple approach avoids additional model calls - a more sophisticated implementation could use embedding-based semantic similarity, at the cost of added complexity and latency.

### 3.4 Encoding Stability on Windows

A common and underdocumented failure mode in Python/subprocess pipelines on Windows is codec errors when processing non-ASCII content - emoji, special characters, international text. This manifests as `UnicodeDecodeError` crashes that terminate the bot process. NEXUS addresses this explicitly:

```python
env["PYTHONUTF8"] = "1"
env["PYTHONIOENCODING"] = "utf-8"
stdout = result.stdout.decode("utf-8", errors="replace")
```

This detail is particularly relevant for developers on Windows machines in Nigeria and across Africa - a population systematically underrepresented in deployment documentation written for macOS/Linux environments.

---

## 4. Implementation

### 4.1 Subprocess Invocation

```python
cmd = [
    "claude",
    "--system-prompt", system_prompt,
    "--output-format", "text",
    "-p", user_message,
    "--permission-mode", "dontAsk",
    "--dangerously-skip-permissions",
]
result = subprocess.run(
    cmd,
    stdout=PIPE, stderr=PIPE,
    timeout=120, env=env, cwd=base_dir
)
response = result.stdout.decode("utf-8", errors="replace").strip()
```

The 120-second timeout accommodates complex agent tasks - deep research, multi-step code generation - without blocking indefinitely. Exponential backoff (capped at 30s) handles transient network failures in the polling loop.

### 4.2 Context Management

```python
def ask_claude_with_history(chat_id, new_message, agent="nexus"):
    history = get_history(chat_id, limit=12)     # from SQLite
    system_prompt = AGENT_PROMPTS[agent]

    if history:
        context = "[Conversation so far:]\n"
        context += "\n".join(f"{h['role']}: {h['content'][:400]}"
                             for h in history)
        prompt = context + f"\n[New message:]\n{new_message}"
    else:
        prompt = new_message

    response = ask_claude(prompt, system_prompt)
    save_message(chat_id, "user", new_message)      # persist
    save_message(chat_id, "assistant", response)    # persist
    return response
```

### 4.3 Process Integrity

A PID file prevents duplicate bot instances - a common failure mode when the bot is restarted without cleanly terminating the previous process:

```python
def _acquire_pid():
    if os.path.exists(PID_FILE):
        old_pid = int(open(PID_FILE).read())
        if psutil.pid_exists(old_pid):
            sys.exit(1)  # already running
    open(PID_FILE, "w").write(str(os.getpid()))
```

---

## 5. Evaluation

### 5.1 Cost Analysis

| Metric | API-based | NEXUS |
|--------|-----------|-------|
| Cost per message | $0.01–$0.10 | $0.00 |
| 1,000 messages/month | $10–$100 | $0.00 |
| 10,000 messages/month | $100–$1,000 | $0.00 |
| Monthly overhead | Unpredictable | $20 flat |
| Currency risk | High | None (pre-paid) |
| Cost in NGN (approx.) | ₦8k–₦80k variable | ₦32k fixed |

The zero-marginal-cost property means experimental use, debugging, and heavy daily use all cost the same. This is qualitatively different from API pricing, which creates psychological friction around usage.

### 5.2 Capability Comparison

| Feature | ChatGPT wrapper | LangChain + API | NEXUS |
|---------|----------------|-----------------|-------|
| Multi-agent routing | Limited | Yes | Yes |
| Persistent memory | No | Requires vector DB | Yes (SQLite) |
| Proactive monitoring | No | Complex | Yes (threads) |
| Real-time data | No | With plugins | Yes (free APIs) |
| Mobile deployment | No | No | Yes (Termux) |
| Setup complexity | Low | High | Low |
| Marginal inference cost | High | High | $0 |

### 5.3 Latency

Claude Code CLI introduces subprocess spawn overhead of approximately 400–600ms compared to direct API calls (~150–250ms). For conversational interactions, this is imperceptible. The tradeoff - ~300ms additional latency in exchange for zero marginal cost - is strongly favorable for personal use cases.

### 5.4 Live Test Results

On initial deployment, a single BOUNTY scan retrieved **20 verified open hackathons** from Devpost within 15 seconds. ALPHA successfully retrieved live prices for BTC ($71,881), ETH ($2,221), and SOL ($89.87) with 24-hour change data. The Fear & Greed index returned a score of 26 (Fear). All results delivered to Telegram with formatted output including progress bars and structured cards.

---

## 6. Implications for Emerging Markets

### 6.1 The Dollar Problem

The dominant framing of AI accessibility focuses on model capability and dataset diversity. Less discussed is the economic structure of access itself. Per-token API pricing, denominated in USD, creates a compounding disadvantage for developers in naira, cedis, shillings, and other currencies experiencing ongoing depreciation against the dollar.

NEXUS reframes this: the correct unit of AI access is not tokens but **subscriptions**. A fixed monthly subscription, paid once, converts infinite usage into a known cost. For a developer in Lagos earning ₦300,000/month, ₦32,000 for unlimited AI agency is a different decision than ₦80,000+ in unpredictable API bills.

### 6.2 The Connectivity Problem

NEXUS is architecturally resilient to intermittent connectivity. SQLite writes are local and synchronous. External API calls fail silently with cached or default responses. The Telegram polling connection reconnects automatically. The bot continues serving cached data when external APIs are unavailable.

This matters in environments where bandwidth is expensive, connections drop, and VPN usage is common.

### 6.3 The Infrastructure Problem

Deploying AI applications traditionally implies cloud infrastructure: virtual machines, container orchestration, managed databases, load balancers. Each adds cost and configuration complexity that creates a high floor for serious AI development.

NEXUS requires: Python, a terminal, and an internet connection. It runs on a ₦50,000 Android phone via Termux. It runs on a five-year-old laptop. It requires no cloud account, no credit card for infrastructure, no DevOps knowledge.

The infrastructure is already in the developer's pocket.

---

## 7. Limitations

**Subscription dependency.** NEXUS requires an active Claude Code subscription. If the subscription lapses, all intelligence stops. Mitigation: an Ollama fallback is architecturally straightforward - replace the `subprocess.run(["claude", ...])` call with an HTTP request to a local Ollama instance.

**Single-process design.** The current implementation runs all agents in a single Python process. High message volume could cause latency as Claude CLI calls are synchronous. Mitigation: a thread pool for concurrent agent execution is a straightforward upgrade.

**Reminder persistence.** Reminders are held in-memory and lost on process restart. Mitigation: a `reminders` table in SQLite with a polling thread is a one-session addition.

**Single-user design.** Per-user conversation isolation exists; however, shared deployments would require per-user rate limiting and access control. Not a limitation for personal use.

**WhatsApp.** Unofficial WhatsApp API access via Baileys carries account suspension risk. Official WhatsApp Business API requires business verification and per-message fees - reintroducing the cost structure NEXUS eliminates.

---

## 8. Future Work

- **RAG memory layer.** Embedding-based retrieval over stored conversations and documents. Allows NEXUS to answer "what opportunities did you find last month?" from its own history.
- **MCP integration.** Model Context Protocol provides standardized tool access, allowing Claude to directly invoke APIs mid-conversation without wrapper code.
- **A2A support.** Google's Agent-to-Agent protocol enables inter-agent communication and delegation to external agents.
- **Ollama fallback.** Local model inference when Claude Code subscription is unavailable or for cost-sensitive deployments.
- **X402 micropayments.** Autonomous payment capability for premium data APIs, enabling NEXUS to access paid data sources within a user-defined budget.
- **Multi-user deployment.** Per-user isolation enabling NEXUS to serve a small team from a single instance.
- **Voice interface.** WhatsApp/Telegram voice note transcription and audio response.

---

## 9. Conclusion

NEXUS demonstrates that sophisticated multi-agent AI systems are buildable at zero marginal cost through a single architectural decision: substituting API calls with CLI subprocess invocation against an existing flat-rate subscription.

The broader claim is stronger than a cost optimization. **The assumption that serious AI development requires cloud infrastructure and variable API budgets is false.** A personal computer, a $20/month subscription, and a Telegram bot token are sufficient to build and run an AI agency with real-time data integration, persistent memory, specialist agents, and proactive background automation.

For Nigeria's 700,000 developers - and for the millions of builders across Africa, Southeast Asia, Latin America, and Eastern Europe navigating dollar-denominated AI access costs - this architecture represents a replicable path to building seriously with frontier AI without the financial overhead that has historically limited access to those already inside well-funded organizations.

The intelligence is already available. The subscription already exists for many developers using Claude Code for software development. The marginal cost of turning that subscription into a full personal AI agency is the afternoon it takes to build it.

The code is available at: **github.com/David-Pjs/nexus-agency**

---

## References

[1] Richards, T. (2023). *AutoGPT: An Autonomous GPT-4 Experiment.* GitHub. https://github.com/Significant-Gravitas/AutoGPT

[2] Nakajima, Y. (2023). *BabyAGI.* GitHub. https://github.com/yoheinakajima/babyagi

[3] Chase, H. (2022). *LangChain: Building applications with LLMs through composability.* GitHub. https://github.com/langchain-ai/langchain

[4] Wu, Q., Bansal, G., Zhang, J., et al. (2023). *AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation.* arXiv:2308.08155.

[5] Anthropic. (2024). *Claude Code: Agentic coding in your terminal.* https://claude.ai/code

[6] Telegram. (2024). *Bot API Documentation.* https://core.telegram.org/bots/api

[7] CoinGecko. (2024). *Public API Documentation.* https://docs.coingecko.com

[8] DeFiLlama. (2024). *Yields API.* https://defillama.com/docs/api

[9] Brown, T., Mann, B., Ryder, N., et al. (2020). *Language Models are Few-Shot Learners.* NeurIPS 2020. arXiv:2005.14165.

[10] Significant-Gravitas. (2023). *The real cost of AI agents.* Internal analysis referenced in AutoGPT documentation.

---

*This paper was written using Claude Code as both the primary development tool and the runtime intelligence layer of the system described - a form of AI-assisted systems research that is itself an instance of the architecture under study.*

*Source code:* github.com/David-Pjs/nexus-agency
*License:* MIT
*Contact:* github.com/David-Pjs
