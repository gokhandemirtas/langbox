# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Instructions for Claude Code

**IMPORTANT - MCP Server Status Check**: At the start of every Claude Code session:
1. **Check if the MCP server is available** by attempting to use any MCP tool (e.g., `mcp__langbox-mongodb__list_collections`)
2. **Notify the user** of the MCP server status:
   - If available: Inform the user that the MCP server is connected and ready
   - If unavailable: Inform the user that the MCP server is not available and they may need to restart Claude Code or check the configuration
3. This check should be done proactively at session start, not when the user first requests database access

**IMPORTANT - Database Access**: When the user asks questions about data in MongoDB:
1. **ALWAYS use the MCP server tools** (prefixed with `mcp__langbox-mongodb__`) to query the database
2. **DO NOT** use bash commands like `docker exec` or `mongosh` to access the database
3. **ASSUME** MongoDB is running and available — the MCP server will handle connection issues

**IMPORTANT**: When uncertain about library versions or APIs:
1. **Always check `pyproject.toml`** for dependency versions before making assumptions
2. Use the version to look up correct API docs or make informed decisions about available features

## Project Overview

Langbox is a reliable, locally-run personal assistant using GGUF model inference (llama-cpp-python), structured output generation (outlines), and a modular skill architecture. Designed for predictability over agentic unpredictability — the LLM classifies intent, Python orchestrates execution.

The core reliability principle: **outlines-constrained generation** is used throughout. The LLM can only output values conforming to a Pydantic schema, making intent classification and sub-classification structurally reliable where free-form tool calling is not.

## Development Setup

```bash
uv sync
cp .env.template .env   # fill in your values
cd db && docker-compose up -d
uv run python main.py
uv run python main.py --debug      # debug logging
```

## Architecture

### Request Flow

```
User input (CLI or Telegram)
  → intent_classifier.py    outlines constrains to IntentResponse.intent
  → router.py               SKILL_MAP lookup → skill.handle(query)
  → skill handler           returns raw data string
  → handle_conversation()   wraps into natural language (if needs_wrapping=True)
  → response logged + returned
```

### Intent Classification

`agents/intent_classifier.py`:
- Prepends last 4 conversation exchanges AND current topic (`## Current topic:`) for follow-up awareness
- Calls `generate_structured_output()` with `IntentResponse` — outlines guarantees a valid intent literal
- `IntentResponse.intent` is a single `Literal[...]` — one intent per query
- Displays a "tinkering" Rich spinner while the LLM runs
- Returns the response string (used by both CLI and Telegram)
- On Ctrl+C, `cmd_save()` is called before exit to persist the session summary

Valid intents: `HOME_CONTROL`, `WEATHER`, `FINANCE_STOCKS`, `TRANSPORTATION`, `REMINDER`, `NEWSFEED`, `INFORMATION_QUERY`, `SEARCH`, `CHAT`

**Follow-up rule (highest priority)**: If a `## Recent conversation` section is present and the query references it, always classify as `CHAT`. Action requests following a domain response ("add to my watchlist", "save this", "track this") are always CHAT follow-ups, not new domain intents.

**Out-of-domain physical requests** ("fry an egg", "make me coffee", "drive me somewhere") → always `CHAT` so the persona can respond playfully.

### Router

`agents/router.py`:
- Looks up skill in `SKILL_MAP` by intent string
- For `SEARCH` and `INFORMATION_QUERY`: enriches short follow-up queries (≤6 words) by appending `_current_topic` so "a jamie oliver recipe" becomes "a jamie oliver recipe egg recipe"
- Calls `skill.handle(query=query)` (async or sync)
- If `skill.needs_wrapping=True` → passes raw response to `handle_conversation()`
- Falls back to `CHAT` for unrecognised intents

### Skill Dataclass (`skills/base.py`)

```python
@dataclass
class Skill:
    id: str                    # intent name, e.g. "WEATHER"
    description: str           # one-liner for intent classification prompt
    system_prompt: Optional[str]  # sub-classification prompt (None if unused)
    handle: Callable           # handle(query: str) -> str
    needs_wrapping: bool = True
```

