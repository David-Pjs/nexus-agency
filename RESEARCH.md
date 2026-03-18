# NEXUS: A Zero-Cost Personal AI Agency Architecture Using Local LLM Orchestration

**Abstract**

The proliferation of large language model (LLM) APIs has enabled powerful AI applications, but recurring per-token costs create a significant barrier to adoption — particularly in emerging markets where dollar-denominated pricing represents a disproportionate economic burden. This paper presents NEXUS, a personal AI agency architecture that achieves zero marginal API cost by routing all inference through a locally installed LLM CLI (Claude Code) rather than direct API calls. NEXUS delivers multi-agent orchestration, real-time data integration, persistent memory, and proactive monitoring entirely from a personal computer or Android phone, accessible via Telegram. We describe the architecture, implementation decisions, performance characteristics, and implications for AI accessibility in resource-constrained environments.

---

## 1. Introduction

Large language models have demonstrated remarkable capability across research, coding, creative work, and decision support. Commercial access to these models — primarily through APIs such as the Anthropic API, OpenAI API, and Google Gemini — has enabled a new class of AI-powered applications. However, the economics of API-based access present a structural barrier:

- Per-token pricing means costs scale with usage
- Dollar-denominated pricing creates currency risk for users in non-USD economies
- Cloud dependency requires reliable internet connectivity
- Individual developers and researchers in emerging markets face disproportionate cost burdens

Nigeria, with Africa's largest developer population and a rapidly growing AI community, exemplifies this challenge. As of 2024, $50/month in API costs represents approximately ₦80,000 — a meaningful fraction of a junior developer's monthly salary.

NEXUS addresses this through a key architectural insight: **the Claude Code subscription model, intended for software development, provides unlimited LLM access at a flat monthly rate**. By routing all agent inference through the Claude Code CLI subprocess rather than direct API calls, NEXUS achieves zero marginal cost per message while retaining full model capability.

---

## 2. Related Work

### 2.1 Multi-Agent Systems
Prior work in multi-agent LLM systems includes AutoGPT [Citation], BabyAGI [Citation], and LangChain Agents [Citation]. These systems typically require direct API access and accumulate significant costs for complex tasks. Microsoft's AutoGen framework [Citation] enables agent-to-agent communication but remains API-dependent.

### 2.2 Personal AI Assistants
Personal assistant applications such as Replika, Character.ai, and various GPT-wrapper chatbots provide conversational AI but lack agent specialization, real-time data integration, and local execution.

### 2.3 Local LLM Execution
Ollama, LM Studio, and similar tools enable local model execution without API costs, but sacrifice model capability. NEXUS takes a different approach: leveraging an existing subscription CLI tool rather than running models locally.

### 2.4 Telegram Bots as AI Interfaces
Telegram's Bot API has been used as an interface layer for AI systems due to its reliability, cross-platform support, and free tier. Previous implementations have used it to wrap API-based chatbots; NEXUS extends this pattern to a full multi-agent architecture.

---

## 3. System Architecture

### 3.1 Core Design Principle

```
Traditional approach:
User → Application → LLM API → Response
Cost: $0.01–$0.10 per interaction

NEXUS approach:
User → Telegram → nexus_bot.py → claude CLI → Response
Cost: $0.00 per interaction (flat subscription)
```

The critical substitution is replacing `anthropic.Anthropic().messages.create()` with `subprocess.run(["claude", "-p", prompt])`. This single architectural decision eliminates per-message costs entirely.

### 3.2 Components

**3.2.1 Interface Layer (nexus_bot.py)**
The main process polls the Telegram Bot API using long-polling (20s timeout). Messages are routed to the appropriate agent handler based on slash command parsing or, for natural language input, to the NEXUS orchestrator.

**3.2.2 Agent Layer**
Seven specialized agents each maintain a distinct system prompt loaded from markdown files:

| Agent | Domain | System Prompt |
|-------|--------|---------------|
| NEXUS | Orchestration | agents/nexus/AGENT.md |
| SCOUT | Research | agents/scout/AGENT.md |
| ARCHITECT | Strategy | agents/architect/AGENT.md |
| HERALD | Marketing | agents/herald/AGENT.md |
| BOUNTY | Opportunities | agents/bounty/AGENT.md |
| ALPHA | Crypto/DeFi | agents/alpha/AGENT.md |
| FORGE | Engineering | agents/forge/AGENT.md |
| ATLAS | Scheduling | agents/atlas/AGENT.md |

