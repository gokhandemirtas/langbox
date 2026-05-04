"""Agent factory for creating LLM instances.

Routes to either llama-cpp-python or MLX backend based on LANGBOX_LLM_BACKEND env var.
"""

import multiprocessing
import os
from typing import Optional

from langchain.agents import create_agent
from utils.log import logger

_backend = os.environ.get("LANGBOX_LLM_BACKEND", "llamacpp")

# Import backend-specific helpers
if _backend == "mlx":
  from utils.llm_structured_output_mlx import _get_or_load_mlx, _model_path
else:
  from langchain_community.chat_models import ChatLlamaCpp
  from utils.llm_structured_output_llamacpp import _get_or_load_llama, _model_path

_chat_llm_instance = None


class MLXChatWrapper:
  """
  Wrapper around MLX model to provide a LangChain-compatible interface.

  Implements the minimal interface needed by the reasoning engine:
  - ainvoke(messages) -> response with .content attribute
  """

  def __init__(
    self,
    model,
    tokenizer,
    temperature: float = 0.5,
    max_tokens: int = 1024,
    **kwargs
  ):
    self.model = model
    self.tokenizer = tokenizer
    self.temperature = temperature
    self.max_tokens = max_tokens
    self.kwargs = kwargs

  def invoke(self, messages: list):
    """Sync invoke - convert LangChain messages to MLX prompt and generate."""
    # Convert LangChain messages to a single prompt string
    prompt_parts = []
    for msg in messages:
      role = msg.__class__.__name__
      content = msg.content

      if "System" in role:
        prompt_parts.append(f"System: {content}")
      elif "Human" in role:
        prompt_parts.append(f"User: {content}")
      elif "AI" in role:
        prompt_parts.append(f"Assistant: {content}")

    prompt = "\n\n".join(prompt_parts) + "\n\nAssistant:"

    # Generate synchronously
    response_text = self._generate_sync(prompt)

    # Return object with .content attribute (like LangChain responses)
    class Response:
      def __init__(self, content):
        self.content = content

    return Response(response_text)

  async def ainvoke(self, messages: list):
    """Async invoke - convert LangChain messages to MLX prompt and generate."""
    # Convert LangChain messages to a single prompt string
    prompt_parts = []
    for msg in messages:
      role = msg.__class__.__name__
      content = msg.content

      if "System" in role:
        prompt_parts.append(f"System: {content}")
      elif "Human" in role:
        prompt_parts.append(f"User: {content}")
      elif "AI" in role:
        prompt_parts.append(f"Assistant: {content}")

    prompt = "\n\n".join(prompt_parts) + "\n\nAssistant:"

    # MLX has thread-local streams, so we must run generation in the same thread
    # Running synchronously is fine - MLX is already optimized and fast
    response_text = self._generate_sync(prompt)

    # Return object with .content attribute (like LangChain responses)
    class Response:
      def __init__(self, content):
        self.content = content

    return Response(response_text)

  def _generate_sync(self, prompt: str) -> str:
    """Synchronous MLX generation."""
    try:
      import mlx_lm
      from mlx_lm.sample_utils import make_sampler
    except ImportError:
      raise ImportError(
        "mlx-lm is required for MLX inference. Install with: uv pip install mlx-lm"
      )

    # Create a sampler with the desired temperature
    # MLX requires using make_sampler(temp=...) rather than passing temp directly
    sampler = make_sampler(temp=self.temperature)

    response = mlx_lm.generate(
      self.model,
      self.tokenizer,
      prompt=prompt,
      max_tokens=self.max_tokens,
      sampler=sampler,
      **self.kwargs
    )

    return response


def create_llm(
    model_name: Optional[str] = None,
    temperature: float = 0.5,
    n_gpu_layers: int = -1,
    n_batch: int = 2048,
    max_tokens: int | None = None,
    repeat_penalty: float = 1.5,
    top_p: float = 0.95,
    top_k: int = 40,
    echo: bool = False,
    verbose: bool = False,
    n_threads: Optional[int] = None,
):
    """
    Create an LLM instance for the configured backend.

    Returns:
      - ChatLlamaCpp instance if backend is llamacpp
      - MLXChatWrapper instance if backend is mlx
    """
    global _chat_llm_instance

    if model_name is None:
        model_name = os.environ.get("MODEL_GENERALIST")

    if _chat_llm_instance is not None:
        return _chat_llm_instance

    effective_max_tokens = max_tokens or int(os.environ.get("MODEL_MAX_TOKENS", 1024))

    if _backend == "mlx":
        # MLX backend
        full_path = _model_path(model_name)
        model, tokenizer = _get_or_load_mlx(model_name, full_path)

        llm = MLXChatWrapper(
            model=model,
            tokenizer=tokenizer,
            temperature=temperature,
            max_tokens=effective_max_tokens,
        )

        if verbose:
            logger.debug(f"[mlx] Created chat wrapper for {model_name}")

    else:
        # llama.cpp backend
        if n_threads is None:
            n_threads = multiprocessing.cpu_count() - 1

        n_ctx = int(os.environ.get("MODEL_CTX", 8192))
        full_path = _model_path(model_name)
        llama_instance = _get_or_load_llama(model_name, full_path, n_gpu_layers, {})

        llm = ChatLlamaCpp.model_construct(
            model_path=full_path,
            client=llama_instance,
            temperature=temperature,
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
            n_batch=n_batch,
            max_tokens=effective_max_tokens,
            repeat_penalty=repeat_penalty,
            top_p=top_p,
            top_k=top_k,
            echo=echo,
            n_threads=n_threads,
            verbose=verbose,
        )

    _chat_llm_instance = llm
    return llm


def create_llm_agent(
    model_name: Optional[str] = None,
    temperature: float = 0.5,
    n_gpu_layers: int = -1,
    n_batch: int = 2048,
    max_tokens: int | None = None,
    repeat_penalty: float = 1.5,
    top_p: float = 0.95,
    top_k: int = 40,
    echo: bool = False,
    verbose: bool = False,
    n_threads: Optional[int] = None,
    checkpointer=None,
    **agent_kwargs,
):
    """
    Create a LangGraph agent.

    NOTE: LangGraph agents are only supported with llama.cpp backend.
    For MLX, this will raise NotImplementedError.
    """
    if _backend == "mlx":
        raise NotImplementedError(
            "LangGraph agents are not yet supported with MLX backend. "
            "For basic LLM usage, use create_llm() instead, or switch to llama-cpp backend."
        )

    llm = create_llm(
        model_name=model_name,
        temperature=temperature,
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
    return agent
