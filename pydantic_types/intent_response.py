from typing import Literal

from pydantic import BaseModel, Field


class IntentResponse(BaseModel):
  """Strict schema for intent classification. Constrains output to valid intent categories."""

  intent: Literal[
    "HOME_CONTROL",
    "WEATHER",
    "FINANCE_STOCKS",
    "TRANSPORTATION",
    "REMINDER",
    "NEWSFEED",
    "INFORMATION_QUERY",
    "GREETING",
  ] = Field(..., description="The classified intent category")
