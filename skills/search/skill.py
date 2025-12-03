import re

from ddgs import DDGS
from loguru import logger


def _extract_topic(query: str) -> str:
    """Strip the 'search:' prefix and return the bare topic."""
    match = re.match(r"search\s*:\s*(.+)", query, flags=re.IGNORECASE)
    return match.group(1).strip() if match else query.strip()


async def handle_search(query: str) -> str:
    """Perform a DuckDuckGo search and return formatted results."""
    topic = _extract_topic(query)
    logger.debug(f"Searching DuckDuckGo for: {topic}")

    results = DDGS().text(topic, max_results=5)

    if not results:
        return f"No results found for: {topic}"

    lines = [f"Search results for: {topic}"]
    for i, item in enumerate(results, 1):
        title = item.get("title", "")
        snippet = item.get("body", "").replace("\n", " ")
        link = item.get("href", "")
        lines.append(f"\n{i}. {title}\n   {snippet}\n   {link}")

    return "\n".join(lines)
