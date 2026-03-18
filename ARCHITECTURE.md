# AI Agency — System Architecture

## Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        YOU (Human)                              │
│              Telegram DM  │  Discord DM/Channel                 │
└──────────────────┬────────┴──────────────────────────────────── ┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                  NEXUS — Orchestrator Agent                     │
│  • Routes your message to the right specialist agent            │
│  • Spawns sub-agents for parallel tasks                         │
│  • Aggregates results back to you                               │
│  Model: Groq / Llama 3.3 70B                                    │
└──┬──────┬──────┬──────┬──────┬──────┬──────┬───────────────────┘
   │      │      │      │      │      │      │
   ▼      ▼      ▼      ▼      ▼      ▼      ▼
┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐
│SCOUT ││ARCH  ││HERALD││BOUNTY││ATLAS ││ALPHA ││FORGE │
│      ││ITECT ││      ││      ││      ││      ││      │
│24/7  ││Biz   ││Mktg  ││Hacks ││Mtgs  ││Web3  ││Code  │
│Rsrch ││Plans ││Copy  ││Grants││Cal   ││DeFi  ││Build │
└──┬───┘└──┬───┘└──┬───┘└──┬───┘└──┬───┘└──┬───┘└──┬───┘
   │       │       │       │       │       │       │
   └───────┴───────┴───┬───┴───────┴───────┴───────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SHARED SKILLS LAYER                          │
│  Browser(Playwright) │ WebSearch │ FileWriter │ GoogleCalendar  │
│  Telegram │ Discord │ Groq API │ Ollama (local fallback)        │
└─────────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                  MONITORING DASHBOARD                           │
│  http://localhost:18789                                         │
│  • Agent status (online/busy/idle)                              │
│  • Task queue per agent                                         │
│  • Token usage & cost tracker                                   │
│  • Error logs & retries                                         │
│  • Scheduled job calendar                                       │
└─────────────────────────────────────────────────────────────────┘
```

## Agent Responsibilities

| Agent    | Trigger Keywords                        | Skills Used                    |
|----------|-----------------------------------------|--------------------------------|
| NEXUS    | anything (router)                       | all                            |
| SCOUT    | research, find, look up, summarize      | browser, web-search, scheduler |
| ARCHITECT| plan, draft, write, proposal, pitch     | file-writer, browser           |
| HERALD   | market, promote, copy, campaign, post   | file-writer, browser           |
| BOUNTY   | hackathon, grant, airdrop, opportunity  | browser, web-search            |
| ATLAS    | meeting, calendar, schedule, remind     | google-calendar                |
| ALPHA    | web3, defi, token, nft, yield, crypto   | browser, web-search            |
| FORGE    | build, code, automate, fix, create      | browser, code-exec             |

## Free Stack

- OpenClaw (MIT license, free)
- Groq API (free tier: 14,400 req/day, Llama 3.3 70B)
- Ollama (local fallback, unlimited, free)
- Telegram Bot API (free)
- Discord Bot API (free)
- Playwright (free)
- Total monthly cost: $0
