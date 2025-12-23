import os
import sys

# Suppress Metal/GGML initialization logs - MUST be set before ANY imports that use llama_cpp
os.environ["GGML_METAL_LOG_LEVEL"] = "0"
os.environ["GGML_LOG_LEVEL"] = "0"
os.environ["LLAMA_CPP_LOG_LEVEL"] = "0"

# Redirect stderr temporarily to suppress C++ level logs
class SuppressStderr:
    def __enter__(self):
        self.null = open(os.devnull, 'w')
        self.old_stderr = sys.stderr
        sys.stderr = self.null
        return self

    def __exit__(self, *args):
        sys.stderr = self.old_stderr
        self.null.close()

import asyncio
import logging
import time

from loguru import logger

from agents.intent_classifier import run_intent_classifier
from db.init import init

start_time = time.time()
logger.debug("Booting...")

# Reduce llama-cpp-python logging
logging.getLogger("llama_cpp").setLevel(logging.ERROR)


async def main():
  await init()
  logger.debug(f"Booting complete in {time.time() - start_time}s")

  # Continuous conversation loop
  while True:
    try:
      await run_intent_classifier()
    except KeyboardInterrupt:
      print("\n\nGoodbye! Have a great day!")
      break
    except EOFError:
      print("\n\nGoodbye! Have a great day!")
      break
    except Exception as e:
      logger.error(f"An error occurred: {e}")
      print("\nSorry, I encountered an error. Let's try again.\n")


if __name__ == "__main__":
  asyncio.run(main())
