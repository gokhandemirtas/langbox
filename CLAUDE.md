# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Langbox is a Python project for running local LLM inference using LangChain and llama-cpp-python. The project uses GGUF model files for efficient CPU/GPU inference with the Llama.cpp backend, and MongoDB with Beanie ODM for data persistence.

This is an intelligent personal assistant system that uses LLMs to classify user intents and route them to specialized handlers for tasks like weather queries, finance tracking, calendar management, and more.

## Development Setup

This project uses `uv` for dependency management. Python version requirement: >=3.11.14

Install dependencies:
```bash
uv sync
```

Run the main script:
```bash
uv run python main.py
```

Start the MongoDB database:
```bash
cd db && docker-compose up -d
```

## Architecture

### System Architecture

The application follows a modular agent-based architecture:

1. **Intent Classification** (`agents/intent_classifier.py`)
   - Uses LangGraph with InMemorySaver for conversation state management
   - Classifies user queries into predefined intent categories
   - Employs Qwen2.5 model for fast, accurate intent detection
   - Configuration: temperature=0.0, n_ctx=8192, n_gpu_layers=8, n_batch=1000

2. **Intent Router** (`agents/router.py`)
   - Routes classified intents to appropriate handlers
   - Supports 10+ intent categories including weather, finance, calendar, home control, etc.
   - Falls back to general chat handler for unrecognized intents

3. **Specialized Handlers** (`handlers/`)
   - Each handler implements domain-specific functionality
   - Handlers are organized in subdirectories with a `handler_*.py` naming convention
   - Available handlers:
     - `weather/handler_weather.py`: Weather forecasts and queries (uses structured output generation)
     - `finance/handler_finance.py`: Stock information and financial data
     - `calendar/handler_calendar.py`: Schedule and calendar management
     - `home_control/handler_home_control.py`: Smart home device control (Philips Hue integration)
     - `security/handler_security.py`: Security system management
     - `timer/handler_timer.py`: Timer and reminder functionality
     - `transportation/handler_transportation.py`: Transportation and navigation
     - `information/handler_information.py`: General information queries
     - `chat/handler_chat.py`: General conversation and greetings
     - `conversation/handler_conversation.py`: Conversational wrapper that processes handler responses into natural language

4. **Conversational Response Handler** (`handlers/conversation.py`)
   - Processes raw handler responses into natural, conversational language
   - Uses LangChain agent with temperature=0.7 for natural responses
   - Saves complete conversation history to MongoDB with both formatted and raw responses
   - Executed after each handler completes to provide user-friendly output

5. **Agent Factory** (`agents/agent_factory.py`)
   - Centralizes LLM agent creation
   - Provides consistent configuration across different agents

### Model Configuration

The project uses GGUF quantized models stored in the `models/` directory. Models are referenced via environment variables in `.env`:
- Primary model: Configured via `MODEL_QWEN2.5` environment variable
- Backend: llama-cpp-python via LangChain Community
- Models are lazily initialized for better startup performance

### LLM Configuration

Key parameters for ChatLlamaCpp (as used in intent_classifier.py:27-39):
- `n_ctx`: 8192 tokens context window
- `n_gpu_layers`: 8 (offloads layers to GPU for better performance)
- `n_batch`: 1000 (must be between 1 and n_ctx, affects VRAM usage and throughput)
- `max_tokens`: 512 (maximum generation length)
- `temperature`: 0.0 for intent classification (deterministic); varies by handler
- `repeat_penalty`: 1.2 to reduce repetition
- `top_p`: 0.1 for focused sampling
- `top_k`: 10 for limited token consideration

**Performance Note**: GGML/Metal initialization logs are suppressed via environment variables in `main.py:4-5` and `utils/llm_structured_output.py:5-6` for cleaner output.

### Structured Output Generation

The project uses the `outlines` library for constrained generation to produce structured JSON outputs that conform to Pydantic schemas. This ensures reliable parsing and validation of LLM responses.

Implementation in `utils/llm_structured_output.py`:
- Direct integration with llama.cpp via `outlines.from_llamacpp()`
- Accepts Pydantic models to define output schema
- Guarantees valid JSON conforming to the schema
- **Creates a fresh `Llama` instance for each call** - no caching to prevent context contamination
- Used in weather and home control handlers for intent classification

Example usage (from `handlers/weather/handler_weather.py`):
```python
result = generate_structured_output(
    model_name=os.environ["MODEL_QWEN2.5"],
    user_prompt=query,
    system_prompt=weatherIntentPrompt,
    pydantic_model=WeatherIntentResponse,
)
```

