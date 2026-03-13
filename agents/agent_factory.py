"""Agent factory for creating LLM instances."""

import gc
import multiprocessing
import os
import threading
import time
from typing import Optional

from langchain.agents import create_agent
from langchain_community.chat_models import ChatLlamaCpp
from loguru import logger

from utils.llm_structured_output import _backend, _is_memory_pressure, _snapshot_memory, print_load_stats


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


# ---------------------------------------------------------------------------
# ChatLlamaCpp cache
# ---------------------------------------------------------------------------

_llm_cache: dict[tuple, ChatLlamaCpp] = {}
_llm_last_used: dict[tuple, float] = {}
_llm_lock = threading.Lock()


def _llm_cache_key(model_name, temperature, n_ctx, n_gpu_layers, n_batch,
                   max_tokens, repeat_penalty, top_p, top_k, echo, n_threads) -> tuple:
    return (model_name, temperature, n_ctx, n_gpu_layers, n_batch,
            max_tokens, repeat_penalty, top_p, top_k, echo, n_threads)


def _evict_lru_llm() -> None:
    if not _llm_last_used:
        return
    lru_key = min(_llm_last_used, key=_llm_last_used.__getitem__)
    evicted = _llm_cache.pop(lru_key, None)
    _llm_last_used.pop(lru_key, None)
    if evicted is not None:
        del evicted
        gc.collect()
        logger.info(f"[cache] Evicted ChatLlamaCpp model due to memory pressure: {lru_key[0]}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _create_llm_ollama(model_name: str, temperature: float, n_ctx: int,
                       max_tokens: int, top_p: float, top_k: int, repeat_penalty: float):
    from langchain_ollama import ChatOllama
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    t0 = time.perf_counter()
    llm = ChatOllama(
        model=model_name,
        base_url=base_url,
        temperature=temperature,
        num_ctx=n_ctx,
        num_predict=max_tokens,
        top_p=top_p,
        top_k=top_k,
        repeat_penalty=repeat_penalty,
    )
    elapsed = time.perf_counter() - t0
    print(f"[LLM/ollama] {model_name} | time: {elapsed:.2f}s")
    return llm


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

    if _backend() == "ollama":
        return _create_llm_ollama(model_name, temperature, n_ctx, max_tokens, top_p, top_k, repeat_penalty)

    key = _llm_cache_key(model_name, temperature, n_ctx, n_gpu_layers, n_batch,
                         max_tokens, repeat_penalty, top_p, top_k, echo, n_threads)

    with _llm_lock:
        if key in _llm_cache:
            _llm_last_used[key] = time.monotonic()
            logger.debug(f"[cache] Reusing ChatLlamaCpp model: {model_name}")
            return _llm_cache[key]

        while _is_memory_pressure() and _llm_cache:
            _evict_lru_llm()

        full_path = _model_path(model_name)
        vram_before, ram_before = _snapshot_memory()
        t0 = time.perf_counter()
        fds = _suppress_stderr()
        try:
            llm = ChatLlamaCpp(
                model_path=full_path,
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
        elapsed = time.perf_counter() - t0
        vram_after, ram_after = _snapshot_memory()
        print_load_stats(model_name, full_path, elapsed, vram_before, vram_after, ram_before, ram_after)

        _llm_cache[key] = llm
        _llm_last_used[key] = time.monotonic()
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
