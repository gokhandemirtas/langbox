#!/usr/bin/env python3
"""Daily routines - runs morning briefing with reminders, weather, etc.

Can be called from main.py or run as standalone script:
    Standalone: uv run python daily_routines.py
    From main: imported and called by main.py at startup
"""

import asyncio
import os
import sys

# Suppress Metal/GGML initialization logs
os.environ["GGML_METAL_LOG_LEVEL"] = "0"
os.environ["GGML_LOG_LEVEL"] = "0"
os.environ["LLAMA_CPP_LOG_LEVEL"] = "0"

from datetime import datetime

from loguru import logger

from handlers.reminder.handler_list import handle_list_reminders
from handlers.weather.handler_weather import query_weather


async def run_daily_routines() -> str:
  """Execute all daily routines and return combined updates as a single paragraph.

  Note: Database must be initialized before calling this function.

  Returns:
      String containing all daily updates (reminders, weather, etc.) to be processed by LLM
  """

  logger.debug(f"📅 DAILY BRIEFING - {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}")

  updates = []

  # ==================== ROUTINE 1: List Today's Reminders ====================
  try:
    reminders_response = await handle_list_reminders()
    updates.append(f"REMINDERS: {reminders_response}")
    logger.debug("✓ Reminders collected")
  except Exception as e:
    logger.error(f"Failed to get reminders: {e}")
    updates.append("REMINDERS: Failed to retrieve reminders")

  # ==================== ROUTINE 2: Check Weather for London ====================
  try:
    weather_data = await query_weather(location="London", period="CURRENT")
    today = weather_data.get("today", {})

    # Format weather output
    location = today.get("location", "London")
    temp = today.get("current_temperature", "N/A")

    weather_info = (
      f"WEATHER in {location}: Current temperature is {temp}°C."
    )
    updates.append(weather_info)
    logger.debug("✓ Weather collected")

  except Exception as e:
    logger.error(f"Failed to get weather: {e}")
    updates.append("WEATHER: Failed to retrieve weather information")

  # ==================== ROUTINE 3: Placeholder for Future Routines ====================
  # TODO: Add more routines here as needed
  # Examples:
  # - Check calendar appointments
  # - News briefing
  # - Stock market summary
  # - System health checks
  # - Upcoming birthdays/anniversaries

  # Combine all updates into a single paragraph
  combined_updates = " ".join(updates)
  logger.debug(f"✓ Daily routines complete, returning {len(updates)} updates")

  return combined_updates


async def main():
  """Main entry point when running as standalone script."""
  from db.init import init

  # Initialize database connection
  await init()

  # Run daily routines
  result = await run_daily_routines()

  # Display the result
  logger.debug("\n" + "=" * 70)
  logger.debug("DAILY BRIEFING RAW OUTPUT")
  logger.debug("=" * 70)
  logger.debug(result)
  logger.debug("=" * 70 + "\n")


if __name__ == "__main__":
  try:
    asyncio.run(main())
  except KeyboardInterrupt:
    logger.debug("\n\n⚠️  Daily routines interrupted by user")
    sys.exit(0)
  except Exception as e:
    logger.error(f"Daily routines failed: {e}")
    logger.debug(f"\n❌ Daily routines failed: {e}")
    sys.exit(1)
