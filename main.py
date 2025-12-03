import asyncio
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

async def main(debug: bool = False, emote: bool = False):

  import logging
  import time

  from loguru import logger
  start_time = time.time()
  logger.remove()
  logger.add(sys.stderr, level="DEBUG" if debug else "INFO")
  
  logger.debug("Booting...")

  from agents.intent_classifier import run_intent_classifier
  from commands import handle_command
  from daily_routines import run_daily_routines
  from db.init import init
  from skills.conversation.skill import enable_emote
  from skills.personalizer.skill import start_personalizer
  from skills.telegram import start_telegram_bot
  from skills.telegram.skill import enable_tts

  logging.getLogger("llama_cpp").setLevel(logging.ERROR)

  await init()

  if emote:
    enable_emote()
    logger.debug("Emote mode enabled")
  if "--speak" in sys.argv:
    enable_tts()
    logger.debug("Telegram TTS enabled")

  if "--journal" in sys.argv:
    from skills.journal import summarize_pending_journal
    await summarize_pending_journal()

  asyncio.create_task(start_telegram_bot())
  await start_personalizer()
  logger.debug(f"Booting complete in {time.time() - start_time:.2f}s")

  if "--track_camera" in sys.argv:
    from skills.camera_tracking.skill import start_tracking
    start_tracking()


  # Continuous conversation loop
  while True:
    try:
      user_input = (await asyncio.to_thread(input, "\n \nHow may I assist? \n \n")).strip()
      if not user_input:
        continue
      if user_input.startswith("/"):
        await handle_command(user_input)
        continue
      await run_intent_classifier(user_input)
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
  asyncio.run(main(debug="--debug" in sys.argv, emote="--emote" in sys.argv))