Skills with `needs_wrapping=True` return raw data strings — `handle_conversation()` converts them to natural language. Skills with `needs_wrapping=False` return the final user-facing text directly (e.g. CHAT).

### Skill Registry (`skills/registry.py`)

- `SKILLS: list[Skill]` — all registered skills
- `SKILL_MAP: dict[str, Skill]` — keyed by `skill.id`

### Registered Skills

| Intent | Directory | Key files |
|---|---|---|
| `WEATHER` | `skills/weather/` | `skill.py`, `weather_client.py` (Open-Meteo, no key) |
| `FINANCE_STOCKS` | `skills/finance/` | `skill.py`, `prompts.py` (yfinance + fuzzy ticker resolution) |
| `HOME_CONTROL` | `skills/home_control/` | `skill.py`, `hue_client.py` (Philips Hue) |
| `REMINDER` | `skills/reminder/` | `skill.py`, `create.py`, `list.py`, `timer.py`, `parser.py` |
| `NEWSFEED` | `skills/newsfeed/` | `skill.py` (RSS feeds) |
| `SEARCH` | `skills/search/` | `skill.py` (DuckDuckGo via `ddgs`) |
| `TRANSPORTATION` | `skills/transportation/` | `skill.py`, `ors_client.py`, `prompts.py` (OpenRouteService) |
| `INFORMATION_QUERY` | `skills/information/` | `skill.py`, `prompts.py` (Wikipedia) |
| `CHAT` | `skills/conversation/` | `skill.py` — also handles post-processing for all other skills |

### Conversation Skill (`skills/conversation/skill.py`)

Handles two roles:
- `handle_chat(query)` — CHAT intent; serialises rolling history into a single prompt, calls `generate_structured_output()` with `_ChatResponse(topic, answer)`
- `handle_conversation(query, handler_response)` — wraps raw skill output into natural language, calls `generate_structured_output()` with `_ConversationResponse(topic, answer)`
- Both functions update `_current_topic` from the structured output result in the same inference pass — no separate call needed
- `get_recent_history(n)` — used by the intent classifier to prepend context
- `get_current_topic()` — returns the active topic label; used by the intent classifier and router

**Topic tracking**: after every exchange (skill or chat), a 3–5 word topic label (e.g. `"Tesla Q4 earnings"`, `"weather in London"`) is stored in `_current_topic`. This is injected into the classifier prompt as `## Current topic:` so follow-up queries resolve correctly even when vague.

**Rolling history**: `_history` deque (max 20 messages). When near capacity, the oldest half is compressed into `_rolling_summary` by the LLM and injected into the system prompt.

### ReAct Reasoning Engine (`skills/conversation/reasoning_engine.py`)

Triggered from `handle_chat` when `should_use_reasoning()` returns `True`.

`should_use_reasoning` only activates for queries that genuinely need an external lookup — specifically pronoun+question-word combos (`"how tall is he"`, `"where is she from"`) or comparison keywords (`"vs"`, `"taller"`, `"bigger"`). Short conversational follow-ups (`"what was that?"`, `"tell me more"`) stay on the standard CHAT path.

ReAct loop rules:
- If the answer is already in conversation history or observations → `RESPOND` immediately
- If the query asks the assistant to clarify something it already said → `RESPOND` from context
- After 2+ observations, strongly prefer `RESPOND` rather than looping further
- Max steps: 5 (safety cap)

### Background Services (not in SKILL_MAP)

- **`skills/telegram/`** — Telegram bot, started automatically on boot if `TELEGRAM_BOT_TOKEN` is set. Routes messages through `run_intent_classifier()`. `@planner <task>` invokes the planner. Responses capped at 4096 chars (summarised if longer).
- **`skills/camera_tracking/`** — Face detection + emotion recognition in a background thread. Started with `--track_camera` flag.
- **`skills/personalizer/`** — Persona analysis from conversation history. Currently disabled (commented out in `main.py`).

### Planner (`skills/planner/`)

Invoked via `/planner <task>` (CLI) or `@planner <task>` (Telegram).

