"""Utility for generating structured outputs — supports llamacpp and ollama backends."""

import gc
import os
import threading
import time
from typing import TypeVar

import outlines
import psutil
from json_repair import repair_json
from langsmith import traceable
from llama_cpp import Llama
from loguru import logger
from pydantic import BaseModel

try:
    from pynvml import nvmlDeviceGetHandleByIndex, nvmlDeviceGetMemoryInfo, nvmlInit
    _nvml_available = True
except Exception:
    _nvml_available = False

# ---------------------------------------------------------------------------
# Backend detection
# ---------------------------------------------------------------------------

def _backend() -> str:
    return os.environ.get("INFERENCE_BACKEND", "llamacpp").lower()

# ---------------------------------------------------------------------------
# Memory helpers
# ---------------------------------------------------------------------------

def _snapshot_memory() -> tuple[float | None, float]:
    vram = None
    if _nvml_available:
        try:
            nvmlInit()
            info = nvmlDeviceGetMemoryInfo(nvmlDeviceGetHandleByIndex(0))
            vram = info.used / 1024 ** 2
        except Exception:
            pass
    ram = psutil.Process(os.getpid()).memory_info().rss / 1024 ** 2
    return vram, ram


def _is_memory_pressure(vram_threshold: float = 0.92, ram_threshold: float = 0.92) -> bool:
    """Return True when VRAM or system RAM is above the given usage fraction."""
    if _nvml_available:
        try:
            nvmlInit()
            info = nvmlDeviceGetMemoryInfo(nvmlDeviceGetHandleByIndex(0))
            if info.used / info.total > vram_threshold:
                return True
        except Exception:
            pass
    return psutil.virtual_memory().percent / 100 > ram_threshold


def print_load_stats(model_name: str, full_path: str, elapsed: float,
                     vram_before: float | None, vram_after: float | None,
                     ram_before: float, ram_after: float) -> None:
    file_mb = os.path.getsize(full_path) / 1024 ** 2
    vram_str = (
        f"+{vram_after - vram_before:.0f} MB"
        if vram_before is not None and vram_after is not None
        else "N/A"
    )
    print(
        f"[LLM] {model_name} | "
        f"file: {file_mb:.0f} MB | "
        f"load time: {elapsed:.2f}s | "
        f"VRAM delta: {vram_str} | "
        f"RAM delta: +{ram_after - ram_before:.0f} MB"
    )

# ---------------------------------------------------------------------------
# llamacpp model cache
# ---------------------------------------------------------------------------

_llama_cache: dict[tuple, Llama] = {}
_llama_last_used: dict[tuple, float] = {}
_llama_lock = threading.Lock()


def _llama_cache_key(model_name: str, n_ctx: int | None, n_gpu_layers: int,
                     max_tokens: int | None, llama_kwargs: dict) -> tuple:
    return (model_name, n_ctx, n_gpu_layers, max_tokens, tuple(sorted(llama_kwargs.items())))


def _evict_lru_llama() -> None:
    if not _llama_last_used:
        return
    lru_key = min(_llama_last_used, key=_llama_last_used.__getitem__)
    evicted = _llama_cache.pop(lru_key, None)
    _llama_last_used.pop(lru_key, None)
    if evicted is not None:
        del evicted
        gc.collect()
        logger.info(f"[cache] Evicted Llama model due to memory pressure: {lru_key[0]}")


def _get_or_load_llama(model_name: str, full_path: str, n_ctx: int | None,
                       n_gpu_layers: int, max_tokens: int | None,
                       llama_kwargs: dict) -> Llama:
    key = _llama_cache_key(model_name, n_ctx, n_gpu_layers, max_tokens, llama_kwargs)

    with _llama_lock:
        if key in _llama_cache:
            _llama_last_used[key] = time.monotonic()
            logger.debug(f"[cache] Reusing Llama model: {model_name}")
            return _llama_cache[key]

        while _is_memory_pressure() and _llama_cache:
            _evict_lru_llama()

        vram_before, ram_before = _snapshot_memory()
        t0 = time.perf_counter()
        fds = _suppress_stderr()
        try:
            llm = Llama(
                model_path=full_path,
                n_ctx=n_ctx,
                max_tokens=max_tokens,
                n_gpu_layers=n_gpu_layers,
                verbose=False,
                **llama_kwargs,
            )
        finally:
            _restore_stderr(*fds)
        elapsed = time.perf_counter() - t0
        vram_after, ram_after = _snapshot_memory()
        print_load_stats(model_name, full_path, elapsed, vram_before, vram_after, ram_before, ram_after)

        _llama_cache[key] = llm
        _llama_last_used[key] = time.monotonic()
        return llm

# ---------------------------------------------------------------------------
# Internal utilities
# ---------------------------------------------------------------------------

T = TypeVar("T", bound=BaseModel)


def _model_path(model_name: str, model_path: str | None = None) -> str:
    base = model_path or os.environ.get("MODEL_PATH", "models/")
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
# Ollama structured output
# ---------------------------------------------------------------------------

def _generate_structured_output_ollama(
    model_name: str,
    user_prompt: str,
    system_prompt: str,
    pydantic_model: type[T],
) -> T:
    from langchain_ollama import ChatOllama
    from langchain_core.messages import HumanMessage, SystemMessage

    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    t0 = time.perf_counter()
    llm = ChatOllama(model=model_name, base_url=base_url, temperature=0)
    structured = llm.with_structured_output(pydantic_model)
    result = structured.invoke([SystemMessage(system_prompt), HumanMessage(user_prompt)])
    elapsed = time.perf_counter() - t0
    print(f"[LLM/ollama] {model_name} | time: {elapsed:.2f}s")
    return result

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@traceable(name="structured_output_generation", run_type="llm")
def generate_structured_output(
    model_name: str,
    user_prompt: str,
    system_prompt: str,
    pydantic_model: type[T],
    model_path: str | None = None,
    n_ctx: int | None = 2048,
    max_tokens: int | None = 2500,
    n_gpu_layers: int = -1,
    **llama_kwargs,
) -> T:
    """Generate structured output from a model.

    Backend is selected via the INFERENCE_BACKEND env var:
      - "llamacpp" (default): uses llama-cpp-python + outlines
      - "ollama": uses Ollama via langchain-ollama

    llamacpp-specific args (n_ctx, n_gpu_layers, max_tokens, **llama_kwargs)
    are ignored when using the ollama backend.
    """
    try:
        if _backend() == "ollama":
            return _generate_structured_output_ollama(
                model_name, user_prompt, system_prompt, pydantic_model
            )

        full_path = _model_path(model_name, model_path)
        llm = _get_or_load_llama(model_name, full_path, n_ctx, n_gpu_layers, max_tokens, llama_kwargs)

        model = outlines.from_llamacpp(llm)
        prompt = f"Following these instructions: {system_prompt}. answer the users query: {user_prompt} "

        logger.debug(
            f"Generating structured output: Model:{model_name}, "
            f"Structure:{pydantic_model.__name__}, Context size: {n_ctx} Max tokens: {max_tokens}"
        )

        result = model(model_input=prompt, output_type=pydantic_model, max_tokens=max_tokens)
        logger.debug(f"Generated output: {result}")

        if isinstance(result, str):
            try:
                repaired = repair_json(result)
                return pydantic_model.model_validate_json(repaired)
            except Exception as repair_error:
                logger.warning(f"JSON repair failed: {repair_error}, trying original")
                return pydantic_model.model_validate_json(result)
        return result

    except Exception as error:
        logger.error(f"Failed to generate structured output: {error}")
        raise
