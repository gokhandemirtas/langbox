import asyncio

import python_weather

from pydantic_types.weather_forecast import WeatherForecast

TIMEOUT_SECONDS = 30


async def fetch_weather_forecast(location: str) -> WeatherForecast:
  """Fetch weather forecast for a location.

  Args:
      location: City or location name

  Returns:
      WeatherForecast: Structured weather forecast data with flattened structure

  Raises:
      asyncio.TimeoutError: If the request exceeds TIMEOUT_SECONDS
      Exception: If the weather fetch fails
  """
  return await asyncio.wait_for(_fetch(location), timeout=TIMEOUT_SECONDS)


async def _fetch(location: str) -> WeatherForecast:
  """Internal fetch logic."""
  async with python_weather.Client(unit=python_weather.METRIC) as client:
    try:
      weather = await client.get(location)

      forecast = []
    except Exception as e:
      return e

    # Fetch weather forecast for upcoming days.
    for daily in weather:
      hourly_forecasts = []

      # Each daily forecast has their own hourly forecasts.
      # Format: "HH:MM-HH:MM, XX °C, description, condition"
      for hourly in daily:
        time_start = hourly.time.strftime("%H:%M")
        # Calculate end time (1 hour later)
        hour_end = (hourly.time.hour + 1) % 24
        time_end = f"{hour_end:02d}:00"

        condition = str(hourly.kind).replace("Kind.", "")
        hourly_str = (
          f"{time_start}-{time_end}, {hourly.temperature} °C, {hourly.description}, {condition}"
        )
        hourly_forecasts.append(hourly_str)

      # Format each daily forecast as a string
      date_str = daily.date.strftime("%Y-%m-%d")
      hourly_str = ", ".join(hourly_forecasts)
      daily_str = f"{date_str}, avg temp: {daily.temperature} °C, hourly: {hourly_str}"
      forecast.append(daily_str)

    return WeatherForecast(
      location=location,
      current_temperature=weather.temperature,
      forecast=forecast,
    )
