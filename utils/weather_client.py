import python_weather

from pydantic_types.weather_forecast import DailyForecast, WeatherForecast


async def fetch_weather_forecast(location: str) -> WeatherForecast:
  """Fetch weather forecast for a location.

  Args:
      location: City or location name

  Returns:
      WeatherForecast: Structured weather forecast data
  """
  async with python_weather.Client(unit=python_weather.METRIC) as client:
    # Fetch a weather forecast from a city.
    weather = await client.get(location)

    daily_forecasts = []

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

      daily_forecast = DailyForecast(
        date=daily.date.strftime("%Y-%m-%d"),
        average_temperature=daily.temperature,
        hourly_forecasts=hourly_forecasts,
      )
      daily_forecasts.append(daily_forecast)

    return WeatherForecast(
      location=location,
      current_temperature=weather.temperature,
      daily_forecasts=daily_forecasts,
    )
