from pydantic import BaseModel, Field


class ReminderIntentResponse(BaseModel):
  """Schema for reminder intent parsing from user queries."""

  request_type: str = Field(default="REMINDER")  # "REMINDER" or "TIMER"
  reminder_date: str = Field(default="UNKNOWN")  # ISO date format YYYY-MM-DD or "UNKNOWN"
  reminder_text: str = Field(default="UNKNOWN")  # What to remind about or "UNKNOWN"
