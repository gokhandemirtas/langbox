import asyncio

from loguru import logger

from skills.conversation.skill import handle_conversation
from skills.registry import SKILL_MAP


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
  if asyncio.iscoroutinefunction(skill.handle):
    response = await skill.handle(query=query)
  else:
    response = skill.handle(query=query)

  if not skill.needs_wrapping:
    return response

  return await handle_conversation(query, response)
