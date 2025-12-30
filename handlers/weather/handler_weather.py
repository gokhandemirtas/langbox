import json
import os
from datetime import datetime

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from agents.agent_factory import create_llm_agent
from db.schemas import Weather
from prompts.weather_prompt import weather_comment_prompt, weatherIntentPrompt
from pydantic_types.weather_intent_response import WeatherIntentResponse
from utils.llm_structured_output import generate_structured_output
from utils.weather_client import fetch_weather_forecast

# Lazy initialization of weather agent
_weather_agent = None


def _get_weather_agent(model_name=os.environ["MODEL_QWEN2.5"], temperature=0.3):
  """Get or create the weather agent with optimized parameters for weather analysis."""
  global _weather_agent
  _weather_agent = create_llm_agent(model_name, temperature=temperature, top_p=0.9, top_k=40)
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

  # Separate the user query and weather data into distinct sections
  user_message = f"""User Query: {query}

Weather Data:
{data_str}

Please comment on the weather data provided above,in order to answer users query.
Keep your answer short and concise 

Example:
- Today in Paris it's mild and sunny, 20 degrees during the day and 8 in the evening.

"""

  messages = [
    SystemMessage(content=weather_comment_prompt),
    HumanMessage(content=user_message),
  ]

  # Use slightly higher temperature for more natural commentary
  agent = _get_weather_agent(os.environ["MODEL_MISTRAL_7B"], temperature=0.3)
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


async def query_weather(location: str, period: str) -> dict:
  """Fetch weather data and format it for LLM consumption.

  Args:
      location: City/location name
      period: Either "CURRENT" or "FORECAST"

  Returns:
      Dictionary containing formatted weather data
  """

  datestamp = datetime.now().date()

  # Fetch all cities from DB
  everything = await Weather.find_all().to_list()
  all = [record.model_dump(exclude={"id"}) for record in everything]

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
      location=weather_forecast.location,
      current_temperature=weather_forecast.current_temperature,
      forecast=weather_forecast.forecast,
    )
    await newRecord.insert()
    today = newRecord.model_dump(exclude={"id"})

  return {"all": all, "today": today}


async def handle_weather(query: str) -> str:
  """Handle weather information queries.

  Args:
      query: The original user query

  Returns:
      Natural language response about the weather
  """

  intent = _classify_intent(query)
  location = intent.get("location")
  time_period = intent.get("period")

  logger.debug(f"Location: {location}, period: {time_period}")

  # Check if location is missing and ask the user
  if location == "UNKNOWN_LOCATION" or not location:
    return "Could not determine the location"

  # Check if period is missing and ask the user
  if not time_period:
    time_period = "CURRENT"

  weather_data = await query_weather(location, time_period)
  comment = _comment_on_data(query, weather_data)

  return comment
