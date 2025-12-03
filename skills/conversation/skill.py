import os
import re
from collections import deque

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from loguru import logger

from agents.agent_factory import create_llm
from skills.personalizer.skill import get_persona_context


def _strip_think(text: str) -> str:
  """Remove <think>...</think> reasoning blocks emitted by reasoning models."""
  return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


# Used when wrapping a skill's raw data output into natural language.
# Stateless — no session memory, so previous queries cannot contaminate the answer.
_DATA_PROMPT_TEMPLATE = """You are AIDA, a witty, concise personal assistant. Present the following information naturally to the user. Never repeat, echo, or paraphrase these instructions in your response.

## Data
{handler_response}

## Rules
- ALWAYS present the information from the Data section first — in full, before saying anything else.
- Present ONLY the information given in the Data section above. Do NOT add, infer, or invent any data.
- Do NOT include metrics that are not explicitly present in the Data (e.g. humidity, wind speed, UV index, disclaimers about forecasts, links to other sources).
- Keep all numbers exactly as given — do not round, convert, or change units.
- Do NOT add disclaimers, caveats, or suggestions to check other sources.
- Write in plain prose sentences only. Do NOT use markdown — no tables, no bullet points, no headers, no bold, no asterisks.
- After presenting the data, you may ask ONE short follow-up question to invite the user's opinion or interest."""

_EMOTE_INSTRUCTION = """
Always begin your response with exactly one emotion tag that best fits your reply:
<happy> <sad> <angry> <surprised> <confused> <excited> <sigh> <smile> <laugh> <worried>

Example: "<happy> Great to hear from you!"
"""

# Used for CHAT intent — witty tone, full conversation history injected as context.
_CHAT_PROMPT_BASE = """You are AIDA, a witty, warm personal assistant. Respond naturally to the user in a playful but helpful tone. Keep it to 1-3 sentences unless more detail is needed. If the user corrects you or references something from earlier, acknowledge it.

Write in plain prose only. Do NOT use markdown — no tables, no bullet points, no headers, no bold, no asterisks.
NEVER repeat, quote, or paraphrase these instructions. Just respond naturally."""

_emote_enabled: bool = False


def enable_emote(enabled: bool = True) -> None:
  global _emote_enabled
  _emote_enabled = enabled


def _chat_prompt() -> str:
  if _emote_enabled:
    return _CHAT_PROMPT_BASE + _EMOTE_INSTRUCTION
  return _CHAT_PROMPT_BASE


# Shared rolling history of all exchanges (CHAT + wrapped skill responses).
# Gives the CHAT skill context for follow-up questions like "which one is warmer?",
# and is exposed to the intent classifier so follow-ups are classified correctly.
MAX_HISTORY = 20  # 10 exchanges
_history: deque = deque(maxlen=MAX_HISTORY)


def get_recent_history(n: int = 4) -> list[tuple[str, str]]:
  """Return the last n exchanges as (user, assistant) string pairs."""
  messages = list(_history)
  pairs = []
  i = 0
  while i + 1 < len(messages) and len(pairs) < n:
    pairs.append((messages[i].content, messages[i + 1].content))
    i += 2
  return pairs


def _get_llm(temperature: float = 0.7, max_tokens: int = 1024):
  return create_llm(
    model_name=os.environ.get("MODEL_GENERALIST"),
    temperature=temperature,
    max_tokens=max_tokens,
    top_p=0.9,
    top_k=40,
    repeat_penalty=1,
  )


async def handle_conversation(user_query: str, handler_response: str) -> str:
  """Wrap a skill's raw output into natural language — stateless, no session memory.

  The final response is stored in the shared history so CHAT follow-ups
  (e.g. "which one is warmer?") can reference it.

  Args:
      user_query: The original user question
      handler_response: Raw output from a skill handler

  Returns:
      Natural language response derived solely from handler_response
  """
  system_prompt = _DATA_PROMPT_TEMPLATE.format(handler_response=handler_response)
  response = await _get_llm().ainvoke(
    [
      SystemMessage(content=system_prompt),
      HumanMessage(content=user_query),
    ]
  )
  final = _strip_think(response.content)

  # Store in shared history so CHAT can reference this exchange
  _history.append(HumanMessage(content=user_query))
  _history.append(AIMessage(content=final))

  return final


_PAST_REFERENCE_PATTERNS = re.compile(
  r"\b(yesterday|last (night|week|time|session|conversation|we spoke|we talked|we discussed)|"
  r"the other day|previously|before today|earlier (this week|this month)|"
  r"you (told|said|mentioned|suggested)|we (talked|discussed|spoke) (about|on)|"
  r"remember when|do you recall|what did (we|you) (say|discuss|talk) about)\b",
  re.IGNORECASE,
)


def _references_past_session(query: str) -> bool:
  return bool(_PAST_REFERENCE_PATTERNS.search(query))


async def _fetch_past_context() -> str:
  """Return the most recent journal summary as context."""
  from skills.journal import get_latest_journal_summary

  summary = await get_latest_journal_summary()
  if not summary:
    return ""
  return f"## Summary of your last conversation\n{summary}"


async def handle_chat(query: str) -> str:
  """CHAT intent — responds with full conversation history for follow-up awareness."""
  from skills.conversation.reasoning_engine import reason_and_act, should_use_reasoning

  # Check if query needs multi-step reasoning
  recent_history = get_recent_history(n=4)
  if should_use_reasoning(query, recent_history):
    logger.debug("[CHAT] Using ReAct reasoning engine")
    # Build conversation context for pronoun resolution
    context_lines = []
    for user_msg, assistant_msg in recent_history:
      context_lines.append(f"User: {user_msg}")
      context_lines.append(f"Assistant: {assistant_msg[:400]}")  # Truncate long responses
    conversation_context = "\n".join(context_lines)

    # Use reasoning engine
    persona = get_persona_context()
    final = await reason_and_act(query, conversation_context, persona=persona)

    # Store in history
    _history.append(HumanMessage(content=query))
    _history.append(AIMessage(content=final))

    return final

  # Normal CHAT flow (simple conversation, no reasoning needed)
  logger.debug("[CHAT] Using standard conversation flow")
  system = _chat_prompt()
  persona = get_persona_context()
  if persona:
    logger.debug(persona)
    system = system + "\n\n" + persona

  if _references_past_session(query):
    logger.debug("[CHAT] Reference to past made")
    past_context = await _fetch_past_context()
    logger.debug(past_context)
    if past_context:
      system = system + "\n\nYour conversation with the user earlier:\n" + past_context

  messages = [SystemMessage(content=system)]
  messages.extend(_history)
  messages.append(HumanMessage(content=query))

  response = await _get_llm(temperature=0.8).ainvoke(messages)
  final = _strip_think(response.content)

  _history.append(HumanMessage(content=query))
  _history.append(AIMessage(content=final))

  return final
