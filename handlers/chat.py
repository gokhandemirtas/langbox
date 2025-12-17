from loguru import logger


def handle_greeting(query: str) -> str:
    """Handle greetings and conversation starters.

    Args:
        query: The original user query

    Returns:
        A friendly greeting response
    """
    logger.debug(f"👋 ROUTE: GREETING - Responding to greeting: {query}")
    return "Hello! I'm here to help you. How can I assist you today?"


def handle_general_chat(query: str) -> str:
    """Handle casual conversation and chitchat.

    Args:
        query: The original user query

    Returns:
        A conversational response
    """
    logger.debug(f"💬 ROUTE: GENERAL_CHAT - Engaging in general conversation: {query}")
    return "I'd be happy to chat! What would you like to talk about?"
