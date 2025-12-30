"""Handler for creating reminders."""

from datetime import datetime

import questionary
from loguru import logger

from db.schemas import Reminders
from utils.reminder_parser import format_reminder_display, parse_reminder_date


async def handle_create_reminder(datetime_str: str, description: str) -> str:
  """Create a new reminder.

  Args:
      datetime_str: Fuzzy-date string (e.g., "tomorrow 2pm")
      description: What to remind about

  Returns:
      Confirmation message with formatted datetime
  """
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
