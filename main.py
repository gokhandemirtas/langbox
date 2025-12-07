import logging
import os
import time

from loguru import logger

start_time = time.time()
logger.debug("Booting...")
# Suppress Metal/GGML initialization logs - must be set before importing llama_cpp
os.environ["GGML_METAL_LOG_LEVEL"] = "0"
os.environ["GGML_LOG_LEVEL"] = "0"
os.environ["MODEL_PATH"] = "models/"
os.environ["MODEL_QWEN2.5"] = "qwen2.5-1.5b-instruct-fp16.gguf"
os.environ["MODEL_HERMES_2_PRO"] = "Hermes-2-Pro-Llama-3-8B-Q5_K_M.gguf"
os.environ["MODEL_LLAMA2_7B"] = "llama-2-7b-chat.Q3_K_M.gguf"
os.environ["MODEL_MISTRAL_7B"] = "mistral-7b-instruct-v0.2.Q3_K_L.gguf"
os.environ["MODEL_PHI3_MINI"] = "Phi-3-mini-4k-instruct-q4.gguf"
os.environ["MODEL_FINANCE_LLAMA"] = "Finance-Llama-8B-GGUF-q4_K_M.gguf"

# Reduce llama-cpp-python logging
logging.getLogger("llama_cpp").setLevel(logging.ERROR)

if __name__ == "__main__":
    import asyncio

    from agents.intent_classifier import run_intent_classifier
    logger.debug(f"Booting complete in {time.time() - start_time}s")
    asyncio.run(run_intent_classifier())