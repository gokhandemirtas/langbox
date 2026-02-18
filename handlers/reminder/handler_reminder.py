import os

from loguru import logger

from handlers.reminder.handler_create import handle_create_reminder
from handlers.reminder.handler_list import handle_list_reminders
from handlers.reminder.handler_timer import handle_timer
from prompts.reminder_prompt import reminderIntentPrompt
from pydantic_types.reminder_intent_response import ReminderIntentResponse
from utils.llm_structured_output import generate_structured_output


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
      model_name=os.environ["MODEL_QWEN2.5"],
      user_prompt=query,
      system_prompt=reminderIntentPrompt,
      pydantic_model=ReminderIntentResponse,
      n_ctx=4096,
      max_tokens=256,
      temperature=0.0,
      repeat_penalty=1.15,
      top_p=0.95,
      top_k=40,
      n_gpu_layers=-1,
    )

    return result.model_dump()

  except Exception as e:
    logger.error(f"Failed to classify reminder intent. Error: {e}")
    return e


async def handle_reminder(query: str) -> str:
  """Handle timers and reminders.

  Timers: Kept in memory for short-term countdowns
  Reminders: Saved to database for future dates

  Args:
      query: The original user query

  Returns:
      Confirmation of timer/reminder action
  """

  # Classify intent to extract type, datetime, and description
  intent = _classify_intent(query)
  reminder_type = intent.get("type")
  datetime_str = intent.get("datetime", "")
  description = intent.get("description", "")

  if reminder_type:
    logger.debug(
      f"""Detected secondary intent,
      Type: {reminder_type}\n
      DateTime: '{datetime_str}'\n
      Description: '{description}'"""
    )

    # Route based on reminder type
    match reminder_type:
      case "LIST":
        logger.debug("Listing today's reminders")
        return await handle_list_reminders()

      case "TIMER":
        if datetime_str and description:
          logger.debug(f"Timer request: {description}")
          return await handle_timer(datetime_str, description)
        else:
          logger.error("Date or description missing from TIMER request")
          return "Date or description missing"

      case "REMINDER":
        if datetime_str and description:
          logger.debug(f"Creating reminder: {datetime_str} - {description}")
          return await handle_create_reminder(datetime_str, description)
        else:
          logger.error("Date or description missing from CREATE REMINDER request")
          return "Date or description missing"

      case _:
        return "Could not determine if this is a timer or reminder request."
