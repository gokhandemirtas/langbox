"""Agent factory for creating and managing LLM agents with configurable parameters."""

import gc
import multiprocessing
import os
import sys
from typing import Optional

# Suppress Metal/GGML logs before importing langchain_community
os.environ["GGML_METAL_LOG_LEVEL"] = "0"
os.environ["GGML_LOG_LEVEL"] = "0"
os.environ["LLAMA_CPP_LOG_LEVEL"] = "0"

from langchain.agents import create_agent
from langchain_community.chat_models import ChatLlamaCpp
from loguru import logger
from pynvml import nvmlInit, nvmlDeviceGetHandleByIndex, nvmlDeviceGetMemoryInfo

nvmlInit()
_gpu_handle = nvmlDeviceGetHandleByIndex(0)


def _log_vram(label: str):
    """Log current VRAM usage."""
    info = nvmlDeviceGetMemoryInfo(_gpu_handle)
    used = info.used / 1024**2
    total = info.total / 1024**2
    logger.debug(f"VRAM [{label}]: {used:.0f}MB / {total:.0f}MB")

# Track the active LLM so it can be reused or freed when a different model is needed
_active_llm = None
_active_model_name = None


def create_llm(
    model_name: Optional[str] = None,
    temperature: float = 0.5,
    n_ctx: int = 8192,
    n_gpu_layers: int = -1,
    n_batch: int = 1000,
    max_tokens: int = 512,
    repeat_penalty: float = 1.5,
    top_p: float = 0.95,
    top_k: int = 40,
    echo: bool = False,
    verbose: bool = False,
    n_threads: Optional[int] = None,
):
    """Create an LLM instance with configurable parameters.

    Args:
        model_name: Model filename (defaults to MODEL_HERMES_2_PRO env var)
        temperature: Sampling temperature (0.0 = deterministic, higher = more random)
        n_ctx: Context window size in tokens
        n_gpu_layers: Number of layers to offload to GPU
        n_batch: Batch size for processing (must be between 1 and n_ctx)
        max_tokens: Maximum tokens to generate
        repeat_penalty: Penalty for token repetition
        top_p: Nucleus sampling threshold
        top_k: Top-k sampling parameter
        echo: Whether to echo the prompt
        verbose: Enable verbose logging
        n_threads: Number of threads (defaults to CPU count - 1)

    Returns:
        Configured LangChain LLM instance

    Example:
        # Use default MODEL_HERMES_2_PRO
        llm = create_llm()

        # Override with specific model and temperature
        llm = create_llm(
            model_name=os.environ['MODEL_QWEN2.5'],
            temperature=0.0
        )
    """
    global _active_llm, _active_model_name

    # Use MODEL_HERMES_2_PRO as default, fallback to hardcoded default
    if model_name is None:
        model_name = os.environ.get('MODEL_HERMES_2_PRO', 'Hermes-2-Pro-Llama-3-8B-Q5_K_M.gguf')

    # Reuse the existing LLM if same model is requested
    if _active_llm is not None and _active_model_name == model_name:
        logger.debug(f"Reusing existing LLM instance for model: {model_name}")
        _log_vram(f"reusing {model_name}")
        return _active_llm

    # Different model requested — destroy the previous one to free memory
    if _active_llm is not None:
        prev_model = _active_model_name
        logger.debug(f"Destroying LLM instance ({prev_model}) to load {model_name}")
        del _active_llm
        _active_llm = None
        _active_model_name = None
        gc.collect()
        _log_vram(f"after destroying {prev_model}")

    # Default n_threads to CPU count - 1
    if n_threads is None:
        n_threads = multiprocessing.cpu_count() - 1

    # Use MODEL_PATH from environment or default to 'models/'
    model_path = f"{os.environ.get('MODEL_PATH', 'models/')}/{model_name}"

    # Suppress stdout and stderr during LLM initialization to hide Metal/GGML logs and chat template metadata
    stderr_backup = sys.stderr
    stdout_backup = sys.stdout
    devnull = open(os.devnull, 'w')
    sys.stderr = devnull
    sys.stdout = devnull

    try:
        llm = ChatLlamaCpp(
            temperature=temperature,
            model_path=model_path,
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
            n_batch=n_batch,
            max_tokens=max_tokens,
            echo=echo,
            n_threads=n_threads,
            repeat_penalty=repeat_penalty,
            top_p=top_p,
            top_k=top_k,
            verbose=verbose,
        )
    finally:
        sys.stderr = stderr_backup
        sys.stdout = stdout_backup
        devnull.close()

    _active_llm = llm
    _active_model_name = model_name
    _log_vram(f"after loading {model_name}")
    return llm


def create_llm_agent(
    model_name: Optional[str] = None,
    temperature: float = 0.5,
    n_ctx: int = 8192,
    n_gpu_layers: int = -1,
    n_batch: int = 1000,
    max_tokens: int = 512,
    repeat_penalty: float = 1.5,
    top_p: float = 0.95,
    top_k: int = 40,
    echo: bool = False,
    verbose: bool = False,
    n_threads: Optional[int] = None,
    checkpointer=None,
    **agent_kwargs,
):
    """Create an LLM agent with configurable parameters.

    Args:
        model_name: Model filename (defaults to MODEL_HERMES_2_PRO env var)
        temperature: Sampling temperature (0.0 = deterministic, higher = more random)
        n_ctx: Context window size in tokens
        n_gpu_layers: Number of layers to offload to GPU
        n_batch: Batch size for processing (must be between 1 and n_ctx)
        max_tokens: Maximum tokens to generate
        repeat_penalty: Penalty for token repetition
        top_p: Nucleus sampling threshold
        top_k: Top-k sampling parameter
        echo: Whether to echo the prompt
        verbose: Enable verbose logging
        n_threads: Number of threads (defaults to CPU count - 1)
        checkpointer: Optional checkpointer for the agent (e.g., InMemorySaver())
        **agent_kwargs: Additional keyword arguments to pass to create_agent

    Returns:
        Configured LangChain agent instance

    Example:
        # Use default MODEL_HERMES_2_PRO
        agent = create_llm_agent()

        # Override with specific model and temperature
        agent = create_llm_agent(
            model_name=os.environ['MODEL_QWEN2.5'],
            temperature=0.0
        )

        # Create agent with checkpointer
        from langgraph.checkpoint.memory import InMemorySaver
        agent = create_llm_agent(
            model_name=os.environ['MODEL_QWEN2.5'],
            temperature=0.0,
            checkpointer=InMemorySaver()
        )
    """
    llm = create_llm(
        model_name=model_name,
        temperature=temperature,
        n_ctx=n_ctx,
        n_gpu_layers=n_gpu_layers,
        n_batch=n_batch,
        max_tokens=max_tokens,
        repeat_penalty=repeat_penalty,
        top_p=top_p,
        top_k=top_k,
        echo=echo,
        verbose=verbose,
        n_threads=n_threads,
    )

    # Build agent kwargs
    create_agent_kwargs = {"model": llm}
    if checkpointer is not None:
        create_agent_kwargs["checkpointer"] = checkpointer
    create_agent_kwargs.update(agent_kwargs)

    agent = create_agent(**create_agent_kwargs)
    logger.debug(f"Agent created successfully with model: {model_name or 'default'}")
    return agent
