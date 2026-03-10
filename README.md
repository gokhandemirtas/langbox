# Langbox

An intelligent personal assistant system using local LLM inference with LangChain and llama-cpp-python. The project uses GGUF model files for efficient CPU/GPU inference and MongoDB for data persistence.

## Features

- Intent classification and routing to specialized handlers
- Weather forecasts and queries
- Finance tracking and stock information
- Calendar management
- Smart home control
- Security system integration
- Timer and reminders
- Transportation and navigation
- General conversation capabilities
- Structured output generation using outlines

## Prerequisites

- Python >= 3.11.14
- MongoDB (via Docker)
- `uv` package manager

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd langbox
```

2. Install dependencies using `uv`:
```bash
uv sync
```

3. Set up environment variables by copying `.env.template` to `.env` and configuring:
```bash
cp .env.template .env
# Edit .env with your configuration
```

4. Auto Download GGUF models and place them in the `models/` directory
```
uv run init_models.py
```

5. Start MongoDB:
```bash
cd db && docker-compose up -d
```

## Usage

Run the main application:
```bash
uv run python main.py
```

## Architecture

### Core Components

- **Intent Classifier** (`agents/intent_classifier.py`): Classifies user queries using LangGraph and Qwen2.5 model
- **Router** (`agents/router.py`): Routes intents to specialized handlers
- **Handlers** (`handlers/`): Domain-specific functionality for weather, finance, calendar, etc.
- **Database** (`db/`): MongoDB integration with Beanie ODM

### Structured Output Generation

The project includes a reusable utility for generating structured outputs using outlines with llama.cpp backend.

#### Usage Example

```python
from utils.llm_structured_output import generate_structured_output
from pydantic import BaseModel
import os

# Define your response model
class MyResponse(BaseModel):
    field1: str
    field2: int

# Define your prompt function
def my_prompt(query: str) -> str:
    return f"Extract information from: {query}"

# Generate structured output
result = generate_structured_output(
    model_name=os.environ["MODEL_PHI4"],
    prompt_function=my_prompt,
    pydantic_model=MyResponse,
    query="The answer is hello and 42"
)
```

#### Advanced Usage with Llama Parameters

```python
result = generate_structured_output(
    model_name=os.environ["MODEL_PHI4"],
    prompt_function=my_prompt,
    pydantic_model=MyResponse,
    query="Extract this data...",
    n_ctx=8192,          # Context window size
    n_gpu_layers=8,      # GPU layers to offload
    n_batch=1000,        # Batch size
    temperature=0.0,     # Sampling temperature
)
```

#### Creating New Handlers with Structured Output

1. Define your Pydantic model in `pydantic_types/`:
```python
from pydantic import BaseModel

class FinanceIntentResponse(BaseModel):
    ticker: str
    action: str
```

2. Create your prompt function in `prompts/`:
```python
def financeIntentPrompter(query: str) -> str:
    return f"Extract financial intent from: {query}"
```

3. Use the generic function in your handler:
```python
from utils.llm_structured_output import generate_structured_output

result = generate_structured_output(
    model_name=os.environ["MODEL_FINANCE_LLAMA"],
    prompt_function=financeIntentPrompter,
    pydantic_model=FinanceIntentResponse,
    query=query,
)
```

## Project Structure

```
langbox/
├── agents/                  # Agent implementations
│   ├── intent_classifier.py
│   ├── router.py
│   └── agent_factory.py
├── handlers/                # Intent-specific handlers
│   ├── weather/
│   ├── finance/
│   ├── calendar/
│   ├── chat/
│   ├── conversation/
│   ├── home_control/
│   ├── information/
│   ├── reminder/
│   └── transportation/
├── prompts/                 # LLM prompt templates
├── pydantic_types/          # Pydantic response models
├── fixtures/                # Static data (tickers.json)
├── db/                      # Database configuration
│   ├── init.py
│   ├── schemas.py
│   └── docker-compose.yml
├── utils/                   # Utility functions
│   ├── llm_structured_output.py
│   ├── http_client.py
│   └── weather_client.py
├── mcp-server/              # MCP servers for Claude Code
│   └── mongodb/
├── models/                  # GGUF model files (not in git)
├── main.py                  # Application entry point
└── pyproject.toml           # Dependencies
```

## Configuration

### Environment Variables

Required variables in `.env`:
- `MODEL_PHI4`: Path to Qwen2.5 GGUF model
- `MODEL_PATH`: Directory containing model files
- `MONGODB_HOST`, `MONGODB_PORT`, `MONGODB_USER`, `MONGODB_PASSWORD`: MongoDB configuration

### Model Configuration

Models are stored in `models/` directory. Recommended quantization: Q5_K_M or Q4_K_M for balance between quality and performance.

Key LLM parameters:
- `n_ctx`: Context window (typically 8192)
- `n_gpu_layers`: GPU offloading (8-35 typical range)
- `n_batch`: Batch size (300-1000 range)
- `temperature`: 0.0 for deterministic, higher for creative

## Adding New Features

### Adding a New Intent Handler

1. Create handler file in `handlers/`:
```python
async def handle_new_intent(query: str) -> None:
    """Handle NEW_INTENT queries."""
    # Implementation
```

2. Register in `agents/router.py`:
```python
route_map = {
    "NEW_INTENT": handle_new_intent,
}
```

3. Update intent classification prompt in `prompts/intent_prompt.py`

## Development

### Running Tests
```bash
uv run pytest
```

### Code Formatting
```bash
uv run ruff format .
```

### Linting
```bash
uv run ruff check .
```

## License

[Your License]

## Contributing

[Your Contributing Guidelines]
