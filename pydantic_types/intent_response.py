from typing import Literal

from pydantic import BaseModel, Field

IntentLiteral = Literal[
  "HOME_CONTROL",
  "WEATHER",
  "FINANCE_STOCKS",
  "TRANSPORTATION",
  "REMINDER",
  "NEWSFEED",
  "INFORMATION_QUERY",
  "NOTES",
  "SEARCH",
  "SPOTIFY",
  "CHAT",
]


class IntentResponse(BaseModel):
  """Strict schema for intent classification. Constrains output to a single valid intent category."""

  intent: IntentLiteral = Field(..., description="The classified intent category")