Example from `handlers/home_control/handler_home_control.py`:
```python
result = generate_structured_output(
    model_name=os.environ["MODEL_LLAMA2_7B"],
    user_prompt=query,
    system_prompt=get_home_control_prompt(lights_list),
    pydantic_model=HomeControlIntentResponse,
    n_ctx=8192,
)
```

Pydantic models are stored in `pydantic_types/` directory for reusability across handlers:
- `WeatherIntentResponse`: Location and time period extraction for weather queries
- `HomeControlIntentResponse`: Target light and action (on/off) for home control

**Important**: Dynamic prompts should use functions (e.g., `get_home_control_prompt()`) to inject context like available devices into the system prompt.

### Database Configuration

The project uses MongoDB with Beanie ODM for document storage:
- **Database**: MongoDB 7 (via Docker Compose)
- **ODM**: Beanie (async document mapper built on Pydantic)
- **Driver**: PyMongo AsyncMongoClient
- **Initialization**: Managed through `db/init.py`

Configuration is loaded from environment variables (`.env` file):
- `MONGODB_HOST`: Database host (default: localhost)
- `MONGODB_PORT`: Database port (default: 27017)
- `MONGODB_USER`: Database user (default: admin)
- `MONGODB_PASSWORD`: Database password (default: admin)

Database schemas are defined in `db/schemas.py`:
- `Conversations`: Stores chat history with datestamp, question, answer, and raw handler response fields
- `Weather`: Caches weather data with location and forecast information

Connection string format:
```
mongodb://{MONGODB_USER}:{MONGODB_PASSWORD}@{MONGODB_HOST}:{MONGODB_PORT}
```

Usage example:
```python
from db.init import init
from db.schemas import Conversations, Weather
from datetime import datetime

# Initialize database connection (called in main.py)
await init()

# Use Beanie documents
conversation = Conversations(
    datestamp=datetime.now().date(),
    question="What's the weather?",
    answer="It's sunny today",
    raw="Raw handler response data"
)
await conversation.insert()
```

### Dependencies

Core libraries (from pyproject.toml):
- `langchain>=1.1.0`: Framework for LLM applications
- `langchain-community>=0.4.1`: Community integrations (includes ChatLlamaCpp)
- `langgraph>=1.0.4`: Graph-based agent orchestration with state management
- `llama-cpp-python>=0.3.16`: Python bindings for llama.cpp (enables GGUF model inference)
- `beanie>=2.0.1`: Async Python ODM for MongoDB (includes PyMongo AsyncMongoClient)
- `pydantic>=2.12.5`: Data validation and settings management
- `loguru>=0.7.3`: Simplified logging

Structured output generation:
- `outlines>=1.2.9`: Constrained generation for structured outputs from LLMs
- `numba>=0.63.1`: JIT compiler for Python (required by outlines)

External integrations:
- `python-weather>=2.1.0`: Weather data API client
- `yfinance>=0.2.66`: Yahoo Finance API for stock data
- `google-api-python-client>=2.187.0`: Google Calendar API integration
- `wikipedia>=1.4.0`: Wikipedia API for information queries
- `httpx>=0.28.1`: Modern async HTTP client
- `transformers>=4.57.3`: Hugging Face transformers for NLP tasks
- `questionary>=2.1.1`: Interactive command-line prompts
- `pyauto-dotenv>=0.1.0`: Automatic .env file loading
- `datetime>=6.0`: Date and time handling utilities
- `huesdk>=1.0.0`: Philips Hue smart home integration

Development tools:
- `ruff>=0.14.6`: Fast Python linter and formatter

## Project Structure

```
langbox/
├── agents/              # Agent implementations
│   ├── intent_classifier.py  # Intent classification logic
│   ├── router.py             # Intent routing to handlers
│   └── agent_factory.py      # LLM agent creation
├── handlers/           # Intent-specific handlers (organized in subdirectories)
│   ├── weather/
│   │   └── handler_weather.py       # Weather queries with structured output
│   ├── conversation/
│   │   └── handler_conversation.py  # Conversational response wrapper
│   ├── finance/
│   │   └── handler_finance.py       # Finance/stock queries
│   ├── calendar/
│   │   └── handler_calendar.py      # Calendar management
│   ├── chat/
│   │   └── handler_chat.py          # General chat and greetings
│   ├── home_control/
│   │   └── handler_home_control.py  # Philips Hue smart home control
│   ├── security/
│   │   └── handler_security.py      # Security system
│   ├── timer/
│   │   └── handler_timer.py         # Timers and reminders
│   ├── transportation/
│   │   └── handler_transportation.py # Transportation queries
│   └── information/
│       └── handler_information.py   # Information lookup
├── prompts/           # LLM prompt templates
│   ├── intent_prompt.py
│   ├── weather_prompt.py
│   ├── conversation_prompt.py
│   ├── finance_prompt.py
│   └── home_control_prompt.py       # Dynamic prompt generation for Hue
├── pydantic_types/    # Pydantic models for structured outputs
│   ├── weather_intent_response.py
│   ├── weather_forecast.py
│   └── home_control_intent_response.py
├── db/                # Database configuration
│   ├── init.py            # Database initialization
│   ├── schemas.py         # Beanie document models
│   └── docker-compose.yml # MongoDB container config
├── utils/             # Utility functions
│   ├── http_client.py
│   ├── weather_client.py
│   └── llm_structured_output.py  # Outlines-based structured generation
├── models/            # GGUF model files (not in git)
├── main.py           # Application entry point
├── .env              # Environment variables (includes Hue bridge config)
└── pyproject.toml    # Dependencies and project metadata
```

