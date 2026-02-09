"""Handler for timer functionality.

Timers are kept in memory using asyncio tasks.
When a timer expires, it prints the description to the console.
"""

import asyncio
import time

from loguru import logger

from utils.reminder_parser import parse_time

# In-memory store of active timers
_active_timers: dict[str, asyncio.Task] = {}


async def _timer_callback(timer_id: str, description: str, delay_seconds: float):
  """Wait for the specified delay, then print the timer description.

  Args:
      timer_id: Unique identifier for this timer
      description: What to remind about when the timer fires
      delay_seconds: Seconds to wait before firing
  """
  try:
    await asyncio.sleep(delay_seconds)
    print(f"\n⏰ Timer: {description}\n")
    logger.info(f"Timer fired: {description}")
  except asyncio.CancelledError:
    logger.debug(f"Timer cancelled: {description}")
  finally:
    _active_timers.pop(timer_id, None)


async def handle_timer(datetime_str: str, description: str) -> str:
  """Create an in-memory timer that prints the description when it expires.

  Args:
      datetime_str: Natural language duration (e.g., "in 5 minutes", "in 30 seconds")
      description: What to remind about when the timer fires

  Returns:
      Confirmation message
  """
  logger.debug(f"Timer request: '{description}' at '{datetime_str}'")

  delay_seconds = parse_time(datetime_str)
  if not delay_seconds:
    return f"Could not understand the timer duration: '{datetime_str}'"

  delay_seconds = int(delay_seconds)

  if delay_seconds <= 0:
    return "The specified time is in the past. Please set a future time for the timer."

  timer_id = f"timer_{int(time.time())}_{description[:20]}"
  task = asyncio.create_task(_timer_callback(timer_id, description, delay_seconds))
  _active_timers[timer_id] = task

  # Format a human-readable duration
  minutes, seconds = divmod(int(delay_seconds), 60)
  hours, minutes = divmod(minutes, 60)
  parts = []
  if hours:
    parts.append(f"{hours}h")
  if minutes:
    parts.append(f"{minutes}m")
  if seconds or not parts:
    parts.append(f"{seconds}s")
  duration_str = " ".join(parts)

  return f"Timer set for {duration_str}: {description}"
