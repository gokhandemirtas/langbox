"""Agent factory for creating LLM instances."""

import multiprocessing
import os
from typing import Optional

from langchain.agents import create_agent
from langchain_community.chat_models import ChatLlamaCpp
from loguru import logger

from utils.llm_structured_output import _get_or_load_llama, _model_path

_chat_llm_instance: ChatLlamaCpp | None = None


def create_llm(
    model_name: Optional[str] = None,
    temperature: float = 0.5,
    n_gpu_layers: int = -1,
    n_batch: int = 2048,
    max_tokens: int | None = None,
    repeat_penalty: float = 1.5,
    top_p: float = 0.95,
    top_k: int = 40,
    echo: bool = False,
    verbose: bool = False,
    n_threads: Optional[int] = None,
):
    global _chat_llm_instance

    if model_name is None:
        model_name = os.environ.get("MODEL_GENERALIST")
    if n_threads is None:
        n_threads = multiprocessing.cpu_count() - 1

    if _chat_llm_instance is not None:
        return _chat_llm_instance

    effective_max_tokens = max_tokens or int(os.environ.get("MODEL_MAX_TOKENS", 1024))
    n_ctx = int(os.environ.get("MODEL_CTX", 8192))

    full_path = _model_path(model_name)
    llama_instance = _get_or_load_llama(model_name, full_path, n_gpu_layers, {})

    llm = ChatLlamaCpp.model_construct(
        model_path=full_path,
        client=llama_instance,
        temperature=temperature,
        n_ctx=n_ctx,
        n_gpu_layers=n_gpu_layers,
        n_batch=n_batch,
        max_tokens=effective_max_tokens,
        repeat_penalty=repeat_penalty,
        top_p=top_p,
        top_k=top_k,
        echo=echo,
        n_threads=n_threads,
        verbose=verbose,
    )

    _chat_llm_instance = llm
    return llm


def create_llm_agent(
    model_name: Optional[str] = None,
    temperature: float = 0.5,
    n_gpu_layers: int = -1,
    n_batch: int = 2048,
    max_tokens: int | None = None,
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
    return agent
