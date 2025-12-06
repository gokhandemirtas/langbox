from loguru import logger


def handle_greeting(query: str) -> None:
    """Handle greetings and conversation starters.

    Args:
        query: The original user query
    """
    logger.debug(f"👋 ROUTE: GREETING - Responding to greeting: {query}")


def handle_general_chat(query: str) -> None:
    """Handle casual conversation and chitchat.

    Args:
        query: The original user query
    """
    logger.debug(f"💬 ROUTE: GENERAL_CHAT - Engaging in general conversation: {query}")