Outlines-based autonomous loop — **not** LangGraph tool calling (unreliable with local models):
1. `generate_structured_output()` with `PlannerAction` schema selects next tool + query
2. Python calls `SKILL_MAP[tool].handle(query)` directly
3. Results accumulate in a `steps` list (up to `MAX_STEPS = 10`)
4. Loop exits when model outputs `tool="DONE"` or step limit reached
5. LLM synthesises final plan from all collected results
6. Plan saved to `Plans` MongoDB collection
7. In-memory state cleared (fresh start for next call)

`HOME_CONTROL` is excluded from planner tools (real-world side effects).
Only one planner can run at a time (`asyncio.Lock`).

### Structured Output (`utils/llm_structured_output.py`)

`generate_structured_output(model_name, user_prompt, system_prompt, pydantic_model, ...)`:
- Integrates directly with llama.cpp via `outlines.from_llamacpp()`
- Creates a fresh model instance per call (no context contamination)
- Falls back to `json_repair` if outlines returns a string instead of parsed model
- Used by: intent classifier, finance sub-classifier, weather sub-classifier, home control sub-classifier, transportation sub-classifier, planner tool selector

Skill-specific Pydantic types are defined **inline in `skill.py`**, not in separate files.

Now also used by the conversation skill — `_ConversationResponse` and `_ChatResponse` both include a `topic` field alongside `answer`, so topic extraction has zero extra latency.

Shared types in `pydantic_types/`:
- `intent_response.py` — `IntentResponse` with `IntentLiteral` type alias
- `credentials.py` — `Credentials`

### Finance Skill — Ticker Resolution

`skills/finance/skill.py` uses a two-stage approach to handle 600+ tickers:
1. `_find_candidates(query, n=15)` — fast fuzzy pre-filter using `difflib` + substring matching
2. Only the top 15 candidates are injected into the LLM prompt (avoids context overflow)

Tickers are stored in `fixtures/tickers.json`. Refresh with:
```bash
uv run python scripts/update_tickers.py  # pulls S&P 500 + FTSE 100 from Wikipedia
```

### Transportation Skill

`skills/transportation/` uses OpenRouteService (free, 2000 req/day):
- Defaults: `origin="London"`, `mode="public-transport"`
- Sub-classifies query with outlines to extract origin, destination, mode
- Geocodes both locations, fetches turn-by-turn directions
- Requires `ORS_API_KEY` in `.env`

### Agent Persona (`agents/persona.py`)

Central identity for the assistant. Imported by all skills and commands that need to establish who AIDA is.

- `AGENT_NAME` — `"AIDA"`
- `AGENT_IDENTITY` — one-line identity string, prefixes all system prompts
- `AGENT_PREAMBLE` — full preamble used by `handle_chat`, includes:
  - What AIDA **can** do (weather, stocks, home control, reminders, news, search, Wikipedia, directions, conversation)
  - What AIDA **cannot** do (no physical form, no email/calls, no arbitrary web browsing)
  - Roleplay instruction: never flatly refuse out-of-capability requests — acknowledge briefly, then play along, describe vividly, or make a joke

### Agent Factory (`agents/agent_factory.py`)

- `create_llm(...)` — creates and caches `ChatLlamaCpp` instances (keyed by all params)
- `create_llm_agent(...)` — wraps `create_llm()` in a LangGraph agent (used by finance comment step)
- The `Llama` instance is shared between `create_llm()` and `generate_structured_output()` via `_get_or_load_llama()`

### Database (`db/`)

MongoDB 7 via Docker Compose. Beanie ODM with `AsyncMongoClient`.

Schemas in `db/schemas.py`:

| Document | Key fields |
|---|---|
| `Conversations` | `datestamp`, `question`, `answer`, `raw` |
| `Plans` | `created_at`, `ask`, `plan` |
| `Reminders` | `reminder_datetime`, `description`, `is_completed` |
| `Weather` | `datestamp`, `location`, `current_temperature`, `forecast` |
| `Newsfeed` | `datestamp`, `content` |
| `Credentials` | `hueUsername` |
| `HueConfiguration` | `groups`, `lights`, `lastUpdated` |
| `UserPersona` | persona analysis fields (disabled) |

All schemas must be registered in `db/init.py` `collections` list.

## Project Structure

