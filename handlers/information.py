from loguru import logger


def handle_information_query(query: str) -> None:
    """Handle general knowledge and information lookup.

    Args:
        query: The original user query
    """
    logger.debug(f"❓ ROUTE: INFORMATION_QUERY - Looking up information: {query}")
