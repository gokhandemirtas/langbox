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


async def _dispatch(skill, effective_query: str, original_query: str, on_token=None) -> str:
  """Call skill.handle and apply needs_wrapping."""
  # CHAT with streaming: skip the normal handle() call and go straight to handle_chat
  if not skill.needs_wrapping and on_token is not None and skill.id == "CHAT":
    from skills.conversation.skill import handle_chat
    return await handle_chat(query=effective_query, on_token=on_token)

  if asyncio.iscoroutinefunction(skill.handle):
    response = await skill.handle(query=effective_query)
  else:
    response = skill.handle(query=effective_query)

  if not skill.needs_wrapping:
    return response

  return await handle_conversation(original_query, response, on_token=on_token)


def _build_planner_task(query: str) -> str:
  """Synthesise a clear task string for the planner from the query and current topic."""
  topic = get_current_topic()
  if topic and topic.lower() not in query.lower():
    return f"{query} ({topic})"
  return query


async def route_intent(intent: str, query: str, on_token=None) -> str:
  """Route a classified intent to its matching skill."""
  normalized = intent.strip().upper()

  if normalized == "PLANNER":
    from skills.planner.skill import run_planner
    task = _build_planner_task(query)
    logger.debug(f"Intent: PLANNER — task: {task!r}")
    return await run_planner(task)

  skill_id = next((sid for sid in SKILL_MAP if sid in normalized), "CHAT")
  logger.debug(f"Intent: {skill_id}")

  skill = SKILL_MAP[skill_id]
  effective_query = _enrich_query(query, skill_id)

  if skill.auth_provider and not await skill.auth_provider.is_connected():
    logger.info(f"[router] {skill.auth_provider.display_name} not connected — starting auth flow")
    connect_result = await skill.auth_provider.connect()
    if await skill.auth_provider.is_connected():
      retry_response = await _dispatch(skill, effective_query, query, on_token=on_token)
      return f"{connect_result}\n\n{retry_response}"
    return connect_result

  return await _dispatch(skill, effective_query, query, on_token=on_token)
