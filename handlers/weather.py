from loguru import logger


def handle_weather(query: str) -> None:
    """Handle weather information queries.

    Args:
        query: The original user query
    """
    logger.info(f"🌤️  ROUTE: WEATHER - Fetching weather information for: {query}")