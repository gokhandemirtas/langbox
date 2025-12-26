import os
from datetime import datetime

import fuzzydate as fd
import questionary
from loguru import logger

from db.schemas import Reminders
from prompts.reminder_prompt import reminderIntentPrompt
from pydantic_types.reminder_intent_response import ReminderIntentResponse
from utils.llm_structured_output import generate_structured_output


async def handle_reminder(query: str) -> str:
  """Handle timers and reminders.

  Timers: Kept in memory for short-term countdowns
  Reminders: Saved to database for future dates

  Args:
      query: The original user query

  Returns:
      Confirmation of timer/reminder action
  """
  logger.debug(f"⏰ ROUTE: REMINDER - Processing: {query}")

  # Parse the intent using structured output
  try:
    result = generate_structured_output(
      model_name=os.environ["MODEL_QWEN2.5"],
      user_prompt=query,
      system_prompt=reminderIntentPrompt,
      pydantic_model=ReminderIntentResponse,
      max_tokens=512,
      n_ctx=4096,
    )

    request_type = result.request_type
    reminder_date = result.reminder_date
    reminder_text = result.reminder_text

    logger.debug(f"Parsed - Type: {request_type}, Date: {reminder_date}, Text: {reminder_text}")

    if request_type == "REMINDER":
      # Check if reminder text is missing and prompt user
      if (
        not reminder_text
        or reminder_text.strip() == ""
        or reminder_text.lower().strip() in ["unknown", "not specified", "n/a"]
      ):
        reminder_text = await questionary.text("What is the reminder for?").ask_async()
        if not reminder_text or reminder_text.strip() == "":
          return "Reminder cancelled - no description provided."

      # Check if reminder date is missing and prompt user
      if (
        not reminder_date
        or reminder_date.strip() == ""
        or reminder_date.lower().strip() in ["unknown", "not specified", "n/a"]
      ):
        date_input = await questionary.text(
          "When do you want this reminder? (e.g., tomorrow 2pm, next Monday 14:00, 2025-12-30)"
        ).ask_async()
        if not date_input or date_input.strip() == "":
          return "Reminder cancelled - no date provided."

        # Parse the date using fuzzy-date library
        try:
          parsed_date = fd.to_datetime(date_input)

          if parsed_date:
            reminder_date = parsed_date.isoformat()
            logger.debug(f"Parsed date '{date_input}' to '{reminder_date}'")
          else:
            logger.warning(f"Could not parse date: {date_input}")
            return "Could not understand the date format. Please try again."
        except Exception as e:
          logger.error(f"Date parsing error for '{date_input}': {e}")
          return "Could not understand the date format. Please try again."
      # Save reminder to database
      try:
        # Convert ISO string to datetime object (reminder_date is like "2025-12-30T14:00:00")
        reminder_datetime_obj = datetime.fromisoformat(reminder_date)
        new_reminder = Reminders(
          reminder_datetime=reminder_datetime_obj,
          reminder_text=reminder_text,
          created_at=datetime.now().date(),
          is_completed=False,
        )
        await new_reminder.insert()

        # Format display time
        display_time = reminder_datetime_obj.strftime("%Y-%m-%d %H:%M")
        logger.debug(f"Reminder saved to database: {reminder_text} at {display_time}")
        return f"Reminder set for {display_time}: {reminder_text}"

      except ValueError as e:
        logger.error(f"Failed to parse date: {e}")
        return "Could not parse the date. Please specify a valid date."

    elif request_type == "TIMER":
      # Handle timer (in-memory, not persisted)
      logger.debug(f"Timer request: {reminder_text}")
      return f"Timer functionality is in development. Noted: {reminder_text}"

    else:
      return "Could not determine if this is a timer or reminder request."

  except Exception as e:
    logger.error(f"Failed to process timer/reminder: {e}")
    return "Sorry, I couldn't process that timer or reminder request."
