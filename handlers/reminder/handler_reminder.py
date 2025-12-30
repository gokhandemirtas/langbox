import os
from datetime import datetime

import questionary
from loguru import logger

from db.schemas import Reminders
from prompts.reminder_prompt import reminderIntentPrompt
from pydantic_types.reminder_intent_response import ReminderIntentResponse
from utils.llm_structured_output import generate_structured_output
from utils.reminder_parser import format_reminder_display, parse_reminder_date


def _classify_intent(query: str) -> dict:
  """Classify user intent and extract reminder information.

  Args:
      query: The user's reminder query

  Returns:
      Dictionary with keys: type, datetime, description

  Example:
      >>> _classify_intent("Remind me tomorrow to call mom")
      {"type": "REMINDER", "datetime": "tomorrow", "description": "call mom"}
  """
  try:
    result = generate_structured_output(
      model_name=os.environ["MODEL_QWEN3"],
      user_prompt=query,
      system_prompt=reminderIntentPrompt,
      pydantic_model=ReminderIntentResponse,
      n_ctx=4096,
      max_tokens=256,
      temperature=0.0,
      repeat_penalty=1.15,
      top_p=0.95,
      top_k=40,
      n_gpu_layers=8,
    )

    return result.model_dump()

  except Exception as e:
    logger.error(f"Failed to classify reminder intent. Error: {e}")
    return {"type": "REMINDER", "datetime": "", "description": ""}


async def _save_reminder(datetime_str: str, description: str) -> str:
  """Parse datetime and save reminder to database.

  Args:
      datetime_str: Fuzzy-date string (e.g., "tomorrow 2pm")
      description: What to remind about

  Returns:
      Success message with formatted datetime
  """
  # Parse the fuzzy-date string
  parsed_datetime = parse_reminder_date(datetime_str)
  if not parsed_datetime:
    return f"Could not understand the date/time: '{datetime_str}'. Please try again."

  # Save to database
  try:
    new_reminder = Reminders(
      reminder_datetime=parsed_datetime,
      description=description,
      created_at=datetime.now().date(),
      is_completed=False,
    )
    await new_reminder.insert()

    # Format display time
    display_time = format_reminder_display(parsed_datetime)
    logger.debug(f"Reminder saved to database: {description} at {display_time}")
    return f"Reminder set for {display_time}: {description}"

  except Exception as e:
    logger.error(f"Failed to save reminder: {e}")
    return "Failed to save reminder. Please try again."


async def handle_reminder(query: str) -> str:
  """Handle timers and reminders.

  Timers: Kept in memory for short-term countdowns
  Reminders: Saved to database for future dates

  Args:
      query: The original user query

  Returns:
      Confirmation of timer/reminder action
  """
  logger.debug(f"REMINDER - Processing: {query}")

  # Classify intent to extract type, datetime, and description
  intent = _classify_intent(query)
  reminder_type = intent.get("type")
  datetime_str = intent.get("datetime", "")
  description = intent.get("description", "")

  if reminder_type and datetime_str and description:
    logger.debug(
      f"Parsed - Type: {reminder_type}, DateTime: '{datetime_str}', Description: '{description}'"
    )

  # Handle TIMER requests
  if reminder_type == "TIMER":
    logger.debug(f"Timer request: {description}")
    return f"Timer functionality is in development. Noted: {description}"

  # Handle REMINDER requests
  if reminder_type == "REMINDER":
    # Prompt for description if missing
    if not description or description.strip() == "":
      description = await questionary.text("What is the reminder for?").ask_async()
      if not description or description.strip() == "":
        return "Reminder cancelled - no description provided."

    # Prompt for datetime if missing
    if not datetime_str or datetime_str.strip() == "":
      datetime_str = await questionary.text(
        "When do you want this reminder? (e.g., tomorrow 2pm, next Monday 3pm, in two weeks)"
      ).ask_async()
      if not datetime_str or datetime_str.strip() == "":
        return "Reminder cancelled - no date provided."

    # Save reminder using helper function
    return await _save_reminder(datetime_str, description)

  # Unknown request type
  return "Could not determine if this is a timer or reminder request."
