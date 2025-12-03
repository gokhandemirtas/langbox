# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Langbox is a Python project for running local LLM inference using LangChain and llama-cpp-python. The project uses GGUF model files for efficient CPU/GPU inference with the Llama.cpp backend.

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

## Architecture

### Model Configuration

The project is configured to use GGUF quantized models stored in the `models/` directory. The current setup uses:
- Model: Hermes-2-Pro-Llama-3-8B-Q5_K_M.gguf (5.7GB quantized model)
- Backend: llama-cpp-python via LangChain Community

### LLM Configuration (main.py:8-19)

Key parameters for ChatLlamaCpp:
- `n_ctx`: 8192 tokens context window (matches model training context)
- `n_gpu_layers`: 8 (offloads layers to GPU)
- `n_batch`: 300 (must be between 1 and n_ctx, affects VRAM usage)
- `max_tokens`: 512 (maximum generation length)
- `n_threads`: Uses CPU count - 1 for optimal performance
- `temperature`: 0.5 for balanced creativity/determinism
- `repeat_penalty`: 1.5 to reduce repetition

### Dependencies

Core libraries:
- `langchain`: Framework for LLM applications
- `langchain-community`: Community integrations (includes ChatLlamaCpp)
- `llama-cpp-python`: Python bindings for llama.cpp (enables GGUF model inference)

## Model Management

Models are stored in `models/` directory and are not tracked by git. When adding new models:
1. Download GGUF format models
2. Place them in `models/` directory
3. Update the `local_model` path in main.py

The n_gpu_layers and n_batch parameters should be adjusted based on available VRAM.
