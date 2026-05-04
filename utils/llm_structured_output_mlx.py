"""Utility for generating structured outputs using MLX + outlines."""

import os
import threading
import time
from typing import TypeVar

from outlines import Generator, from_mlxlm
from json_repair import repair_json
from langsmith import traceable
from utils.log import logger
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

# Guards the shared MLX model instance. Both generate_structured_output() and
# any concurrent callers need exclusive access to avoid context contamination.
mlx_lock = threading.Lock()


def _model_path(model_name: str, model_path: str | None = None) -> str:
  """Resolve full path to MLX model directory."""
  import glob
  import re

  base = model_path or os.environ.get("MODEL_PATH_MLX", "models/mlx/")

  # MLX models are directories, not files. If model_name has .gguf extension,
  # it's from MODEL_GENERALIST (shared with llama.cpp). Strip it.
  if model_name.endswith(".gguf"):
    # Remove .gguf and any quantization suffix (e.g., .q6_k)
    model_name = model_name.replace(".gguf", "")
    # Remove quantization patterns like .q6_k, .q4_k_m, etc.
    model_name = re.sub(r'\.(q[0-9]_k[_m]?|fp16|f16|f32)$', '', model_name)

  # First try exact match
  exact_path = os.path.join(base, model_name)
  if os.path.isdir(exact_path):
    return exact_path

  # If not found, try to find a directory that starts with the model name
  # (e.g., "gemma-3-12b-it-qat-abliterated" → "gemma-3-12b-it-qat-abliterated-4bit")
  pattern = os.path.join(base, f"{model_name}*")
  matches = [d for d in glob.glob(pattern) if os.path.isdir(d)]

  if matches:
    # Return the first match (alphabetically sorted)
    return sorted(matches)[0]

  # If still not found, return the exact path (will fail later with clear error)
  return exact_path


_mlx_model = None
_mlx_tokenizer = None
_mlx_loaded_model: str | None = None


def _get_or_load_mlx(model_name: str, full_path: str):
  """Load MLX model once and cache it."""
  global _mlx_model, _mlx_tokenizer, _mlx_loaded_model

  if _mlx_model is not None and _mlx_loaded_model == model_name:
    return _mlx_model, _mlx_tokenizer

  try:
    import mlx_lm
  except ImportError:
    raise ImportError(
      "mlx-lm is required for MLX inference. Install with: uv pip install mlx-lm"
    )

  # Verify the path exists before attempting to load
  if not os.path.isdir(full_path):
    raise FileNotFoundError(
      f"MLX model directory not found: {full_path}\n"
      f"MLX models must be directories with .safetensors files, not GGUF files.\n"
      f"Attempted to load model '{model_name}' from MLX path."
    )

  t0 = time.perf_counter()
  logger.debug(f"[mlx] Loading model from {full_path}")

  try:
    model, tokenizer = mlx_lm.load(full_path)
  except Exception as e:
    raise RuntimeError(
      f"Failed to load MLX model from {full_path}: {e}\n"
      f"Ensure the directory contains valid MLX model files (.safetensors, config.json, etc.)"
    ) from e

  _mlx_model = model
  _mlx_tokenizer = tokenizer
  _mlx_loaded_model = model_name

  logger.debug(f"[mlx] Loaded model in {time.perf_counter() - t0:.1f}s")
  return model, tokenizer


@traceable(name="structured_output_generation_mlx", run_type="llm")
def generate_structured_output(
  model_name: str,
  user_prompt: str,
  system_prompt: str,
  pydantic_model: type[T],
  model_path: str | None = None,
  max_tokens: int | None = 512,
  **mlx_kwargs,
) -> T:
  """
  Generate structured output using MLX + Outlines.

  Args:
    model_name: Name of the MLX model directory (e.g., "Llama-3.1-8B-Instruct-8bit")
    user_prompt: User's query
    system_prompt: System instructions
    pydantic_model: Pydantic model class for structured output
    model_path: Optional override for model base path (defaults to MODEL_PATH_MLX env var)
    max_tokens: Maximum tokens to generate
    **mlx_kwargs: Additional kwargs for MLX generation (temperature, etc.)

  Returns:
    Instance of pydantic_model with constrained output
  """
  try:
    full_path = _model_path(model_name, model_path)
    model, tokenizer = _get_or_load_mlx(model_name, full_path)

    prompt = (
      f"Following these instructions: {system_prompt}. answer the users query: {user_prompt} "
    )

    with mlx_lock:
      # Create outlines generator from MLX model
      outlines_model = from_mlxlm(model, tokenizer)
      generator = Generator(outlines_model, output_type=pydantic_model)

      # Generate with schema constraints
      result = generator(prompt, max_tokens=max_tokens, **mlx_kwargs)

    # Outlines should return parsed Pydantic model, but handle string fallback
    if isinstance(result, str):
      try:
        repaired = repair_json(result)
        return pydantic_model.model_validate_json(repaired)
      except Exception as repair_error:
        logger.warning(f"JSON repair failed: {repair_error}, trying original")
        return pydantic_model.model_validate_json(result)

    return result

  except Exception as error:
    logger.error(f"Failed to generate structured output with MLX: {error}")
    raise
