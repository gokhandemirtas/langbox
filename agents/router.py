import asyncio

from utils.log import logger

from skills.conversation.skill import handle_conversation
from skills.registry import SKILL_MAP


async def _dispatch(skill, effective_query: str, original_query: str, on_token=None, on_status=None) -> str:
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


async def route_intent(intent: str, query: str, on_token=None, on_status=None) -> str:
  """Route a classified intent to its matching skill."""
  normalized = intent.strip().upper()

  if normalized == "PLANNER":
    from skills.planner.skill import run_planner
    task = query
    logger.debug(f"Intent: PLANNER — task: {task!r}")
    return await run_planner(task)

  skill_id = next((sid for sid in SKILL_MAP if sid in normalized), "CHAT")
  logger.debug(f"Intent: {skill_id}")

  skill = SKILL_MAP[skill_id]
  effective_query = query

  if skill.auth_provider and not await skill.auth_provider.is_connected():
    logger.info(f"[router] {skill.auth_provider.display_name} not connected — starting auth flow")
    connect_result = await skill.auth_provider.connect()
    if await skill.auth_provider.is_connected():
      retry_response = await _dispatch(skill, effective_query, query, on_token=on_token, on_status=on_status)
      return f"{connect_result}\n\n{retry_response}"
    return connect_result

  return await _dispatch(skill, effective_query, query, on_token=on_token, on_status=on_status)
