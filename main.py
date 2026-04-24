import asyncio
import os
import sys

from rich.console import Console

from agents.intent_classifier import run_intent_classifier
from api.server import start_api_server
from commands import cmd_save, handle_command
from db.init import db_init
from skills.conversation.skill import enable_emote
from skills.personalizer.skill import start_personalizer
from skills.telegram import start_telegram_bot
from skills.telegram.skill import enable_tts

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

  from utils.log import logger, set_level
  set_level(debug)
  start_time = time.time()

  logger.info("Booting, please wait")

  logging.getLogger("llama_cpp").setLevel(logging.ERROR)

  db_init_log = await db_init()

  if emote:
    enable_emote()
    logger.debug("Emote mode enabled")
  if "--speak" in sys.argv:
    enable_tts()
    logger.debug("TTS enabled")

  if "--track_camera" in sys.argv:
    from skills.camera_tracking.skill import start_tracking
    start_tracking()

  if "--server" in sys.argv:
    await start_api_server()
  
  personalizer_log = await start_personalizer()

  from llama_cpp import llama_supports_gpu_offload
  from pynvml import (
      nvmlDeviceGetHandleByIndex,
      nvmlDeviceGetMemoryInfo,
      nvmlDeviceGetName,
      nvmlInit,
  )
  from rich import box
  from rich.table import Table
  nvmlInit()
  _gpu = nvmlDeviceGetHandleByIndex(0)
  gpu_name = nvmlDeviceGetName(_gpu)
  gpu_vram = nvmlDeviceGetMemoryInfo(_gpu).total // 1024 ** 2

  with SuppressStderr():
    gpu_offload = llama_supports_gpu_offload()
  boot_time = time.time() - start_time

  from agents.persona import get_active_persona_id, get_active_voice_id, get_active_name

  table = Table(show_header=True, box=box.HEAVY, show_lines=True, padding=(0, 2))
  table.add_column("Action", style="bold cyan")
  table.add_column("Result")
  table.add_row("Model", os.environ.get("MODEL_GENERALIST", "unknown"))
  table.add_row("GPU", f"{gpu_name} ({gpu_vram:,} MiB), [green]GPU offload[/green]" if gpu_offload else "[red]CPU only[/red]")
  table.add_row("Persona", f"{get_active_name()} ({get_active_persona_id()})")
  table.add_row("Voice", get_active_voice_id() or "[dim]default[/dim]")
  table.add_row("Debug", "on" if debug else "off")
  table.add_row("Personalizer", personalizer_log)
  table.add_row("Database", db_init_log)
  if "--telegram" in sys.argv:
    telegram_log = await start_telegram_bot()
    table.add_row("Telegram", telegram_log)
  
  table.add_row("Boot time", f"{boot_time:.2f}s")
  console = Console(stderr=True, force_terminal=True)
  console.print(table)

  # Opening greeting
  from skills.conversation.skill import generate_greeting
  greeting = await generate_greeting()
  console.print(f"\n[green]{greeting}[/green]")

  # Continuous conversation loop
  while True:
    try:
      user_input = (await asyncio.to_thread(console.input, "❯ ")).strip()
      if not user_input:
        continue
      if user_input.startswith("/"):
        await handle_command(user_input)
        continue
      await run_intent_classifier(user_input)
    except KeyboardInterrupt:
      await cmd_save()
      console.print("\n\nGoodbye! Have a great day!")
      break
    except EOFError:
      console.print("\n\nGoodbye! Have a great day!")
      break
    except Exception as e:
      logger.error(f"An error occurred: {e}")
      print("\nSorry, I encountered an error. Let's try again.\n")


if __name__ == "__main__":
  import asyncio
  asyncio.run(main(debug="--debug" in sys.argv, emote="--emote" in sys.argv))
