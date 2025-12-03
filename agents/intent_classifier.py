import asyncio
import os
import sys
import time

from loguru import logger

from agents.router import route_intent
from pydantic_types.intent_response import IntentResponse
from skills.conversation.skill import get_recent_history
from tts.tts import speak
from utils.llm_structured_output import generate_structured_output

_INTENT_PROMPT = """# Home Assistant Intent Classification Agent

You are an intent classification agent. Classify user queries into exactly one intent category.

## Follow-up Priority Rule (apply this FIRST)

If a "## Recent conversation" section is present, check it before doing anything else:
1. Is the current query a short reaction, acknowledgement, or filler — such as a single word or brief phrase with no clear domain intent? If YES → classify as CHAT immediately.
2. Is the current query a personal statement, preference, or opinion (e.g., "I don't like X", "I prefer Y", "I hate Z", "that's too X") with NO action keyword? If YES → classify as CHAT immediately.
3. Does the current query reference, continue, elaborate on, or react to anything in the conversation history? If YES → classify as CHAT immediately.
4. If none of the above applies → proceed to classify normally using the intent categories below.

This rule takes absolute priority. A query like "explain number 5", "tell me more", "why?", "and the second one?", "what about that last point?" must always be CHAT if there is any prior conversation — even if the words in the query could suggest another intent in isolation.

Short reactions and follow-up prompts are ALWAYS CHAT when conversation history is present: "interesting", "cool", "wow", "really?", "I see", "ok", "got it", "nice", "fascinating", "that's wild", "huh", "makes sense", "go on", "and?", "so?", "tell me about it", "tell me more", "no tell me about it", "go ahead", "keep going", "elaborate", "explain". These are reactions to the prior response, not new search queries.

Personal statements and preferences are ALWAYS CHAT when conversation history is present: "I don't like cold", "I prefer warm weather", "that's too expensive", "I hate rain", "it's too far", "that's perfect". These express opinions about the prior response, not new action requests.

Action requests following a prior response are always CHAT: "add to my watchlist", "save this", "track this", "remind me about this", "book it", "set an alert" — if these follow a domain response, they are follow-ups, not new domain intents.

## Intent Categories

### 1. HOME_CONTROL
Control smart home devices (lights, thermostats, locks, appliances).
- "turn on the lights", "office lights off", "dim the kitchen lights"
- **Keywords:** lights, lamp, bulb, turn on/off, switch on/off, dim

### 2. WEATHER
Weather information queries.
- "how is the weather", "will it rain today", "weather forecast for tomorrow"
- **Keywords:** weather, temperature, rain, snow, forecast, humidity

### 3. FINANCE_STOCKS
Stock prices and financial market information.
- "how is microsoft stock doing", "check Tesla stock", "Bitcoin price"
- **Keywords:** stock, price, market, shares, trading, crypto, bitcoin

### 4. TRANSPORTATION
Navigation and directions between locations. NOT geography questions.
- "how do I get from Putney to Chelsea", "directions to the airport"
- **Keywords:** directions, route, navigate, travel from, get to
- "what is the capital of France" → INFORMATION_QUERY, NOT TRANSPORTATION

### 5. REMINDER
Timers, reminders, alarms, and viewing schedule/calendar.
- "set a timer for 10 minutes", "remind me to call mom at 3pm", "list my reminders", "my calendar today"
- **Keywords:** timer, reminder, alarm, remind me, my calendar, my schedule
- "can you help me bake a cake" → INFORMATION_QUERY, NOT REMINDER

### 6. NEWSFEED
News, headlines, and current events.
- "what's the latest news", "news today", "give me today's headlines", "what's happening in the world"
- **Keywords:** news, headlines, current events, breaking news, what's happening
- Any query containing "news" or asking for headlines is ALWAYS NEWSFEED, NOT INFORMATION_QUERY

### 7. INFORMATION_QUERY
Wikipedia/knowledge lookup. Triggered by: "find out", "tell me about", "what is", "who is", "explain".
- "find out what photosynthesis is", "tell me about the French Revolution", "what is quantum computing"

### 8. SEARCH
Web search for any topic, person, film, product, or general query. Triggered by: "search", "look up", "google", or any standalone topic/name with no other intent keyword.
- "search hellraiser", "look up Elon Musk", "google best pizza in London", "hellraiser"

### 9. CHAT
General conversation, greetings, feedback, follow-up comparisons, reactions, personal statements/preferences, nonsensical input, and anything that doesn't clearly fit another category.
- "hello", "good morning", "how are you", "who are you", "thanks for the help", "you were wrong about that"
- Short reactions when history is present: "interesting", "cool", "wow", "really?", "fascinating", "makes sense", "go on"
- Personal statements and preferences when history is present: "I don't like cold", "I prefer X", "that's too expensive", "I hate rain"
- Follow-up questions with no domain keywords: "which one is warmer?", "which is better?", "what did you just say?"
- References to numbered items in a previous answer: "explain number 5", "tell me more about the third one", "what about item 2?"
- Nonsensical or out-of-domain input: "banana elephant purple", "I am ozymandias"
- **Keywords:** hello, hi, hey, how are you, who are you, thank you, I disagree, I don't like, I prefer, I hate, which one, number, item, the first, the second, the third

## Classification Rules

1. "lights", "lamp", "bulb" + on/off → always HOME_CONTROL
2. "timer", "reminder", "alarm", "remind me", "set a timer", "my calendar", "my schedule" → always REMINDER. The word "today" alone does NOT indicate REMINDER — it must appear with explicit scheduling words.
3. "news", "headlines", "current events", "what's happening" → always NEWSFEED
4. "weather", "forecast", "temperature", "rain", "snow", "humid" anywhere in the query → always WEATHER
5. TRANSPORTATION requires intent to physically travel — geography questions are INFORMATION_QUERY
6. SEARCH triggers on "search", "look up", "google", or a bare topic/name with no other domain keywords
7. INFORMATION_QUERY triggers on "find out", "tell me about", "what is", "who is", "explain"
7. Messages directed at the assistant (feedback, corrections, greetings) → CHAT
8. Follow-up questions that compare, elaborate, or reference a previous answer → CHAT. This applies even when the prior topic was a domain like WEATHER or FINANCE. "Which one is warmer?", "which is cheaper?", "tell me more about the second one" → always CHAT. References to numbered or ordered items from a prior response ("explain number 5", "what about item 3", "tell me more about the first one") → always CHAT.
9. Nonsensical, incomplete, or out-of-domain queries with NO recognizable keyword → CHAT
9a. Any request asking the assistant to ask/quiz/interview the user about something → CHAT
9b. Personal statements, preferences, or opinions with NO action keyword ("I don't like X", "I prefer Y", "that's too X") when conversation history is present → CHAT
10. When in doubt among general questions → INFORMATION_QUERY
11. Choose the single MOST specific intent
12. If the query contains the word "news" (in any form), ALWAYS classify as NEWSFEED.


## Response Format

Respond with EXACTLY ONE WORD — the intent name in uppercase.

Valid responses: HOME_CONTROL, WEATHER, FINANCE_STOCKS, TRANSPORTATION, REMINDER, NEWSFEED, INFORMATION_QUERY, SEARCH, CHAT

Examples:
User: "turn on the lights" → HOME_CONTROL
User: "will it rain today" → WEATHER
User: "check Tesla stock" → FINANCE_STOCKS
User: "directions to the airport" → TRANSPORTATION
User: "set a timer for 10 minutes" → REMINDER
User: "news today" → NEWSFEED
User: "find out what photosynthesis is" → INFORMATION_QUERY
User: "what is quantum computing" → INFORMATION_QUERY
User: "search hellraiser" → SEARCH
User: "look up Blade Runner" → SEARCH
User: "hellraiser" → SEARCH
User: "google best pizza in London" → SEARCH
User: "hello" → CHAT
User: "which one is warmer?" → CHAT
User: "what about item 2?" → CHAT
User: "you were wrong about that" → CHAT
User: "banana elephant purple" → CHAT
User: "interesting" (after a prior response) → CHAT
User: "cool" (after a prior response) → CHAT
User: "wow" (after a prior response) → CHAT
User: "tell me about it" (after a prior response) → CHAT
User: "no tell me about it" (after a prior response) → CHAT
User: "tell me more" (after a prior response) → CHAT
User: "I don't like cold" (after weather discussion) → CHAT
User: "that's too expensive" (after any prior response) → CHAT
User: "I prefer warm weather" (after weather discussion) → CHAT
"""


