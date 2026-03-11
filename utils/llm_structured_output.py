"""Utility for generating structured outputs using outlines and llama.cpp."""

import gc
import os
from typing import TypeVar

import outlines
from json_repair import repair_json
from langsmith import traceable
from llama_cpp import Llama
from loguru import logger
from pydantic import BaseModel

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
        model_name: GGUF model filename
        user_prompt: The user's query
        system_prompt: System instructions for the model
        pydantic_model: Pydantic model class defining the output schema
        model_path: Optional override for the models directory
        n_ctx: Context window size in tokens
        max_tokens: Maximum tokens to generate
        **llama_kwargs: Extra args forwarded to the Llama constructor

    Returns:
        Instance of pydantic_model with the structured response
    """
    try:
        full_path = _model_path(model_name, model_path)
        fds = _suppress_stderr()
        try:
            llm = Llama(
                model_path=full_path,
                n_ctx=n_ctx,
                max_tokens=max_tokens,
                verbose=False,
                **llama_kwargs,
            )
        finally:
            _restore_stderr(*fds)

        model = outlines.from_llamacpp(llm)
        prompt = f"Following these instructions: {system_prompt}. answer the users query: {user_prompt} "

        logger.debug(
            f"Generating structured output: Model:{model_name}, "
            f"Structure:{pydantic_model.__name__}, Context size: {n_ctx} Max tokens: {max_tokens}"
        )

        result = model(model_input=prompt, output_type=pydantic_model, max_tokens=max_tokens)
        logger.debug(f"Generated output: {result}")

        # Free the Llama instance immediately so GPU memory is available for the next model load
        del model
        del llm
        gc.collect()

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
