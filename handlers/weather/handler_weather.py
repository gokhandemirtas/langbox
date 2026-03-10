import os
import re
from collections import Counter
from datetime import datetime
from loguru import logger

from db.schemas import Weather
from prompts.weather_prompt import weatherIntentPrompt
from pydantic_types.weather_intent_response import WeatherIntentResponse
from utils.llm_structured_output import generate_structured_output
from utils.weather_client import fetch_weather_forecast


def _get_condition(hourly_str: str) -> str:
  """Derive the dominant weather condition from the hourly string without LLM."""
  parts = [p.strip() for p in hourly_str.split(",")]
  # Each hourly entry is 3 parts: "HH:MM-HH:MM", "XX °C", "Description"
  descriptions = [parts[i] for i in range(2, len(parts), 3) if i < len(parts)]
  if not descriptions:
    return "conditions unknown"
  most_common = Counter(descriptions).most_common(1)[0][0]
  return most_common.lower()


def _parse_day(day_str: str) -> tuple[int, int, int, str]:
  """Extract avg/low/high temps and hourly portion from a forecast string."""
  avg = int(re.search(r'avg temp: (\d+)', day_str).group(1))
  low = int(re.search(r'low: (\d+)', day_str).group(1))
  high = int(re.search(r'high: (\d+)', day_str).group(1))
  hourly_start = day_str.find('hourly: ')
  hourly = day_str[hourly_start + 8:] if hourly_start != -1 else day_str
  return avg, low, high, hourly


def _format_weather_data(data: dict, period: str = "FORECAST") -> str:
  """Summarize each day's forecast and combine into a readable string."""
  today = data.get("today", {})
  location = today.get("location", "Unknown")
  current_temp = today.get("current_temperature", "?")
  forecast = today.get("forecast", [])

  day_labels = ["Today", "Tomorrow", "The day after tomorrow"]
  period_index = {"CURRENT": [0], "TODAY": [0], "TOMORROW": [1], "DAY_AFTER": [2]}
  indices = period_index.get(period, range(len(forecast)))

  lines = [f"Weather for {location}:", f"Current temperature: {current_temp}°C"]
  for i in indices:
    if i >= len(forecast):
      continue
    label = day_labels[i] if i < len(day_labels) else f"Day {i + 1}"
    avg, low, high, hourly = _parse_day(forecast[i])
    condition = _get_condition(hourly)
    lines.append(f"{label}: average {avg}°C, lows {low}°C and highs {high}°C with {condition}")

  return "\n".join(lines)


def _classify_intent(query: str) -> dict:
  """Classify user intent and extract location and time period.

  Args:
      query: The user's weather query

  Returns:
      Dictionary with keys: location, period

  Example:
      >>> _classify_intent("What's the weather in Seattle?")
      {"location": "Seattle", "period": "CURRENT"}
  """

  try:
    result = generate_structured_output(
      model_name=os.environ["MODEL_QWEN2.5"],
      user_prompt=query,
      system_prompt=weatherIntentPrompt,
      pydantic_model=WeatherIntentResponse,
    )

    location = result.location
    # Reject hallucinated locations: the city must actually appear in the query
    if location and location.lower() != "unknown_location" and location.lower() not in query.lower():
      logger.debug(f"Rejecting hallucinated location '{location}' not found in query")
      location = "UNKNOWN_LOCATION"

    return {"location": location, "period": result.period}

  except Exception as e:
    logger.error(f"Failed to generate structured output. Error: {e}")
    return {"location": "UNKNOWN_LOCATION", "period": "CURRENT"}


async def query_weather(location: str, period: str) -> dict:
  """Fetch weather data and format it for LLM consumption.

  Args:
      location: City/location name
      period: Either "CURRENT" or "FORECAST"

  Returns:
      Dictionary containing formatted weather data
  """

  datestamp = datetime.now().date()

  # Check if today's forecast exists for the location
  found = await Weather.find(Weather.datestamp == datestamp, Weather.location == location).to_list()
  if found:
    logger.debug(f"""Today's forecast found for {location} in DB""")
    today = found[0].model_dump(exclude={"id"})
  else:
    logger.debug(f"""Fetching new forecast for {location}""")
    weather_forecast = await fetch_weather_forecast(location)
    # Create new record with flattened structure
    newRecord = Weather(
      datestamp=datestamp,
      location=weather_forecast.location.lower(),
      current_temperature=weather_forecast.current_temperature,
      forecast=weather_forecast.forecast,
    )
    await newRecord.insert()
    today = newRecord.model_dump(exclude={"id"})

  return {"today": today}


async def handle_weather(query: str) -> str:
  """Handle weather information queries.

  Args:
      query: The original user query

  Returns:
      Natural language response about the weather
  """

  intent = _classify_intent(query)
  location = intent.get("location", "").lower()
  time_period = intent.get("period")

  logger.debug(f"Detected secondary intent, Location: {location}, period: {time_period}")

  # Check if location is missing — signal handle_conversation to use session memory
  if location == "UNKNOWN_LOCATION" or not location:
    return "No specific location was mentioned. Please use the conversation history to answer the user's question."

  # Check if period is missing and ask the user
  if not time_period:
    time_period = "CURRENT"

  weather_data = await query_weather(location, time_period)
  return _format_weather_data(weather_data, time_period)
