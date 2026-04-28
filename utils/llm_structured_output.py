"""Utility for generating structured outputs using llama-cpp-python + outlines."""

import os
import threading
import time
from typing import TypeVar

import outlines
from json_repair import repair_json
from langsmith import traceable
from llama_cpp import Llama
from utils.log import logger
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

# Guards the shared Llama instance. Both generate_structured_output() and
# ChatLlamaCpp (via create_llm/agent_factory) use the same underlying Llama
# object — concurrent access from background tasks corrupts its KV cache.
llm_lock = threading.Lock()


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


_llama_instance: Llama | None = None
_llama_loaded_model: str | None = None


def _get_or_load_llama(
  model_name: str,
  full_path: str,
  n_gpu_layers: int,
  llama_kwargs: dict,
) -> Llama:
  global _llama_instance, _llama_loaded_model

  if _llama_instance is not None:
    return _llama_instance

  n_ctx = int(os.environ.get("MODEL_CTX", 8192))

  t0 = time.perf_counter()
  fds = _suppress_stderr()
  try:
    llm = Llama(
      model_path=full_path,
      n_ctx=n_ctx,
      n_gpu_layers=n_gpu_layers,
      n_batch=2048,
      flash_attn=True,
      use_mlock=True,
      verbose=False,
      **llama_kwargs,
    )
  finally:
    _restore_stderr(*fds)

  _llama_instance = llm
  _llama_loaded_model = model_name
  logger.debug(f"[llm] Loaded model in {time.perf_counter() - t0:.1f}s (ctx={n_ctx})")
  return llm


@traceable(name="structured_output_generation", run_type="llm")
def generate_structured_output(
  model_name: str,
  user_prompt: str,
  system_prompt: str,
  pydantic_model: type[T],
  model_path: str | None = None,
  max_tokens: int | None = 512,
  n_gpu_layers: int = -1,
  **llama_kwargs,
) -> T:
  try:
    full_path = _model_path(model_name, model_path)
    llm = _get_or_load_llama(model_name, full_path, n_gpu_layers, llama_kwargs)

    prompt = (
      f"Following these instructions: {system_prompt}. answer the users query: {user_prompt} "
    )

    with llm_lock:
      model = outlines.from_llamacpp(llm)
      result = model(model_input=prompt, output_type=pydantic_model, max_tokens=max_tokens)

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