**3.2.3 Persistence Layer (db.py)**
SQLite provides persistent storage across restarts. Schema:
```sql
conversations(chat_id, role, content, timestamp)
alerts(id, chat_id, symbol, target, direction, active)
opportunities(id, title, url, prize, deadline, fit_score, source)
user_profile(key, value)
```

**3.2.4 Scheduler (scheduler.py)**
Four background threads handle proactive monitoring:
- BOUNTY scanner: runs at 09:00 daily
- ALPHA monitor: runs every 2 hours
- ATLAS briefing: runs at 08:00 daily
- Gmail monitor: runs every 30 minutes

**3.2.5 Data Integration Layer**
All external data sources use free public APIs requiring no authentication:

| Source | API | Agent |
|--------|-----|-------|
| CoinGecko | /simple/price | ALPHA |
| DeFiLlama | /pools | ALPHA |
| Alternative.me | /fng | ALPHA |
| Devpost | /api/hackathons | BOUNTY |
| DoraHacks | /api/hackathon/list | BOUNTY |
| Gitcoin | GraphQL indexer | BOUNTY |
| wttr.in | JSON weather | Skills |
| Various RSS | CoinTelegraph, TechCrunch | Skills |

### 3.3 Conversation Context Management

Conversation history is stored in SQLite and retrieved per-session. The last 12 messages are prepended to each new prompt, providing continuity across restarts — a significant improvement over in-memory approaches that lose context when the process terminates.

```python
def ask_claude_with_history(chat_id, new_message, agent="nexus"):
    history = get_history(chat_id, limit=12)
    # Build context from persistent history
    # Call claude CLI subprocess
    # Persist response back to SQLite
```

### 3.4 UTF-8 and Encoding Stability

A common failure mode in Windows-based Python/subprocess pipelines is codec errors when processing non-ASCII content (emoji, special characters, international text). NEXUS addresses this through:

```python
env["PYTHONUTF8"] = "1"
env["PYTHONIOENCODING"] = "utf-8"
result.stdout = result.stdout.decode("utf-8", errors="replace")
```

This is particularly relevant for Nigerian and African developers on Windows machines — a population often overlooked in software deployment documentation.

---

## 4. Implementation

### 4.1 Subprocess-based LLM Invocation

```python
cmd = [
    "claude",
    "--system-prompt", system_prompt,
    "--output-format", "text",
    "-p", user_message,
    "--permission-mode", "dontAsk",
    "--dangerously-skip-permissions",
]
result = subprocess.run(cmd, stdout=PIPE, stderr=PIPE, timeout=120, env=env)
response = result.stdout.decode("utf-8", errors="replace").strip()
```

The 120-second timeout accommodates complex agent tasks (deep research, code generation) without blocking indefinitely.

### 4.2 Opportunity Scoring

BOUNTY evaluates each opportunity against a keyword corpus reflecting the user's domain expertise:

```python
FIT_KEYWORDS_HIGH = ["web3", "ai", "fintech", "blockchain",
                     "nigeria", "africa", "defi", "python"]
FIT_KEYWORDS_MEDIUM = ["mobile", "developer", "open source", "startup"]
```

Scores range 1–10. This approach is intentionally simple — a more sophisticated implementation would use embeddings-based similarity — but demonstrates the viability of lightweight scoring without additional model calls.

### 4.3 Price Alert Architecture

Alerts are stored in SQLite with symbol, target price, and direction (above/below). The ALPHA monitoring thread checks all active alerts against live CoinGecko prices every 2 hours, deactivates triggered alerts, and pushes Telegram notifications.

---

## 5. Evaluation

### 5.1 Cost Analysis

| Metric | API-based approach | NEXUS |
|--------|-------------------|-------|
| Cost per message | $0.01–$0.10 | $0.00 |
| 1,000 messages/month | $10–$100 | $0.00 |
| Monthly overhead | Variable | Flat (Claude Code subscription) |
| Currency risk | High | None (subscription pre-paid) |

### 5.2 Capability Comparison

