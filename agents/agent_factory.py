"""Agent factory for creating and managing LLM agents with configurable parameters."""

import multiprocessing
import os
import sys
from typing import Optional

from langchain.agents import create_agent
from langchain_community.chat_models import ChatLlamaCpp
from loguru import logger


def create_llm(
    model_name: Optional[str] = None,
    temperature: float = 0.5,
    n_ctx: int = 8192,
    n_gpu_layers: int = 8,
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
    # Use MODEL_HERMES_2_PRO as default, fallback to hardcoded default
    if model_name is None:
        model_name = os.environ.get('MODEL_HERMES_2_PRO', 'Hermes-2-Pro-Llama-3-8B-Q5_K_M.gguf')

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

    return llm


def create_llm_agent(
    model_name: Optional[str] = None,
    temperature: float = 0.5,
    n_ctx: int = 8192,
    n_gpu_layers: int = 8,
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
