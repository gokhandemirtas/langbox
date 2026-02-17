import os
from datetime import date, datetime

import feedparser
import wikipedia
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from agents.agent_factory import create_llm
from db.schemas import Newsfeed
from prompts.information_prompt import generalKnowledgePrompt, informationIntentPrompt
from pydantic_types.information_intent_response import (
  GeneralKnowledgeResponse,
  InformationIntentResponse,
)
from utils.llm_structured_output import generate_structured_output

BBC_RSS_URL = "http://feeds.bbci.co.uk/news/rss.xml"
CONFIDENCE_THRESHOLD = 7


def _classify_intent(query: str) -> InformationIntentResponse:
  """Extract the search keyword from the user's query using structured output.

  Args:
      query: The user's original query

  Returns:
      InformationIntentResponse with the extracted keyword and query type
  """
  return generate_structured_output(
    model_name=os.environ["MODEL_QWEN2.5"],
    user_prompt=query,
    system_prompt=informationIntentPrompt,
    pydantic_model=InformationIntentResponse,
  )


def _get_contextual_answer(keyword: str) -> str:
  """Build a context string for time/date queries.

  Args:
      keyword: The context descriptor (e.g. 'current_time', 'current_date', 'current_day')

  Returns:
      A string with the relevant date/time information
  """
  now = datetime.now()
  if keyword == "current_time":
    return f"The current time is {now.strftime('%H:%M:%S')}."
  elif keyword == "current_date":
    return f"Today's date is {now.strftime('%A, %B %d, %Y')}."
  elif keyword == "current_day":
    return f"Today is {now.strftime('%A')}."
  else:
    return f"Current date and time: {now.strftime('%A, %B %d, %Y %H:%M:%S')}."


def _search_wiki(keyword: str) -> str:
  """Search Wikipedia for the given keyword.

  Args:
      keyword: The search term to look up on Wikipedia

  Returns:
      Wikipedia summary text, or an error message if not found
  """
  try:
    result = wikipedia.summary(keyword, sentences=5)
    logger.debug(f"Wikipedia result for '{keyword}': {result[:200]}...")
    return result
  except wikipedia.DisambiguationError as e:
    logger.warning(f"Disambiguation for '{keyword}', trying first option: {e.options[0]}")
    return wikipedia.summary(e.options[0], sentences=5)
  except wikipedia.PageError:
    logger.warning(f"No Wikipedia page found for '{keyword}'")
    return f"No Wikipedia article found for '{keyword}'."


async def _fetch_news(keyword: str) -> str:
  """Fetch news from DB cache (if today's feed exists) or BBC RSS feed.

  Args:
      keyword: The topic to filter news by, or 'general' for top headlines

  Returns:
      Formatted string of matching news headlines and summaries
  """
  today = date.today()

  cached = await Newsfeed.find_one(Newsfeed.datestamp == today)
  if cached:
    logger.debug("Using cached newsfeed from database")
    return _filter_news_content(cached.content, keyword)

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

    return _filter_news_content(full_content, keyword)
  except Exception as e:
    logger.error(f"Failed to fetch RSS feed: {e}")
    return "Unable to fetch current news at this time."


def _filter_news_content(content: str, keyword: str) -> str:
  """Filter pre-formatted news content by keyword.

  Args:
      content: Full newsfeed content (one '- title: summary' per line)
      keyword: The topic to filter by, or 'general' for top headlines

  Returns:
      Filtered news lines
  """
  lines = content.strip().split("\n")

  if keyword.lower() == "general":
    return "\n".join(lines[:5])

  keyword_lower = keyword.lower()
  filtered = [line for line in lines if keyword_lower in line.lower()]

  if filtered:
    return "\n".join(filtered[:5])

  logger.debug(f"No entries matching '{keyword}', returning top headlines")
  return "\n".join(lines[:5])


async def _handle_current_events(query: str, keyword: str) -> str:
  """Handle current events queries using BBC News RSS feed.

  Args:
      query: The user's original query
      keyword: The news topic to search for

  Returns:
      Summarized news response
  """
  news_content = await _fetch_news(keyword)
  logger.debug(f"Fetched news for '{keyword}': {news_content[:200]}...")

  llm = create_llm(
    model_name=os.environ.get("MODEL_QWEN2.5"),
    temperature=0.3,
    max_tokens=1024,
  )

  system_prompt = f"""You are a news summarization agent. Based on the following news headlines and summaries, provide a concise and informative response to the user's question.

    News content:
    {news_content}

    IMPORTANT RULES:
    - Summarize the relevant news into a clear, conversational response.
    - Do NOT add any facts or details not present in the news content.
    - If no relevant news was found, say so honestly.
  """

  response = await llm.ainvoke([
    SystemMessage(content=system_prompt),
    HumanMessage(content=query),
  ])

  return response.content


def _handle_general_knowledge(query: str, keyword: str) -> tuple[str, bool]:
  """Handle general knowledge queries with confidence-based Wikipedia fallback.

  Args:
      query: The user's original query
      keyword: The extracted topic keyword

  Returns:
      Tuple of (answer text, needs_summarization). When confidence is high,
      the answer is returned directly and needs_summarization is False.
      When confidence is low, Wikipedia content is returned and needs_summarization is True.
  """
  result = generate_structured_output(
    model_name=os.environ["MODEL_QWEN2.5"],
    user_prompt=query,
    system_prompt=generalKnowledgePrompt,
    pydantic_model=GeneralKnowledgeResponse,
  )

  logger.debug(f"General knowledge response: confidence={result.confidence}, answer={result.answer[:100]}...")

  if result.confidence >= CONFIDENCE_THRESHOLD:
    return result.answer, False

  logger.debug(f"Low confidence ({result.confidence}), falling back to Wikipedia for '{keyword}'")
  return _search_wiki(keyword), True


async def handle_information_query(query: str) -> str:
  """Handle general knowledge and information lookup queries.

  Routes to appropriate sub-handler based on intent classification:
  - current_events: BBC News RSS feed
  - contextual: time/date/day responses
  - general_knowledge: LLM with Wikipedia fallback

  Args:
      query: The original user query

  Returns:
      Information response
  """
  intent = _classify_intent(query)
  logger.debug(
    f"Detected secondary intent: {query}, "
    f"query_type: {intent.query_type}, keyword: {intent.keyword}"
  )

  if intent.query_type.value == "contextual":
    return _get_contextual_answer(intent.keyword)

  if intent.query_type.value == "current_events":
    return await _handle_current_events(query, intent.keyword)

  if intent.query_type.value == "general_knowledge":
    answer, needs_summarization = _handle_general_knowledge(query, intent.keyword)

    if not needs_summarization:
      return answer

    llm = create_llm(
      model_name=os.environ.get("MODEL_QWEN2.5"),
      temperature=0.3,
    )

    system_prompt = f"""You are a knowledge agent that is responsible for reducing the length of a text, to a meaningful summary
        Text to be summarized
        {answer}

        IMPORTANT RULES:
        - Summarize the facts into bullet points (use the dash sign: - to indicate each bullet point), like a news anchor on TV
        - Do NOT add any facts, details, or context that are not present in the Text to be summarized
    """

    response = await llm.ainvoke([
      SystemMessage(content=system_prompt),
      HumanMessage(content=query),
    ])

    return response.content

  return _get_contextual_answer(intent.keyword)
