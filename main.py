import logging
import os
import time

from loguru import logger

start_time = time.time()
logger.info("Booting...")
# Suppress Metal/GGML initialization logs - must be set before importing llama_cpp
os.environ["GGML_METAL_LOG_LEVEL"] = "0"
os.environ["GGML_LOG_LEVEL"] = "0"
os.environ["MODEL_PATH"] = "models/"
os.environ["MODEL_INTENT_CLASSIFIER"] = "qwen2.5-1.5b-instruct-fp16.gguf"
os.environ["MODEL_GENERAL_PURPOSE"] = "Hermes-2-Pro-Llama-3-8B-Q5_K_M.gguf"
os.environ["MODEL_CONVERSATIONAL"] = "Hermes-2-Pro-Llama-3-8B-Q5_K_M.gguf"
os.environ["MODEL_FINANCE"] = "Finance-Llama-8B-GGUF-q4_K_M.gguf"

# Reduce llama-cpp-python logging
logging.getLogger("llama_cpp").setLevel(logging.ERROR)

if __name__ == "__main__":
    from agents.intent_classifier import run_intent_classifier
    logger.info(f"Booting complete in {time.time() - start_time}s")
    run_intent_classifier()