import os
from datetime import date

import feedparser
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from agents.agent_factory import create_llm
from db.schemas import Newsfeed

BBC_RSS_URL = "http://feeds.bbci.co.uk/news/rss.xml"


async def _fetch_news() -> str:
  """Fetch news from DB cache (if today's feed exists) or BBC RSS feed.

  Returns:
      Formatted string of top news headlines and summaries
  """
  today = date.today()

  cached = await Newsfeed.find_one(Newsfeed.datestamp == today)
  if cached:
    logger.debug("Using cached newsfeed from database")
    return cached.content

  try:
    feed = feedparser.parse(BBC_RSS_URL)
    if feed.bozo and not feed.entries:
      logger.warning(f"RSS feed parse error: {feed.bozo_exception}")
      return "Unable to fetch current news at this time."

    entries = feed.entries[:20]
    results = []
    for entry in entries:
      title = entry.get("title", "No title")
      summary = entry.get("summary", "No summary available")
      results.append(f"- {title}: {summary}")

    full_content = "\n".join(results)

    newsfeed = Newsfeed(datestamp=today, content=full_content)
    await newsfeed.insert()
    logger.debug("Saved newsfeed to database")

    return full_content
  except Exception as e:
    logger.error(f"Failed to fetch RSS feed: {e}")
    return "Unable to fetch current news at this time."


async def handle_newsfeed(query: str) -> str:
  """Handle newsfeed queries by fetching and summarizing BBC daily headlines.

  Args:
      query: The user's original query

  Returns:
      Summarized news response
  """
  news_content = await _fetch_news()
  logger.debug(f"Fetched news: {news_content[:200]}...")

  llm = create_llm(
    model_name=os.environ.get("MODEL_QWEN2.5"),
    temperature=0.3,
    max_tokens=1024,
  )

  system_prompt = f"""You are a news summarization agent. Based on the following news headlines and summaries, provide a concise and informative response to the user's question.

    News Content:
    {news_content}

    IMPORTANT RULES:
    - Summarize the provided News Content
    - Do NOT add any facts or details not present in the news content.
  """

  response = await llm.ainvoke([
    SystemMessage(content=system_prompt),
    HumanMessage(content=query),
  ])

  return response.content
