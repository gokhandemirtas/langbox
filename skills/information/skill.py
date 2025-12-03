import asyncio
import os
from datetime import datetime
from enum import Enum

from ddgs import DDGS
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger
from pydantic import BaseModel
from tavily import TavilyClient

from agents.agent_factory import create_llm
from skills.information.prompts import informationIntentPrompt
from utils.llm_structured_output import generate_structured_output


class QueryType(str, Enum):
  contextual = "contextual"
  general_knowledge = "general_knowledge"


class InformationIntentResponse(BaseModel):
  query_type: QueryType
  keyword: str


def _classify_intent(query: str) -> InformationIntentResponse:
  return generate_structured_output(
    model_name=os.environ["MODEL_GENERALIST"],
    user_prompt=query,
    system_prompt=informationIntentPrompt,
    pydantic_model=InformationIntentResponse,
  )


def _get_contextual_answer(keyword: str) -> str:
  now = datetime.now()
  if keyword == "current_time":
    return f"The current time is {now.strftime('%H:%M:%S')}."
  elif keyword == "current_date":
    return f"Today's date is {now.strftime('%A, %B %d, %Y')}."
  elif keyword == "current_day":
    return f"Today is {now.strftime('%A')}."
  else:
    return f"Current date and time: {now.strftime('%A, %B %d, %Y %H:%M:%S')}."


def _search_ddg(query: str) -> list[str]:
  try:
    results = DDGS().text(query, max_results=5)
    lines = [
      f"- {r.get('title', '')}: {r.get('body', '').replace(chr(10), ' ')} ({r.get('href', '')})"
      for r in (results or [])
    ]
    logger.debug(f"DuckDuckGo returned {len(lines)} results for '{query}'")
    return lines
  except Exception as e:
    logger.warning(f"DuckDuckGo search failed: {e}")
    return []


def _search_tavily(query: str) -> list[str]:
  api_key = os.environ.get("TAVILY_API_KEY")
  if not api_key:
    return []
  try:
    results = TavilyClient(api_key=api_key).search(query, max_results=5).get("results", [])
    lines = [
      f"- {r.get('title', '')}: {r.get('content', '').replace(chr(10), ' ')} ({r.get('url', '')})"
      for r in results
    ]
    logger.debug(f"Tavily returned {len(lines)} results for '{query}'")
    return lines
  except Exception as e:
    logger.warning(f"Tavily search failed: {e}")
    return []


async def _search_web(query: str) -> str | None:
  ddg_results, tavily_results = await asyncio.gather(
    asyncio.to_thread(_search_ddg, query),
    asyncio.to_thread(_search_tavily, query),
  )
  combined = ddg_results + tavily_results
  return "\n".join(combined) if combined else None


async def _llm_fallback(query: str) -> str:
  llm = create_llm(model_name=os.environ.get("MODEL_GENERALIST"), temperature=0.3)
  response = await llm.ainvoke([
    SystemMessage(content="Answer the user's question as accurately as possible using your training data."),
    HumanMessage(content=query),
  ])
  return f"I am answering this using my training data: {response.content}"


async def handle_information_query(query: str) -> str:
  """Handle general knowledge queries — DDG first, LLM fallback with disclaimer."""
  intent = _classify_intent(query)
  logger.debug(f"Information intent: query_type={intent.query_type}, keyword={intent.keyword}")

  if intent.query_type.value == "contextual":
    return _get_contextual_answer(intent.keyword)

  web_results = await _search_web(query)
  if web_results:
    return web_results

  logger.debug("DuckDuckGo returned no results, falling back to LLM")
  return await _llm_fallback(query)
