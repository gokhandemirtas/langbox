from typing import Literal

from pydantic import BaseModel, Field


class ReminderIntentResponse(BaseModel):
  """Schema for reminder intent parsing from user queries."""

  type: str = Literal["REMINDER", "TIMER"]  # "REMINDER" or "TIMER"
  datetime: str = Field(
    default=""
  )  # Fuzzy-date string like "tomorrow 5pm", "in two weeks", "next monday"
  description: str = Field(default="")  # What to remind about
