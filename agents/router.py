import asyncio

from utils.log import logger

from skills.conversation.skill import handle_conversation, get_current_topic
from skills.registry import SKILL_MAP

_TOPIC_ENRICHED_INTENTS = {"SEARCH", "INFORMATION_QUERY"}
_SHORT_QUERY_WORDS = 6


def _enrich_query(query: str, intent: str) -> str:
  """Append the current topic to short follow-up search queries.

  e.g. query="a jamie oliver recipe", topic="egg recipe"
       → "a jamie oliver recipe egg recipe"
  """
  if intent not in _TOPIC_ENRICHED_INTENTS:
    return query
  topic = get_current_topic()
  if not topic:
    return query
  if len(query.split()) <= _SHORT_QUERY_WORDS:
    enriched = f"{query} {topic}"
    logger.debug(f"[router] query enriched with topic: '{enriched}'")
    return enriched
  return query


async def _dispatch(skill, effective_query: str, original_query: str) -> str:
  """Call skill.handle and apply needs_wrapping."""
  if asyncio.iscoroutinefunction(skill.handle):
    response = await skill.handle(query=effective_query)
  else:
    response = skill.handle(query=effective_query)

  if not skill.needs_wrapping:
    return response

  return await handle_conversation(original_query, response)


async def route_intent(intent: str, query: str) -> str:
  """Route a classified intent to its matching skill.

  Args:
      intent: The classified intent category (e.g., "WEATHER")
      query: The original user query

  Returns:
      The final natural language response
  """
  skill_id = next((sid for sid in SKILL_MAP if sid in intent.strip().upper()), "CHAT")
  logger.debug(f"Intent: {skill_id}")

  skill = SKILL_MAP[skill_id]
  effective_query = _enrich_query(query, skill_id)

  if skill.auth_provider and not await skill.auth_provider.is_connected():
    logger.info(f"[router] {skill.auth_provider.display_name} not connected — starting auth flow")
    connect_result = await skill.auth_provider.connect()
    # Auto-retry the skill if auth succeeded
    if await skill.auth_provider.is_connected():
      retry_response = await _dispatch(skill, effective_query, query)
      return f"{connect_result}\n\n{retry_response}"
    return connect_result

  return await _dispatch(skill, effective_query, query)
