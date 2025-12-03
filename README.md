# Langbox

A reliable, locally-run personal assistant using GGUF model inference, structured output generation, and a modular skill architecture. Designed for predictability and safety over agentic unpredictability — the LLM classifies intent, Python orchestrates execution.

## Features

- Intent classification with constrained structured output (outlines + llama.cpp)
- Skill-based routing: weather, finance, home control, reminders, news, search, transportation, information
- Autonomous multi-step planner with outlines-based tool selection loop
- Telegram bot interface for remote access
- MongoDB persistence (conversations, plans, reminders, weather cache)
- Smart home control via Philips Hue
- Face tracking and emotion detection (optional)

## Prerequisites

- Python >= 3.11.14
- `uv` package manager
- MongoDB (via Docker Compose)
- Node.js (for MCP server)
- A GGUF model file (Q5_K_M or Q6_K recommended)

## Installation

```bash
git clone <repository-url>
cd langbox
uv sync
cp .env.template .env
# Edit .env with your configuration
cd db && docker-compose up -d
```

## Running

```bash
uv run python main.py
uv run python main.py --debug     # debug logging
uv run python main.py --speak       # TTS output
uv run python main.py --track_camera  # enable face tracking
```

## CLI Commands

| Command | Description |
|---|---|
| `/planner <task>` | Run the autonomous multi-step planning agent |
| `/save` | Summarise and save the current session to MongoDB |
| `/clear` | Wipe in-memory conversation history |
| `/history` | Print session history to terminal |
| `/help` | List available commands |

## Telegram

Send messages to your bot to use the assistant remotely. Use `@planner <task>` to invoke the planner. Responses are capped at 4096 characters and summarised if necessary.

## Architecture

### Request Flow

```
User input (CLI or Telegram)
  → intent_classifier.py   — outlines constrains output to IntentResponse
  → router.py              — looks up skill in SKILL_MAP, calls skill.handle()
  → skill handler          — fetches/computes raw data
  → handle_conversation()  — wraps raw data into natural language (if needs_wrapping=True)
  → response returned and saved to MongoDB history
```

### Reliability Design

The system uses **outlines-constrained generation** throughout rather than free-form LLM tool calling. The LLM can only output values that conform to a Pydantic schema — invalid intents, unknown tickers, and malformed tool calls are structurally impossible. This is why intent classification and sub-classification are reliable where vanilla tool use is not.

### Skill Architecture

Each skill lives in `skills/<name>/`:

```
skills/<name>/
├── __init__.py     # exports: skill = Skill(id=..., handle=..., ...)
├── skill.py        # handler logic + inline Pydantic types
└── prompts.py      # sub-classification prompt (if needed)
```

The `Skill` dataclass (`skills/base.py`):

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Intent name used by the router (e.g. `"WEATHER"`) |
| `description` | `str` | One-liner injected into the intent classification prompt |
| `system_prompt` | `Optional[str]` | Sub-classification prompt (None if not used) |
| `handle` | `Callable` | Async or sync handler — signature: `handle(query: str) -> str` |
| `needs_wrapping` | `bool` | If True, raw output is post-processed by `handle_conversation()` |

### Registered Skills

| Intent | Skill | Description |
|---|---|---|
| `WEATHER` | `skills/weather/` | Forecasts via Open-Meteo (no API key) |
| `FINANCE_STOCKS` | `skills/finance/` | Stock prices via yfinance + fuzzy ticker resolution |
| `HOME_CONTROL` | `skills/home_control/` | Philips Hue lights control |
| `REMINDER` | `skills/reminder/` | Timers and reminders stored in MongoDB |
| `NEWSFEED` | `skills/newsfeed/` | RSS news headlines |
| `SEARCH` | `skills/search/` | Web search via DuckDuckGo |
| `TRANSPORTATION` | `skills/transportation/` | Directions via OpenRouteService |
| `INFORMATION_QUERY` | `skills/information/` | Wikipedia knowledge lookup |
| `CHAT` | `skills/conversation/` | General conversation with rolling history |

### Background Services

- **Telegram** (`skills/telegram/`) — polls Telegram and routes messages through the same pipeline as CLI. Started automatically if `TELEGRAM_BOT_TOKEN` is set.
- **Camera tracking** (`skills/camera_tracking/`) — face detection and emotion recognition. Started with `--track_camera` flag.
- **Personalizer** (`skills/personalizer/`) — conversation-based persona analysis. Currently disabled.

### Planner

`/planner <task>` invokes an outlines-based autonomous agent loop:

1. Structured output selects the next tool (`PlannerAction` schema)
2. Python calls the skill directly via `SKILL_MAP`
3. Results accumulate across up to 10 steps
4. LLM synthesises a final plan from all collected data
5. Plan saved to `Plans` collection in MongoDB

HOME_CONTROL is excluded from the planner (real-world side effects should not happen autonomously).

### Database Schemas (MongoDB via Beanie)

| Collection | Schema | Description |
|---|---|---|
| `conversations` | `Conversations` | Chat history per session |
| `plans` | `Plans` | Planner results (ask + plan + timestamp) |
| `reminders` | `Reminders` | Timers and reminders |
| `weather` | `Weather` | Cached weather data |
| `newsfeed` | `Newsfeed` | Cached RSS content |
| `credentials` | `Credentials` | Hue bridge username |
| `hueconfiguration` | `HueConfiguration` | Cached Hue lights/groups |
| `userpersona` | `UserPersona` | Persona analysis output |

## Adding a New Skill

1. Create `skills/<name>/skill.py` with an async handler:
```python
async def handle_new_intent(query: str) -> str:
    return "raw data string"
```

2. Export a `Skill` instance from `skills/<name>/__init__.py`:
```python
from skills.base import Skill
from skills.<name>.skill import handle_new_intent

skill = Skill(
    id="NEW_INTENT",
    description="One-liner for intent classification prompt",
    system_prompt=None,
    handle=handle_new_intent,
    needs_wrapping=True,
)
```

3. Register in `skills/registry.py`:
```python
from skills.<name> import skill as new_intent_skill
SKILLS = [..., new_intent_skill]
```

4. Add the literal to `pydantic_types/intent_response.py`:
```python
IntentLiteral = Literal[..., "NEW_INTENT"]
```

5. Add the intent category and examples to `_INTENT_PROMPT` in `agents/intent_classifier.py`.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `MODEL_GENERALIST` | Yes | GGUF model filename (relative to `MODEL_PATH`) |
| `MODEL_PATH` | Yes | Path to models directory |
| `MONGODB_HOST/PORT/USER/PASSWORD` | Yes | MongoDB connection |
| `MONGODB_DB` | Yes | Database name |
| `TELEGRAM_BOT_TOKEN` | Optional | From @BotFather |
| `TELEGRAM_ALLOWED_CHAT_IDS` | Optional | Comma-separated Telegram chat IDs |
| `ORS_API_KEY` | Optional | OpenRouteService API key (free at openrouteservice.org) |
| `HUE_BRIDGE_IP` | Optional | Philips Hue bridge IP |

## Scripts

```bash
uv run python scripts/update_tickers.py   # refresh tickers.json from S&P 500 + FTSE 100
```

## Development

```bash
uv run ruff format .   # format
uv run ruff check .    # lint
```
