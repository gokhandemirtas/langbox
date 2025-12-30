"""Handler for listing today's reminders."""

from datetime import datetime, time

from loguru import logger

from db.schemas import Reminders


async def handle_list_reminders() -> str:
  """List all reminders scheduled for today.

  Returns:
      Formatted string with today's reminders or message if none found
  """
  try:
    # Get today's date range (start and end of day)
    today = datetime.now().date()
    start_of_day = datetime.combine(today, time.min)
    end_of_day = datetime.combine(today, time.max)

    # Query reminders for today that aren't completed
    reminders = await Reminders.find(
      Reminders.reminder_datetime >= start_of_day,
      Reminders.reminder_datetime <= end_of_day,
      Reminders.is_completed == False,
    ).to_list()

    if not reminders:
      return "You have no reminders scheduled for today."

    # Format the reminders list
    reminder_lines = []
    for idx, reminder in enumerate(reminders, 1):
      time_str = reminder.reminder_datetime.strftime("%I:%M %p")
      reminder_lines.append(f"{idx}. {time_str} - {reminder.description}")

    result = "Your reminders for today:\n" + "\n".join(reminder_lines)
    logger.debug(f"Found {len(reminders)} reminders for today")
    return result

  except Exception as e:
    logger.error(f"Failed to list reminders: {e}")
    return "Failed to retrieve reminders. Please try again."
