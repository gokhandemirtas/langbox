from loguru import logger


def handle_security_alarm(query: str) -> None:
    """Handle security system and alarm control.

    Args:
        query: The original user query
    """
    logger.debug(f"🔒 ROUTE: SECURITY_ALARM - Managing security system: {query}")
