"""Agent factory for creating LLM instances."""

import multiprocessing
import os
from typing import Optional

from langchain.agents import create_agent
from langchain_community.chat_models import ChatLlamaCpp
from loguru import logger


def _model_path(model_name: str) -> str:
    base = os.environ.get("MODEL_PATH", "models/")
    return os.path.join(base, model_name)


def _suppress_stderr():
    old_err = os.dup(2)
    old_out = os.dup(1)
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, 2)
    os.dup2(devnull, 1)
    return old_err, old_out, devnull


def _restore_stderr(old_err, old_out, devnull):
    os.dup2(old_err, 2)
    os.dup2(old_out, 1)
    os.close(old_err)
    os.close(old_out)
    os.close(devnull)


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
    if model_name is None:
        model_name = os.environ.get("MODEL_GENERALIST")
    if n_threads is None:
        n_threads = multiprocessing.cpu_count() - 1

    fds = _suppress_stderr()
    try:
        return ChatLlamaCpp(
            model_path=_model_path(model_name),
            temperature=temperature,
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
            n_batch=n_batch,
            max_tokens=max_tokens,
            repeat_penalty=repeat_penalty,
            top_p=top_p,
            top_k=top_k,
            echo=echo,
            n_threads=n_threads,
            verbose=verbose,
        )
    finally:
        _restore_stderr(*fds)


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

    kwargs = {"model": llm}
    if checkpointer is not None:
        kwargs["checkpointer"] = checkpointer
    kwargs.update(agent_kwargs)

    agent = create_agent(**kwargs)
    logger.debug(f"Agent created with model: {model_name or 'default'}")
    return agent
