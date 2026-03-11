import asyncio

from loguru import logger

from skills.conversation.skill import handle_conversation
from skills.registry import SKILL_MAP


async def route_intent(intent: str, query: str) -> str:
  """Route a classified intent to the matching skill.

  Args:
      intent: The classified intent category (e.g., "WEATHER")
      query: The original user query

  Returns:
      The final natural language response
  """
  intent_upper = intent.strip().upper()

  detected_intent = next(
    (sid for sid in SKILL_MAP if sid in intent_upper),
    None,
  )

  if not detected_intent:
    logger.warning(f"Could not extract valid intent from response: {intent[:200]}...")
    detected_intent = "CHAT"

  logger.debug(f"Detected primary intent: {detected_intent}")

  skill = SKILL_MAP[detected_intent]
  if asyncio.iscoroutinefunction(skill.handle):
    response = await skill.handle(query=query)
  else:
    response = skill.handle(query=query)

  # Skills that already produce final natural language skip the wrapping step
  if not skill.needs_wrapping:
    return response

  return await handle_conversation(query, response)
