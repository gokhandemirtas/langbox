import os
from datetime import datetime
from enum import Enum

import wikipedia
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger
from pydantic import BaseModel

from agents.agent_factory import create_llm
from skills.information.prompts import generalKnowledgePrompt, informationIntentPrompt
from utils.llm_structured_output import generate_structured_output

CONFIDENCE_THRESHOLD = 9  # Only skip Wikipedia when model is very certain (9-10)


class QueryType(str, Enum):
  contextual = "contextual"
  general_knowledge = "general_knowledge"


class InformationIntentResponse(BaseModel):
  query_type: QueryType
  keyword: str


class GeneralKnowledgeResponse(BaseModel):
  answer: str
  confidence: int


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


def _search_wiki(keyword: str) -> str:
  try:
    result = wikipedia.summary(keyword, sentences=5)
    logger.debug(f"Wikipedia result for '{keyword}': {result[:200]}...")
    return result
  except wikipedia.DisambiguationError as e:
    logger.warning(f"Disambiguation for '{keyword}', trying first option: {e.options[0]}")
    return wikipedia.summary(e.options[0], sentences=5)
  except wikipedia.PageError:
    logger.warning(f"No Wikipedia page found for '{keyword}'")
    return None


def _handle_general_knowledge(query: str, keyword: str) -> tuple[str, bool]:
  result = generate_structured_output(
    model_name=os.environ["MODEL_GENERALIST"],
    user_prompt=query,
    system_prompt=generalKnowledgePrompt,
    pydantic_model=GeneralKnowledgeResponse,
  )

  logger.debug(f"General knowledge response: confidence={result.confidence}, answer={result.answer[:100]}...")

  if result.confidence >= CONFIDENCE_THRESHOLD:
    return result.answer, False

  logger.debug(f"Low confidence ({result.confidence}), falling back to Wikipedia for '{keyword}'")
  wiki = _search_wiki(keyword)
  if wiki is not None:
    return wiki, True

  logger.debug(f"No Wikipedia page for '{keyword}', using low-confidence LLM answer with disclaimer")
  return f"I'm not certain of this, but: {result.answer}", False


async def handle_information_query(query: str) -> str:
  """Handle general knowledge and information lookup queries."""
  intent = _classify_intent(query)
  logger.debug(
    f"Detected secondary intent: {query}, "
    f"query_type: {intent.query_type}, keyword: {intent.keyword}"
  )

  if intent.query_type.value == "contextual":
    return _get_contextual_answer(intent.keyword)

  if intent.query_type.value == "general_knowledge":
    answer, needs_summarization = _handle_general_knowledge(query, intent.keyword)

    if not needs_summarization:
      return answer

    llm = create_llm(
      model_name=os.environ.get("MODEL_GENERALIST"),
      temperature=0.3,
    )

    system_prompt = f"""You are a knowledge agent that is responsible for reducing the length of a text, to a meaningful summary
        Text to be summarized
        {answer}

        IMPORTANT RULES:
        - Summarize the content into bullet points (use the dash sign: - to indicate each bullet point)
        - Do NOT add any facts, details, or context that are not present in the Text to be summarized
    """

    response = await llm.ainvoke([
      SystemMessage(content=system_prompt),
      HumanMessage(content=query),
    ])

    return response.content

  return _get_contextual_answer(intent.keyword)
