from pydantic import BaseModel, Field


class DailyForecast(BaseModel):
  """Daily weather forecast with hourly breakdowns."""

  date: str = Field(..., description="Date in YYYY-MM-DD format")
  average_temperature: int = Field(..., description="Average temperature for the day in Celsius")
  hourly_forecasts: list[str] = Field(
    default_factory=list,
    description="List of hourly forecasts in format 'HH:MM-HH:MM, XX °C, description, condition'",
  )


class WeatherForecast(BaseModel):
  """Complete weather forecast for a location."""

  location: str = Field(..., description="Location/city name")
  current_temperature: int = Field(..., description="Current temperature in Celsius")
  daily_forecasts: list[DailyForecast] = Field(
    default_factory=list, description="List of daily forecasts for upcoming days"
  )
