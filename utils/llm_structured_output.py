"""Utility for generating structured outputs using outlines and llama.cpp."""

import os

os.environ["GGML_METAL_LOG_LEVEL"] = "0"
os.environ["GGML_LOG_LEVEL"] = "0"

from typing import TypeVar

import outlines
from llama_cpp import Llama
from loguru import logger
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def generate_structured_output(
  model_name: str,
  user_prompt: str,
  system_prompt: str,
  pydantic_model: type[T],
  model_path: str | None = None,
  **llama_kwargs,
) -> T:
  """Generate structured output using outlines with llama.cpp backend.

  Args:
      model_name: Name of the model (e.g., MODEL_QWEN2.5 environment variable value)
      prompt_function: Function that takes a query string and returns a formatted prompt
      pydantic_model: Pydantic model class defining the expected output structure
      query: User query to process
      model_path: Optional path to models directory. Defaults to MODEL_PATH env var
      **llama_kwargs: Additional keyword arguments to pass to Llama constructor
          (e.g., n_ctx, n_gpu_layers, temperature, etc.)

  Returns:
      Instance of pydantic_model with the structured response

  Raises:
      Exception: If model initialization or inference fails

  Example:
      >>> from pydantic import BaseModel
      >>> class WeatherIntent(BaseModel):
      ...     location: str
      ...     period: str
      >>> def weather_prompt(query: str) -> str:
      ...     return f"Extract weather info from: {query}"
      >>> result = generate_structured_output(
      ...     model_name="qwen2.5-1.5b-instruct-fp16.gguf",
      ...     prompt_function=weather_prompt,
      ...     pydantic_model=WeatherIntent,
      ...     query="What's the weather in Seattle?",
      ...     n_ctx=8192,
      ...     n_gpu_layers=8
      ... )
  """
  if model_path is None:
    model_path = os.environ.get("MODEL_PATH", "models/")

  # Construct full model path
  full_model_path = os.path.join(model_path, model_name)

  try:
    # Initialize llama.cpp model
    llm = Llama(model_path=full_model_path, **llama_kwargs)

    # Wrap with outlines for structured generation
    model = outlines.from_llamacpp(llm)
    prompt = f"""
        System prompt: {system_prompt}
        Users query: {user_prompt}
    """

    logger.debug(f"Generating structured output with prompt: {prompt[:100]}...")

    # Generate structured output
    result = model(prompt, pydantic_model)

    logger.debug(f"Generated output: {result}")

    # Parse the JSON string into the Pydantic model
    if isinstance(result, str):
      return pydantic_model.model_validate_json(result)
    return result

  except Exception as e:
    logger.error(f"Failed to generate structured output: {e}")
    raise
