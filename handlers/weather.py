import json
import os
import re
from datetime import datetime
from typing import Literal

import python_weather
import questionary
from json_repair import repair_json
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger
from pydantic import BaseModel, Field

from agents.agent_factory import create_llm_agent
from db.connection import get_db
from db.schemas import Weather
from prompts.weather_prompt import weather_comment_prompt, weather_intent_prompt

db = get_db()

# Pydantic schema for weather intent validation
class WeatherIntent(BaseModel):
    """Strict schema for weather intent classification."""
    location: str = Field(..., description="City or location name, or 'UNKNOWN_LOCATION' if not identified")
    timePeriod: Literal["CURRENT", "FORECAST"] = Field(..., description="Either CURRENT or FORECAST")

# Lazy initialization of weather agent
_weather_agent = None

def _get_weather_agent(model_name=os.environ['MODEL_QWEN2.5']):
    """Get or create the weather agent."""
    global _weather_agent
    _weather_agent = create_llm_agent(
            model_name,
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
    data_str = json.dumps(data, indent=2)

    messages = [
        SystemMessage(content=weather_comment_prompt),
        HumanMessage(content=f"User Query: {query}\n\nWeather Data:\n{data_str}\n\nProvide a natural response to the user's query based on this data.")
    ]

    agent = _get_weather_agent(os.environ["MODEL_QWEN2.5"])
    response = agent.invoke({
        "messages": messages
    })

    result = response["messages"][-1].content.strip()

    return result


def _classify_intent(query: str) -> dict:
    """Classify user intent and extract location and time period.

    Args:
        query: The user's weather query

    Returns:
        Dictionary with keys: location, timePeriod

    Example:
        >>> _classify_intent("What's the weather in Seattle?")
        {"location": "Seattle", "timePeriod": "CURRENT"}
    """
    messages = [
        SystemMessage(content=weather_intent_prompt),
        HumanMessage(content=query)
    ]

    agent = _get_weather_agent()
    response = agent.invoke({
        "messages": messages
    })

    # Extract the response content
    result = response["messages"][-1].content.strip()

    # Try to parse and validate JSON response
    try:
        # Fix malformed JSON using json-repair
        fixed_json = repair_json(result)
        # Validate with Pydantic schema
        intent = WeatherIntent.model_validate_json(fixed_json)

        return intent.model_dump()

    except Exception as e:
        logger.error(f"Failed to parse/validate JSON response: {result}. Error: {e}")
        return {"location": "UNKNOWN_LOCATION", "timePeriod": "CURRENT"}
    
async def _get_weather(location: str, timePeriod: str) -> dict:
    """Fetch weather data and format it for LLM consumption.

    Args:
        location: City/location name
        timePeriod: Either "CURRENT" or "FORECAST"

    Returns:
        Dictionary containing formatted weather data
    """

    datestamp = datetime.now().strftime("%Y%m%d")

    today = db.query(Weather, datestamp = datestamp, limit=1).forecast

    if today:
        logger.debug(f"Record found on: {datestamp}, returning from DB")
        forecast = today
        
    else:
        logger.debug(f"Record NOT found on: {datestamp}, fetching live")
        async with python_weather.Client(unit=python_weather.METRIC) as client:
            # Fetch a weather forecast from a city.
            weather = await client.get(location)

            # Format the data in a structured way
            formatted_data = {
                "location": location,
                "current_temperature": weather.temperature,
                "unit": "Fahrenheit",
                "daily_forecasts": []
            }

            # Fetch weather forecast for upcoming days.
            for daily in weather:
                daily_data = {
                    "date": daily.date.strftime("%Y-%m-%d"),
                    "average_temperature": daily.temperature,
                    "hourly_forecasts": []
                }

                # Each daily forecast has their own hourly forecasts.
                for hourly in daily:
                    hourly_data = {
                        "time": hourly.time.strftime("%H:%M"),
                        "temperature": hourly.temperature,
                        "description": hourly.description,
                        "condition": str(hourly.kind).replace("Kind.", "")
                    }
                    daily_data["hourly_forecasts"].append(hourly_data)

                formatted_data["daily_forecasts"].append(daily_data)

                forecast = Weather(datestamp = datestamp, location = location, forecast = str(formatted_data))
                logger.debug(f"Saved weather data on: {datestamp}")
                db.save([forecast])


    return forecast


async def handle_weather(query: str) -> None:
    """Handle weather information queries.

    Args:
        query: The original user query
    """

    intent = _classify_intent(query)
    location = intent.get("location")
    time_period = intent.get("timePeriod")

    logger.debug(f"Location: {location}, timePeriod: {time_period}")

    # Check if location is missing and ask the user
    if location == "UNKNOWN_LOCATION" or not location:
        location = questionary.text(
            "Where would you like to check the weather?",
            validate=lambda text: len(text) > 0 or "Please enter a location"
        ).ask()

        if not location:
            logger.error("No location provided by user")
            return

    # Check if timePeriod is missing and ask the user
    if not time_period:
        logger.info("Could not determine time period from query, asking user...")
        time_period = questionary.select(
            "What time period are you interested in?",
            choices=["CURRENT", "FORECAST"]
        ).ask()

        if not time_period:
            logger.error("No time period selected by user")
            return

    logger.debug(f"Fetching weather information for: {location} ({time_period})")

    # Fetch and format weather data
    weather_data = await _get_weather(location, time_period)
    logger.debug(weather_data)
    # Get LLM commentary on the weather data
    response = _comment_on_data(query, weather_data)
    return response