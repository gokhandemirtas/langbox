import json
import os
from datetime import datetime
from typing import Literal

import questionary
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger
from pydantic import BaseModel, Field

from agents.agent_factory import create_llm_agent
from db.schemas import Weather
from prompts.weather_prompt import weather_comment_prompt, weatherIntentPrompt
from pydantic_types.weather_intent_response import WeatherIntentResponse
from utils.llm_structured_output import generate_structured_output
from utils.weather_client import fetch_weather_forecast


# Pydantic schema for weather intent validation
class WeatherIntent(BaseModel):
  """Strict schema for weather intent classification."""

  location: str = Field(
    ..., description="City or location name, or 'UNKNOWN_LOCATION' if not identified"
  )
  period: Literal["CURRENT", "FORECAST"] = Field(..., description="Either CURRENT or FORECAST")


# Lazy initialization of weather agent
_weather_agent = None


def _get_weather_agent(model_name=os.environ["MODEL_QWEN2.5"], temperature=0.3):
  """Get or create the weather agent with optimized parameters for weather analysis."""
  global _weather_agent
  _weather_agent = create_llm_agent(
    model_name,
    temperature=temperature,
    top_p=0.9,
    top_k=40,
  )
  return _weather_agent


def _comment_on_data(query: str, data: dict) -> str:
  """Comment on the weather data.

  Args:
      query: The user's original weather query
      data: Formatted weather forecast data

  Returns:
      Formatted string: Natural language response
  """
  # Format the data as a readable string for the LLM
  data_str = json.dumps(data, indent=2, default=str)

  messages = [
    SystemMessage(content=weather_comment_prompt),
    HumanMessage(content=f"""User Query: {query}, Weather Data: {data_str} """),
  ]

  # Use slightly higher temperature for more natural commentary
  agent = _get_weather_agent(os.environ["MODEL_QWEN2.5"], temperature=0.4)
  response = agent.invoke({"messages": messages})

  result = response["messages"][-1].content.strip()

  return result


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

  # Try to parse and validate JSON response
  try:
    result = generate_structured_output(
      model_name=os.environ["MODEL_QWEN2.5"],
      user_prompt=query,
      system_prompt=weatherIntentPrompt,
      pydantic_model=WeatherIntentResponse,
    )

    return result.model_dump()

  except Exception as e:
    logger.error(f"Failed to generate structured output. Error: {e}")
    return {"location": "UNKNOWN_LOCATION", "period": "CURRENT"}


async def _query_weather(location: str, period: str) -> dict:
  """Fetch weather data and format it for LLM consumption.

  Args:
      location: City/location name
      period: Either "CURRENT" or "FORECAST"

  Returns:
      Dictionary containing formatted weather data
  """

  datestamp = datetime.now().date()

  # Fetch all past weather records
  everything = await Weather.find_all().to_list()
  past = [record.model_dump(exclude={"id"}) for record in everything]

  # Check if today's forecast exists for the location
  found = await Weather.find(Weather.datestamp == datestamp, Weather.location == location).to_list()
  if found:
    logger.debug(f"""Today's forecast found for {location} in DB""")
    today = found[0].forecast
  else:
    logger.debug(f"""Fetching new forecast for {location}""")
    weather_forecast = await fetch_weather_forecast(location)
    # Convert Pydantic model to dict for storage
    today = weather_forecast.model_dump()
    newRecord = Weather(datestamp=datestamp, location=location, forecast=today)
    await newRecord.insert()

  return {"past": past, "today": today}


async def handle_weather(query: str) -> None:
  """Handle weather information queries.

  Args:
      query: The original user query
  """

  intent = _classify_intent(query)
  location = intent.get("location")
  time_period = intent.get("period")

  logger.debug(f"Location: {location}, period: {time_period}")

  # Check if location is missing and ask the user
  if location == "UNKNOWN_LOCATION" or not location:
    location = await questionary.text(
      "Where would you like to check the weather?",
      validate=lambda text: len(text) > 0 or "Please enter a location",
    ).ask_async()

    if not location:
      logger.error("No location provided by user")
      return

  # Check if period is missing and ask the user
  if not time_period:
    logger.info("Could not determine time period from query, asking user...")
    time_period = await questionary.select(
      "What time period are you interested in?", choices=["CURRENT", "FORECAST"]
    ).ask_async()

    if not time_period:
      logger.error("No time period selected by user")
      return

  weather_data = await _query_weather(location, time_period)
  comment = _comment_on_data(query, weather_data)

  return comment
