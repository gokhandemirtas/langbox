from loguru import logger

from handlers.calendar import handle_calendar_schedule
from handlers.chat import handle_general_chat, handle_greeting
from handlers.finance import handle_finance_stocks
from handlers.home_control import handle_home_control
from handlers.information import handle_information_query
from handlers.security import handle_security_alarm
from handlers.timer import handle_timer_reminder
from handlers.transportation import handle_transportation
from handlers.weather import handle_weather


def route_intent(intent: str, query: str) -> None:
    """
    Route classified intents to their appropriate handlers.

    Args:
        intent: The classified intent category (e.g., "HOME_CONTROL", "WEATHER", etc.)
        query: The original user query
    """
    # Define valid intent categories
    valid_intents = [
        "HOME_CONTROL",
        "SECURITY_ALARM",
        "WEATHER",
        "FINANCE_STOCKS",
        "TRANSPORTATION",
        "CALENDAR_SCHEDULE",
        "TIMER_REMINDER",
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
        logger.info("Falling back to general chat handler")
        handle_general_chat(query=query)
        return

    # Log the detected intent
    logger.info(f"Detected intent: {detected_intent}")
    logger.debug(f"Original query: {query}")

    # Route to the appropriate handler
    route_map = {
        "HOME_CONTROL": handle_home_control,
        "SECURITY_ALARM": handle_security_alarm,
        "WEATHER": handle_weather,
        "FINANCE_STOCKS": handle_finance_stocks,
        "TRANSPORTATION": handle_transportation,
        "CALENDAR_SCHEDULE": handle_calendar_schedule,
        "TIMER_REMINDER": handle_timer_reminder,
        "INFORMATION_QUERY": handle_information_query,
        "GREETING": handle_greeting,
        "GENERAL_CHAT": handle_general_chat,
    }

    handler = route_map.get(detected_intent)
    if handler:
        handler(query=query)
    else:
        logger.warning(f"No handler found for intent: {detected_intent}")
        handle_general_chat(query=query)
