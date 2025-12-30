from typing import Literal

from pydantic import BaseModel, Field


class ReminderIntentResponse(BaseModel):
  """Schema for reminder intent parsing from user queries."""

  type: Literal["REMINDER", "TIMER", "LIST"] = "REMINDER"  # "REMINDER", "TIMER", or "LIST"
  datetime: str = Field(
    default=""
  )  # Human readable date string like "tomorrow 5pm", "in two weeks", "next monday", or "today"
  description: str = Field(default="")  # What to remind about
