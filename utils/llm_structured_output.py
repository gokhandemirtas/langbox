"""
Dispatcher for structured output generation.

Routes to either llama-cpp-python or MLX backend based on LANGBOX_LLM_BACKEND env var.
"""

import os

_backend = os.environ.get("LANGBOX_LLM_BACKEND", "llamacpp")

if _backend == "mlx":
  from utils.llm_structured_output_mlx import generate_structured_output
else:
  from utils.llm_structured_output_llamacpp import generate_structured_output

__all__ = ["generate_structured_output"]
