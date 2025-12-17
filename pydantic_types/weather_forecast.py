from pydantic import BaseModel, Field


class WeatherForecast(BaseModel):
  """Complete weather forecast for a location with flattened structure."""

  location: str = Field(..., description="Location/city name")
  current_temperature: int = Field(..., description="Current temperature in Celsius")
  forecast: list[str] = Field(
    default_factory=list,
    description="List of daily forecasts as formatted strings"
  )