def _build_classifier_prompt(user_query: str) -> str:
  """Prepend recent conversation history so the classifier can resolve follow-ups."""
  history = get_recent_history(n=4)
  if not history:
    return user_query

  lines = ["## Recent conversation"]
  for human, assistant in history:
    lines.append(f"User: {human}")
    lines.append(f"Assistant: {assistant[:600]}")  # truncate long responses
  lines.append(f"\nCurrent query: {user_query}")
  return "\n".join(lines)


async def run_intent_classifier(user_query: str) -> str:
  """Run the intent classifier agent and return the response."""

  start_time = time.time()
  classifier_input = _build_classifier_prompt(user_query)

  # Use structured output to guarantee a valid intent classification
  logger.debug("Invoking primary intent classifier")
  logger.debug(f"Classifier input:\n{classifier_input}")

  result = await asyncio.to_thread(
    generate_structured_output,
    model_name=os.environ["MODEL_GENERALIST"],
    user_prompt=classifier_input,
    system_prompt=_INTENT_PROMPT,
    pydantic_model=IntentResponse,
    max_tokens=100,
  )
  logger.debug(f"Classified intent: {result.intent}")

  handler_response = await route_intent(intent=result.intent, query=user_query)

  # Append to today's journal
  from skills.journal import append_to_journal

  await append_to_journal(question=user_query, answer=handler_response)

  logger.info(handler_response)
  if "--speak" in sys.argv:
    speak(handler_response)

  elapsed_time = time.time() - start_time
  logger.info(f"Finished in total {elapsed_time:.2f}s")

  return handler_response
