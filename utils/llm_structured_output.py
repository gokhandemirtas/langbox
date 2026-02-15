"""Utility for generating structured outputs using outlines and llama.cpp."""

import os
from typing import TypeVar

import outlines
from json_repair import repair_json
from langsmith import traceable
from loguru import logger
from pydantic import BaseModel

from utils.vram_manager import vram_manager

T = TypeVar("T", bound=BaseModel)


@traceable(name="structured_output_generation", run_type="llm")
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

  """
  try:
    llm = vram_manager.get_or_load_llama(
      model_name=model_name,
      model_path=model_path,
      n_ctx=n_ctx,
      max_tokens=max_tokens,
      verbose=False,
      **llama_kwargs,
    )

    # Wrap with outlines for structured generation
    model = outlines.from_llamacpp(llm)

    prompt = (
      f"""Following these instructions: {system_prompt}. answer the users query: {user_prompt} """
    )

    logger.debug(f"Generating structured output: Model:{model_name}, Structure:{pydantic_model.__name__}, Context size: {n_ctx} Max tokens: {max_tokens}")

    # Generate structured output
    result = model(model_input=prompt, output_type=pydantic_model, max_tokens=max_tokens)

    logger.debug(f"Generated output: {result}")

    # Parse the JSON string into the Pydantic model
    if isinstance(result, str):
      # Repair any malformed/truncated JSON before validation
      try:
        repaired_json = repair_json(result)
        return pydantic_model.model_validate_json(repaired_json)
      except Exception as repair_error:
        logger.warning(f"JSON repair failed: {repair_error}, trying original")
        return pydantic_model.model_validate_json(result)
    return result

  except Exception as error:
    logger.error(f"Failed to generate structured output: {error}")
    raise
