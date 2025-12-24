"""Utility for generating structured outputs using outlines and llama.cpp."""

import os
import sys

os.environ["GGML_METAL_LOG_LEVEL"] = "0"
os.environ["GGML_LOG_LEVEL"] = "0"
os.environ["LLAMA_CPP_LOG_LEVEL"] = "0"

from typing import TypeVar

import outlines
from json_repair import repair_json
from loguru import logger
from pydantic import BaseModel

# Suppress stderr during llama_cpp import to hide Metal initialization logs
_original_stderr = sys.stderr
sys.stderr = open(os.devnull, "w")
try:
  from llama_cpp import Llama
finally:
  sys.stderr.close()
  sys.stderr = _original_stderr

T = TypeVar("T", bound=BaseModel)


def generate_structured_output(
  model_name: str,
  user_prompt: str,
  system_prompt: str,
  pydantic_model: type[T],
  model_path: str | None = None,
  n_ctx: int | None = 2048,
  max_tokens: int | None = 2500,
  **llama_kwargs,
) -> T:
  """Generate structured output using outlines with llama.cpp backend.

  Args:
      model_name: Name of the model (e.g., MODEL_QWEN2.5 environment variable value)
      user_prompt: The user's query to process
      system_prompt: System instructions/prompt for the model
      pydantic_model: Pydantic model class defining the expected output structure
      model_path: Optional path to models directory. Defaults to MODEL_PATH env var
      n_ctx: Context window size in tokens (default: 2048)
      max_tokens: Maximum tokens to generate (default: 512)
      **llama_kwargs: Additional keyword arguments to pass to Llama constructor
          (e.g., n_gpu_layers, temperature, etc.)

  Returns:
      Instance of pydantic_model with the structured response

  Raises:
      Exception: If model initialization or inference fails

  Example:
      >>> from pydantic import BaseModel
      >>> class WeatherIntent(BaseModel):
      ...     location: str
      ...     period: str
      >>> result = generate_structured_output(
      ...     model_name="qwen2.5-1.5b-instruct-fp16.gguf",
      ...     user_prompt="What's the weather in Seattle?",
      ...     system_prompt="Extract weather location and period from query",
      ...     pydantic_model=WeatherIntent,
      ...     n_ctx=2048,
      ...     max_tokens=512,
      ...     n_gpu_layers=8
      ... )
  """
  if model_path is None:
    model_path = os.environ.get("MODEL_PATH", "models/")

  # Construct full model path
  full_model_path = os.path.join(model_path, model_name)

  try:
    # Initialize llama.cpp model - suppress Metal logs during initialization
    stderr_backup = sys.stderr
    sys.stderr = open(os.devnull, "w")
    try:
      llm = Llama(
        model_path=full_model_path,
        n_ctx=n_ctx,
        max_tokens=max_tokens,
        verbose=False,
        **llama_kwargs,
      )
    finally:
      sys.stderr.close()
      sys.stderr = stderr_backup

    # Wrap with outlines for structured generation
    model = outlines.models.from_llamacpp(llm)

    prompt = f"""System prompt: {system_prompt}. Users query: {user_prompt} """

    logger.debug(f"Generating structured output with {model_name}")

    # Generate structured output
    result = model(prompt, pydantic_model)

    logger.debug(f"Generated output: {result}")

    # Parse the JSON string into the Pydantic model
    if isinstance(result, str):
      # Repair any malformed/truncated JSON before validation
      try:
        repaired_json = repair_json(result)
        logger.debug(f"Repaired JSON: {repaired_json}")
        return pydantic_model.model_validate_json(repaired_json)
      except Exception as repair_error:
        logger.warning(f"JSON repair failed: {repair_error}, trying original")
        return pydantic_model.model_validate_json(result)
    return result

  except Exception as error:
    logger.error(f"Failed to generate structured output: {error}")
    raise
