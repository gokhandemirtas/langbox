from typing import Literal

from pydantic import BaseModel, Field


class WeatherIntentResponse(BaseModel):
  """Strict schema for weather intent classification."""

  location: str = Field(
    ..., description="City or location name, or 'UNKNOWN_LOCATION' if not identified"
  )
  period: Literal["CURRENT", "FORECAST"] = Field(..., description="Either CURRENT or FORECAST")