```
langbox/
├── agents/
│   ├── intent_classifier.py     # outlines classification + routing trigger
│   ├── router.py                # SKILL_MAP dispatch + query enrichment + needs_wrapping logic
│   ├── agent_factory.py         # ChatLlamaCpp cache + LangGraph agent factory
│   └── persona.py               # AIDA identity, capabilities, and roleplay instructions
├── skills/
│   ├── base.py                  # Skill dataclass
│   ├── registry.py              # SKILLS list + SKILL_MAP dict
│   ├── conversation/            # CHAT intent + handle_conversation() wrapper + ReAct engine
│   ├── weather/                 # Open-Meteo forecast
│   ├── finance/                 # yfinance + fuzzy ticker resolution
│   ├── home_control/            # Philips Hue
│   ├── reminder/                # Reminders + timers
│   ├── newsfeed/                # RSS feeds
│   ├── search/                  # DuckDuckGo
│   ├── transportation/          # OpenRouteService directions
│   ├── information/             # Wikipedia
│   ├── planner/                 # Outlines-based autonomous planning loop
│   ├── telegram/                # Telegram bot background service
│   ├── camera_tracking/         # Face detection background thread
│   └── personalizer/            # Persona analysis (disabled)
├── pydantic_types/
│   ├── intent_response.py       # IntentLiteral + IntentResponse
│   └── credentials.py
├── utils/
│   ├── llm_structured_output.py # outlines + llama.cpp constrained generation
│   ├── http_client.py           # aiohttp async client
│   ├── resource_monitor.py      # VRAM/RAM background monitor
│   └── log.py                   # central logger; also writes to /tmp/langbox_debug.log
├── db/
│   ├── schemas.py               # Beanie document models
│   ├── init.py                  # init_beanie() called at startup
│   └── docker-compose.yml
├── scripts/
│   └── update_tickers.py        # Refresh fixtures/tickers.json
├── fixtures/
│   └── tickers.json             # 600+ stock tickers (S&P 500 + FTSE 100)
├── tts/
│   └── tts.py                   # speak() for --speak flag
├── mcp-server/mongodb/          # Node.js MCP server for Claude Code DB access
├── .config/claude-code/mcp.json # MCP server config
├── models/                      # GGUF files (not in git)
├── main.py                      # Entry point + CLI loop
├── daily_routines.py            # Daily briefing
├── commands.py                  # /save /clear /history /planner /help
├── .env                         # Secrets (not in git)
└── pyproject.toml
```

## Adding a New Skill

1. Create `skills/<name>/skill.py` with `async def handle_<name>(query: str) -> str`
2. Export `skill = Skill(...)` from `skills/<name>/__init__.py`
3. Add to `SKILLS` list in `skills/registry.py`
4. Add literal to `IntentLiteral` in `pydantic_types/intent_response.py`
5. Add intent category + examples to `_INTENT_PROMPT` in `agents/intent_classifier.py`
6. Optionally add `prompts.py` for sub-classification

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `MODEL_GENERALIST` | Yes | GGUF filename (relative to `MODEL_PATH`) |
| `MODEL_PATH` | Yes | Models directory |
| `MONGODB_HOST/PORT/USER/PASSWORD/DB` | Yes | MongoDB connection |
| `TELEGRAM_BOT_TOKEN` | Optional | From @BotFather |
| `TELEGRAM_ALLOWED_CHAT_IDS` | Optional | Comma-separated chat IDs (get from @userinfobot) |
| `ORS_API_KEY` | Optional | OpenRouteService key (free at openrouteservice.org) |
| `HUE_BRIDGE_IP` | Optional | Philips Hue bridge IP |
| `REQUESTS_CA_BUNDLE` | Optional | Path to Hue bridge `.pem` cert |

## MongoDB MCP Server

Claude Code has direct MongoDB access via MCP tools (no bash needed):

- `mcp__langbox-mongodb__list_collections`
- `mcp__langbox-mongodb__query_collection` — `collection`, `filter`, `limit`
- `mcp__langbox-mongodb__count_documents` — `collection`, `filter`
- `mcp__langbox-mongodb__get_recent_journal_entries` — `limit`
- `mcp__langbox-mongodb__search_journal` — `searchText`, `limit`

Configured in `.config/claude-code/mcp.json`. Requires Node.js and MongoDB running.
