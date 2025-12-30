import asyncio

from loguru import logger

from handlers.chat.handler_chat import handle_general_chat, handle_greeting
from handlers.finance.handler_finance import handle_finance_stocks
from handlers.home_control.handler_home_control import handle_home_control
from handlers.information.handler_information import handle_information_query
from handlers.reminder.handler_reminder import handle_reminder
from handlers.transportation.handler_transportation import handle_transportation
from handlers.weather.handler_weather import handle_weather


async def route_intent(intent: str, query: str) -> str:
  """
  Route classified intents to their appropriate handlers.

  Args:
      intent: The classified intent category (e.g., "HOME_CONTROL", "WEATHER", etc.)
      query: The original user query

  Returns:
      The handler's response string
  """
  # Define valid intent categories
  valid_intents = [
    "HOME_CONTROL",
    "WEATHER",
    "FINANCE_STOCKS",
    "TRANSPORTATION",
    "CALENDAR_SCHEDULE",
    "REMINDER",
    "INFORMATION_QUERY",
    "GREETING",
    "GENERAL_CHAT",
  ]

  # Extract the intent from the response
  # The LLM sometimes returns verbose responses instead of just the intent name
  intent_upper = intent.strip().upper()

  # Try to find a valid intent in the response
  detected_intent = None
  for valid_intent in valid_intents:
    if valid_intent in intent_upper:
      detected_intent = valid_intent
      break

  # If we couldn't find a valid intent, log the full response for debugging
  if not detected_intent:
    logger.warning(f"Could not extract valid intent from response: {intent[:200]}...")
    logger.debug("Falling back to general chat handler")
    if asyncio.iscoroutinefunction(handle_general_chat):
      return await handle_general_chat(query=query)
    else:
      return handle_general_chat(query=query)

  # Log the detected intent
  logger.debug(f"Detected intent: {detected_intent}")
  logger.debug(f"Original query: {query}")

  # Route to the appropriate handler
  route_map = {
    "HOME_CONTROL": handle_home_control,
    "WEATHER": handle_weather,
    "FINANCE_STOCKS": handle_finance_stocks,
    "TRANSPORTATION": handle_transportation,
    "REMINDER": handle_reminder,
    "INFORMATION_QUERY": handle_information_query,
    "GREETING": handle_greeting,
    "GENERAL_CHAT": handle_general_chat,
  }

  handler = route_map.get(detected_intent)
  if handler:
    # Check if handler is async and await it
    if asyncio.iscoroutinefunction(handler):
      return await handler(query=query)
    else:
      return handler(query=query)
  else:
    logger.warning(f"No handler found for intent: {detected_intent}")
    if asyncio.iscoroutinefunction(handle_general_chat):
      return await handle_general_chat(query=query)
    else:
      return handle_general_chat(query=query)
