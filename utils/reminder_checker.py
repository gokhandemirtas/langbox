"""Utility for checking daily reminders from the database."""

from datetime import datetime

from loguru import logger

from db.schemas import Reminders


async def check_daily_reminders() -> list[str]:
  """Check for reminders scheduled for today.

  Returns:
      List of formatted reminder strings with time information
  """
  today = datetime.now().date()
  logger.debug(f"Checking reminders for {today}")

  try:
    # Find all incomplete reminders for today (by date component)
    all_reminders = await Reminders.find(
      Reminders.is_completed == False  # noqa: E712
    ).to_list()

    # Filter by today's date
    today_reminders = [
      r for r in all_reminders if r.reminder_datetime.date() == today
    ]

    if not today_reminders:
      logger.debug("No reminders for today")
      return []

    # Format reminders with time information
    reminder_texts = []
    for reminder in today_reminders:
      time_str = reminder.reminder_datetime.strftime("%H:%M")
      if reminder.reminder_end_time:
        end_time_str = reminder.reminder_end_time.strftime("%H:%M")
        formatted = f"[{time_str}-{end_time_str}] {reminder.description}"
      else:
        formatted = f"[{time_str}] {reminder.description}"
      reminder_texts.append(formatted)

    logger.info(f"Found {len(reminder_texts)} reminder(s) for today")
    return reminder_texts

  except Exception as e:
    logger.error(f"Failed to check daily reminders: {e}")
    return []


async def mark_reminder_completed(reminder_text: str) -> bool:
  """Mark a reminder as completed.

  Args:
      reminder_text: The text of the reminder to mark as completed

  Returns:
      True if successful, False otherwise
  """
  try:
    today = datetime.now().date()
    # Find all reminders for today
    all_reminders = await Reminders.find(
      Reminders.is_completed == False  # noqa: E712
    ).to_list()

    # Filter by today and matching text
    for reminder in all_reminders:
      if reminder.reminder_datetime.date() == today and reminder.description == reminder_text:
        reminder.is_completed = True
        await reminder.save()
        logger.debug(f"Marked reminder as completed: {reminder_text}")
        return True

    logger.warning(f"Reminder not found: {reminder_text}")
    return False

  except Exception as e:
    logger.error(f"Failed to mark reminder as completed: {e}")
    return False