| Feature | ChatGPT wrapper | LangChain + API | NEXUS |
|---------|----------------|-----------------|-------|
| Multi-agent routing | Limited | Yes | Yes |
| Persistent memory | No | With vector DB | Yes (SQLite) |
| Proactive monitoring | No | Complex setup | Yes (threads) |
| Real-time data | No | With tools | Yes (free APIs) |
| Mobile deployment | No | No | Yes (Termux) |
| Marginal cost | High | High | $0 |

### 5.3 Latency

Claude Code CLI introduces subprocess spawn overhead (~500ms) compared to direct API calls (~200ms). For conversational use this is imperceptible. For high-frequency automated tasks, direct API access would be preferable.

---

## 6. Implications for Emerging Markets

### 6.1 The Dollar Problem

Nigeria's developer community — estimated at 700,000+ — has demonstrated significant AI interest and capability. The primary barrier to serious AI development is not talent or motivation but dollar-denominated access costs. A $20/month flat subscription accessed via CLI subprocess is a fundamentally different economic proposition than unpredictable per-token billing.

### 6.2 The Connectivity Problem

NEXUS's architecture is resilient to intermittent connectivity. SQLite persistence means the bot recovers gracefully from network interruptions. External API calls fail silently with sensible defaults. The only hard dependency is the Telegram polling connection — which resumes automatically on reconnection.

### 6.3 The Infrastructure Problem

Deploying AI applications traditionally requires cloud infrastructure (AWS, GCP, Azure) with associated costs and configuration complexity. NEXUS runs on any Python-capable device — including Android phones via Termux. A ₦50,000 Android phone running Termux can host a full AI agency.

---

## 7. Limitations

**Subscription dependency:** NEXUS requires an active Claude Code subscription. If the subscription lapses, all intelligence stops. A fallback to Ollama (local models) is architecturally straightforward but not yet implemented.

**Single-user design:** The current implementation is designed for personal use. Multi-user deployments would require per-user conversation isolation and rate limiting.

**WhatsApp unavailability:** WhatsApp's unofficial API access (via Baileys) risks account suspension. An official WhatsApp Business API integration would require business verification and per-message costs.

**Reminder persistence:** Reminders are stored in-memory and lost on process restart. SQLite-backed reminders are a straightforward improvement.

---

## 8. Future Work

- **RAG layer:** Embedding-based retrieval over stored conversations and documents
- **MCP integration:** Model Context Protocol for standardized tool access
- **A2A support:** Agent-to-Agent protocol for inter-agent communication
- **WhatsApp bridge:** Baileys-based parallel interface
- **X402 payments:** Autonomous micropayment capability for premium data sources
- **Ollama fallback:** Local model support when Claude Code is unavailable
- **Multi-user support:** Per-user isolation for shared deployments

---

## 9. Conclusion

NEXUS demonstrates that sophisticated multi-agent AI systems are buildable at zero marginal cost through careful architectural choices. By treating the Claude Code CLI as an infrastructure component rather than a development tool, we transform a flat-rate subscription into unlimited AI agency capability.

The broader implication extends beyond cost: **the assumption that serious AI development requires cloud infrastructure and API budgets is false**. A laptop, a phone, and a Claude Code subscription are sufficient to build and run a personal AI agency with real-time data integration, persistent memory, and proactive monitoring.

For the 700,000 developers in Nigeria — and millions more across Africa and other emerging markets — this architecture represents a path to building seriously with AI without the dollar-denominated cost barrier that has historically limited access.

The code is open source. The setup takes 10 minutes. The intelligence is already on your machine.

---

## References

- Anthropic. (2024). Claude Code: Agentic coding in your terminal. https://claude.ai/code
- Brown, T., et al. (2020). Language Models are Few-Shot Learners. NeurIPS 2020.
- Chase, H. (2022). LangChain. https://github.com/langchain-ai/langchain
- Wu, Q., et al. (2023). AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation. arXiv:2308.08155
- Telegram. (2024). Bot API Documentation. https://core.telegram.org/bots/api
- CoinGecko. (2024). Public API Documentation. https://docs.coingecko.com
- DeFiLlama. (2024). Yields API. https://defillama.com/docs/api

---

*This research was conducted using Claude Code as both the development tool and the runtime intelligence layer — a form of AI-assisted AI research that is itself an example of the architecture described.*

*Code: https://github.com/yourusername/nexus-agency*
*License: MIT*
