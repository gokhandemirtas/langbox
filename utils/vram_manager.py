"""VRAM-aware LRU model manager for LLM instances.

Provides a unified cache for both ChatLlamaCpp (LangChain) and raw Llama
(llama-cpp-python / outlines) instances, tracking per-model VRAM usage and
evicting the least-recently-used model when GPU memory is insufficient.
"""

import gc
import multiprocessing
import os
import time
from dataclasses import dataclass, field

from loguru import logger
from pynvml import nvmlDeviceGetHandleByIndex, nvmlDeviceGetMemoryInfo, nvmlInit

# Suppress Metal/GGML/CUDA logs before any llama imports
os.environ["GGML_METAL_LOG_LEVEL"] = "0"
os.environ["GGML_LOG_LEVEL"] = "0"
os.environ["LLAMA_CPP_LOG_LEVEL"] = "0"


@dataclass
class ModelEntry:
  """A cached model instance with metadata for VRAM management."""

  instance: object
  model_name: str
  model_type: str  # "ChatLlamaCpp" or "Llama"
  vram_bytes: int = 0
  last_used: float = field(default_factory=time.time)
  cache_key: str = ""


class VRAMModelManager:
  """LRU cache for LLM models with VRAM-aware eviction."""

  def __init__(self):
    self._models: dict[str, ModelEntry] = {}  # key = cache_key
    nvmlInit()
    self._gpu_handle = nvmlDeviceGetHandleByIndex(0)
    self.log_vram("init")

  def log_vram(self, label: str):
    """Log current VRAM usage."""
    info = nvmlDeviceGetMemoryInfo(self._gpu_handle)
    used = info.used / 1024**2
    total = info.total / 1024**2
    logger.debug(f"VRAM [{label}]: {used:.0f}MB / {total:.0f}MB")

  def _get_free_vram(self) -> int:
    """Return free VRAM in bytes."""
    return nvmlDeviceGetMemoryInfo(self._gpu_handle).free

  def _estimate_model_size(self, model_path: str) -> int:
    """Estimate VRAM needed from the GGUF file size on disk."""
    try:
      return os.path.getsize(model_path)
    except OSError:
      logger.warning(f"Cannot stat {model_path}, assuming 2GB")
      return 2 * 1024**3

  def _suppress_stderr(self):
    """Redirect stderr+stdout to /dev/null. Returns restore info."""
    old_stderr_fd = os.dup(2)
    old_stdout_fd = os.dup(1)
    devnull_fd = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull_fd, 2)
    os.dup2(devnull_fd, 1)
    return old_stderr_fd, old_stdout_fd, devnull_fd

  def _restore_stderr(self, old_stderr_fd, old_stdout_fd, devnull_fd):
    """Restore stderr+stdout after suppression."""
    os.dup2(old_stderr_fd, 2)
    os.dup2(old_stdout_fd, 1)
    os.close(old_stderr_fd)
    os.close(old_stdout_fd)
    os.close(devnull_fd)

  def _ensure_vram(self, estimated_size: int):
    """Evict LRU models until there is enough free VRAM for the new model."""
    free = self._get_free_vram()
    if free >= estimated_size:
      return

    logger.debug(
      f"Need {estimated_size / 1024**2:.0f}MB, "
      f"free {free / 1024**2:.0f}MB — evicting LRU models"
    )

    # Sort by last_used ascending (oldest first)
    sorted_entries = sorted(self._models.values(), key=lambda e: e.last_used)
    for entry in sorted_entries:
      if self._get_free_vram() >= estimated_size:
        break
      self._evict(entry.cache_key)

  def _evict(self, cache_key: str):
    """Evict a single model from the cache and free its VRAM."""
    entry = self._models.pop(cache_key, None)
    if entry is None:
      return
    logger.debug(
      f"Evicting {entry.model_type}:{entry.model_name} "
      f"(~{entry.vram_bytes / 1024**2:.0f}MB, last used {time.time() - entry.last_used:.0f}s ago)"
    )
    del entry.instance
    del entry
    gc.collect()
    self.log_vram("after eviction")

  def _resolve_model_path(self, model_name: str, model_path: str | None = None) -> str:
    """Build full path to the GGUF file."""
    if model_path is None:
      model_path = os.environ.get("MODEL_PATH", "models/")
    return os.path.join(model_path, model_name)

  # -- Public API --------------------------------------------------------

  def get_or_load_llamacpp(
    self,
    model_name: str,
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
    n_threads: int | None = None,
    model_path: str | None = None,
  ):
    """Return a cached or freshly-loaded ChatLlamaCpp instance."""
    from langchain_community.chat_models import ChatLlamaCpp

    cache_key = f"ChatLlamaCpp:{model_name}"

    if cache_key in self._models:
      entry = self._models[cache_key]
      entry.last_used = time.time()
      logger.debug(f"Reusing cached ChatLlamaCpp for {model_name}")
      self.log_vram(f"reusing {model_name}")
      return entry.instance

    full_path = self._resolve_model_path(model_name, model_path)
    estimated = self._estimate_model_size(full_path)
    self._ensure_vram(estimated)

    if n_threads is None:
      n_threads = multiprocessing.cpu_count() - 1

    vram_before = nvmlDeviceGetMemoryInfo(self._gpu_handle).used

    fds = self._suppress_stderr()
    try:
      llm = ChatLlamaCpp(
        temperature=temperature,
        model_path=full_path,
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
      self._restore_stderr(*fds)

    vram_after = nvmlDeviceGetMemoryInfo(self._gpu_handle).used
    vram_used = max(0, vram_after - vram_before)

    self._models[cache_key] = ModelEntry(
      instance=llm,
      model_name=model_name,
      model_type="ChatLlamaCpp",
      vram_bytes=vram_used,
      last_used=time.time(),
      cache_key=cache_key,
    )
    logger.debug(f"Loaded ChatLlamaCpp:{model_name} ({vram_used / 1024**2:.0f}MB VRAM)")
    self.log_vram(f"after loading {model_name}")
    return llm

  def get_or_load_llama(
    self,
    model_name: str,
    model_path: str | None = None,
    n_ctx: int = 2048,
    max_tokens: int = 2500,
    verbose: bool = False,
    **llama_kwargs,
  ):
    """Return a cached or freshly-loaded raw Llama instance (for outlines)."""
    from llama_cpp import Llama

    cache_key = f"Llama:{model_name}"

    if cache_key in self._models:
      entry = self._models[cache_key]
      entry.last_used = time.time()
      logger.debug(f"Reusing cached Llama for {model_name}")
      self.log_vram(f"reusing {model_name}")
      return entry.instance

    full_path = self._resolve_model_path(model_name, model_path)
    estimated = self._estimate_model_size(full_path)
    self._ensure_vram(estimated)

    vram_before = nvmlDeviceGetMemoryInfo(self._gpu_handle).used

    fds = self._suppress_stderr()
    try:
      llm = Llama(
        model_path=full_path,
        n_ctx=n_ctx,
        max_tokens=max_tokens,
        verbose=verbose,
        **llama_kwargs,
      )
    finally:
      self._restore_stderr(*fds)

    vram_after = nvmlDeviceGetMemoryInfo(self._gpu_handle).used
    vram_used = max(0, vram_after - vram_before)

    self._models[cache_key] = ModelEntry(
      instance=llm,
      model_name=model_name,
      model_type="Llama",
      vram_bytes=vram_used,
      last_used=time.time(),
      cache_key=cache_key,
    )
    logger.debug(f"Loaded Llama:{model_name} ({vram_used / 1024**2:.0f}MB VRAM)")
    self.log_vram(f"after loading {model_name}")
    return llm


# Module-level singleton
vram_manager = VRAMModelManager()
