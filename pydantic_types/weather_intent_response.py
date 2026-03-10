from typing import Literal

from pydantic import BaseModel, Field


class WeatherIntentResponse(BaseModel):
  """Strict schema for weather intent classification."""

  location: str = Field(
    ..., description="City or location name, or 'UNKNOWN_LOCATION' if not identified"
  )
  period: Literal["CURRENT", "TODAY", "TOMORROW", "DAY_AFTER", "FORECAST"] = Field(
    ..., description="CURRENT for right now, TODAY for today only, TOMORROW for tomorrow only, DAY_AFTER for the day after tomorrow, FORECAST for all days or unspecified"
  )
