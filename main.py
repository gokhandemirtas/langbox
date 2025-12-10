import asyncio
import logging
import os
import time

from loguru import logger

from agents.intent_classifier import run_intent_classifier
from db.init import init

start_time = time.time()
logger.debug("Booting...")
# Suppress Metal/GGML initialization logs - must be set before importing llama_cpp
os.environ["GGML_METAL_LOG_LEVEL"] = "0"
os.environ["GGML_LOG_LEVEL"] = "0"

# Reduce llama-cpp-python logging
logging.getLogger("llama_cpp").setLevel(logging.ERROR)


async def main():
  await init()
  logger.debug(f"Booting complete in {time.time() - start_time}s")
  await run_intent_classifier()


if __name__ == "__main__":
  asyncio.run(main())
