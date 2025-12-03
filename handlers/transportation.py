from loguru import logger


def handle_transportation(query: str) -> None:
    """Handle transit and traffic information.

    Args:
        query: The original user query
    """
    logger.info(f"🚗 ROUTE: TRANSPORTATION - Checking transit/traffic information: {query}")
