import os
import sys

# Suppress GGML/llama.cpp initialization logs - MUST be set before ANY imports that use llama_cpp
os.environ["GGML_METAL_LOG_LEVEL"] = "0"
os.environ["GGML_LOG_LEVEL"] = "0"
os.environ["LLAMA_CPP_LOG_LEVEL"] = "0"


# Redirect stderr at the OS file descriptor level to suppress C/C++ level logs
class SuppressStderr:
    def __enter__(self):
        self.old_fd = os.dup(2)
        self.devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(self.devnull, 2)
        return self

    def __exit__(self, *args):
        os.dup2(self.old_fd, 2)
        os.close(self.old_fd)
        os.close(self.devnull)


async def main():

  import logging
  import time

  from loguru import logger

  from agents.intent_classifier import run_intent_classifier
  from daily_routines import run_daily_routines
  from db.init import init

  logging.getLogger("llama_cpp").setLevel(logging.ERROR)
  start_time = time.time()
  logger.debug("Booting...")

  await init()
  logger.debug(f"Booting complete in {time.time() - start_time:.2f}s")

  # Run daily routines (reminders, weather, etc.)
  daily_updates = await run_daily_routines()

  # Process daily updates through conversational handler
  if daily_updates:
    logger.info(daily_updates)

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
  import asyncio
  asyncio.run(main())
