import python_weather


async def fetch_weather_forecast(location):
  async with python_weather.Client(unit=python_weather.METRIC) as client:
    # Fetch a weather forecast from a city.
    weather = await client.get(location)

    # Format the data in a structured way
    formatted_data = {
      "location": location,
      "current_temperature": weather.temperature,
      "unit": "Celsius",
      "daily_forecasts": [],
    }

    # Fetch weather forecast for upcoming days.
    for daily in weather:
      daily_data = {
        "date": daily.date.strftime("%Y-%m-%d"),
        "average_temperature": daily.temperature,
        "hourly_forecasts": [],
      }

      # Each daily forecast has their own hourly forecasts.
      for hourly in daily:
        hourly_data = {
          "time": hourly.time.strftime("%H:%M"),
          "temperature": hourly.temperature,
          "description": hourly.description,
          "condition": str(hourly.kind).replace("Kind.", ""),
        }
        daily_data["hourly_forecasts"].append(hourly_data)

      formatted_data["daily_forecasts"].append(daily_data)

    return formatted_data