## Model Management

Models are stored in `models/` directory and are not tracked by git.

When adding new models:
1. Download GGUF format models (recommended: quantized models like Q5_K_M or Q4_K_M)
2. Place them in `models/` directory
3. Add the model path to `.env` file with an appropriate variable name (e.g., `MODEL_QWEN2.5`)
4. Reference the model in code via `os.environ.get('MODEL_NAME')`

**Performance tuning**:
- `n_gpu_layers`: Adjust based on available VRAM (8-35 typical range)
- `n_batch`: Higher values improve throughput but use more VRAM (300-1000 range)
- `n_ctx`: Set based on model's training context (usually 4096, 8192, or 32768)
- For CPU-only inference, set `n_gpu_layers=0`

## Adding New Handlers

To add a new intent handler:

1. Create handler file in `handlers/` directory:
```python
from loguru import logger

async def handle_new_intent(query: str) -> str:
    """Handle NEW_INTENT queries.

    Args:
        query: The user's original query

    Returns:
        Raw response data (will be processed by conversation handler)
    """
    logger.debug(f"Handling NEW_INTENT: {query}")
    # Implementation here
    return "Raw response data"
```

2. Add intent to `agents/router.py`:
```python
valid_intents = [
    # ... existing intents
    "NEW_INTENT",
]

route_map = {
    # ... existing routes
    "NEW_INTENT": handle_new_intent,
}
```

3. Update intent classification prompt in `prompts/intent_prompt.py` to include the new intent category.

4. (Optional) Create specialized prompt template in `prompts/new_intent_prompt.py`.

5. (Optional) If you need structured outputs, create Pydantic models in `pydantic_types/` and use `utils/llm_structured_output.py`.

**Important**: All handlers should return string responses. The `handlers/conversation.py` will automatically process these into natural language before displaying to the user and saving to the database.

## Application Flow

1. User input is received in `main.py` via continuous loop
2. Query is sent to Intent Classifier (`agents/intent_classifier.py`)
3. Intent Classifier uses Qwen2.5 model to determine intent category
4. Intent Router (`agents/router.py`) dispatches to appropriate handler
5. Handler executes domain-specific logic (may use structured output generation)
6. Handler returns raw response data
7. Conversational Handler (`handlers/conversation.py`) wraps response in natural language
8. Complete interaction (question, answer, raw response) is saved to MongoDB
9. Natural language response is displayed to user
10. Loop continues for next query

## Interactive Features

The system uses `questionary` for interactive CLI prompts when additional information is needed:
- Missing location in weather queries (see `handlers/weather.py:161-164`)
- Missing time period selection (see `handlers/weather.py:173-175`)

This allows graceful handling of incomplete queries without restarting the conversation.

## Environment Variables

Required variables in `.env`:
- `MODEL_QWEN2.5`: Path to the Qwen2.5 GGUF model file (filename only, relative to `models/` directory)
- `MODEL_LLAMA2_7B`: Path to Llama 2 7B model for home control (e.g., `llama-2-7b-chat.Q3_K_M.gguf`)
- `MODEL_PATH`: Path to models directory (defaults to `models/` if not specified)
- `MONGODB_HOST`: MongoDB host (default: localhost)
- `MONGODB_PORT`: MongoDB port (default: 27017)
- `MONGODB_USER`: MongoDB username (default: admin)
- `MONGODB_PASSWORD`: MongoDB password (default: admin)

Smart Home Integration (Philips Hue):
- `HUE_BRIDGE_IP`: IP address of the Philips Hue bridge (e.g., "192.168.0.10")
- `REQUESTS_CA_BUNDLE`: Path to Hue bridge certificate file (e.g., "hue_bridge.pem")

Optional integration-specific variables:
- Weather API credentials
- Google Calendar OAuth credentials
- Other service API keys

**Note**: Model files (`.gguf`) and certificates (`.pem`) are excluded from git via `.gitignore`.
