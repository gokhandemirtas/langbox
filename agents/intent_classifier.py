import asyncio
import os
import sys
import time

from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

from utils.log import logger

_console = Console(stderr=True, force_terminal=True)

from agents.router import route_intent
from pydantic_types.intent_response import IntentResponse
from skills.conversation.skill import get_current_topic, get_recent_history
from tts.tts import speak
from utils.llm_structured_output import generate_structured_output

_INTENT_PROMPT = """# Home Assistant Intent Classification Agent

You are an intent classification agent. Classify user queries into exactly one intent category.

## Follow-up Priority Rule (apply this FIRST)

**Exception — always classify before checking conversation history:**
- Music playback commands → always SPOTIFY regardless of history: "pause", "resume", "skip", "next track", "previous track", "play [anything]", "what's playing", "now playing", "volume [n]", "add to queue", "pause spotify", "play spotify"
- Note commands → always NOTES regardless of history (see rule 5)

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

### 8. NOTES
Create, list, read, or delete personal notes.
- "save a note about...", "note that...", "show my notes", "read my note on X", "delete note X"
- **Keywords:** note, notes, save a note, remember this, my notes
- Category tags trigger NOTES when combined with listing: "show my read list", "what do I want to watch"

### 9. SEARCH
Web search for any topic, person, film, product, or general query. Triggered by: "search", "look up", "google", or any standalone topic/name with no other intent keyword.
- "search hellraiser", "look up Elon Musk", "google best pizza in London", "hellraiser"

### 10. SPOTIFY
Control Spotify music playback.
- "play Radiohead", "pause Spotify", "skip this song", "what's playing", "turn the volume up to 80", "add this to queue"
- **Keywords:** play, pause, skip, next track, previous track, volume, now playing, queue, Spotify

### 11. PLANNER
Multi-step planning requests that require research and synthesis into a structured plan or itinerary. Triggered when the user explicitly asks the assistant to *create*, *plan*, or *come up with* something that involves gathering information across multiple steps.
- "plan a 2 week itinerary for Japan", "come up with a travel plan for me", "create a study plan for learning Spanish"
- "plan my trip to Tokyo", "can you put together an itinerary", "I need a plan for my Japan trip"
- "come up with a 2 week schedule", "build me a Japan travel itinerary", "design a workout plan"
- Only applies when the subject of the plan is clear from the query OR the current conversation topic. If there is no clear subject and no conversation context, classify as CHAT instead.
- **Keywords:** plan, itinerary, schedule, put together, come up with a plan, create a plan, build a plan, design a plan, map out

### 12. CHAT
General conversation, greetings, feedback, follow-up comparisons, reactions, personal statements/preferences, nonsensical input, creative/generative requests directed at the assistant, and anything that doesn't clearly fit another category.
- "hello", "good morning", "how are you", "who are you", "thanks for the help", "you were wrong about that"
- Short reactions when history is present: "interesting", "cool", "wow", "really?", "fascinating", "makes sense", "go on"
- Personal statements and preferences when history is present: "I don't like cold", "I prefer X", "that's too expensive", "I hate rain"
- Follow-up questions with no domain keywords: "which one is warmer?", "which is better?", "what did you just say?"
- References to numbered items in a previous answer: "explain number 5", "tell me more about the third one", "what about item 2?"
- Nonsensical or out-of-domain input: "banana elephant purple", "I am ozymandias"
- Requests for physical actions the assistant cannot perform: "fry an egg", "make me coffee", "drive me somewhere", "cook dinner", "open the door", "pour me a drink"
- **Creative/generative requests** asking the assistant to produce content: "come up with a 2 week itinerary", "write me a poem", "create a meal plan", "suggest some ideas", "can you make a list of", "I was hoping you could come up with", "give me a plan for", "draft a schedule"
- **Keywords:** hello, hi, hey, how are you, who are you, thank you, I disagree, I don't like, I prefer, I hate, which one, number, item, the first, the second, the third, come up with, write me, make me a list, give me a plan, create a, draft a, suggest some

## Classification Rules

1. "lights", "lamp", "bulb" + on/off → always HOME_CONTROL
2. "timer", "reminder", "alarm", "remind me", "set a timer", "my calendar", "my schedule" → always REMINDER. The word "today" alone does NOT indicate REMINDER — it must appear with explicit scheduling words.
3. "news", "headlines", "current events", "what's happening" → always NEWSFEED
4. "weather", "forecast", "temperature", "rain", "snow", "humid" anywhere in the query → always WEATHER
5. "take a note", "save a note", "note that", "note:", "add a note", "show my notes", "list my notes", "list notes", "delete note", "read my note" → always NOTES, even when conversation history is present
5a. "pause", "resume", "skip", "next track", "previous track", "play [music/artist/song]", "what's playing", "now playing", "add to queue", "volume [number]", "pause spotify", "play spotify" → always SPOTIFY, even when conversation history is present. Music playback commands are never CHAT follow-ups.
6. TRANSPORTATION requires intent to physically travel — geography questions are INFORMATION_QUERY
7. SEARCH triggers on "search", "look up", "google", or a bare topic/name with no other domain keywords
7a. SPOTIFY triggers on "play [music]", "pause", "skip", "next track", "previous track", "volume", "now playing", "what's playing", "add to queue" — music playback commands always override SEARCH
8. INFORMATION_QUERY triggers on "find out", "tell me about", "what is", "who is", "explain"
9. Messages directed at the assistant (feedback, corrections, greetings) → CHAT
10. Follow-up questions that compare, elaborate, or reference a previous answer → CHAT. This applies even when the prior topic was a domain like WEATHER or FINANCE. "Which one is warmer?", "which is cheaper?", "tell me more about the second one" → always CHAT. References to numbered or ordered items from a prior response ("explain number 5", "what about item 3", "tell me more about the first one") → always CHAT.
11. Nonsensical, incomplete, or out-of-domain queries with NO recognizable keyword → CHAT
11c. Requests for physical actions the assistant cannot perform (cooking, driving, fetching objects, opening doors) → CHAT
11d. Creative or generative requests directed at the assistant — "write me", "make me a list", "draft a", "suggest some", "I was hoping you could" — are ALWAYS CHAT, never SEARCH or INFORMATION_QUERY, UNLESS they are planning requests (see rule 11e)
11e. Planning requests — "plan a trip", "come up with an itinerary", "create a plan", "build a schedule", "put together a travel plan", "come up with a 2 week plan" — are ALWAYS PLANNER when the subject is clear from the query or current conversation topic. "I was hoping you could plan a 2 week itinerary" during a Japan conversation → PLANNER.
11a. Any request asking the assistant to ask/quiz/interview the user about something → CHAT
11b. Personal statements, preferences, or opinions with NO action keyword ("I don't like X", "I prefer Y", "that's too X") when conversation history is present → CHAT
12. When in doubt among general questions → INFORMATION_QUERY
13. Choose the single MOST specific intent
14. If the query contains the word "news" (in any form), ALWAYS classify as NEWSFEED.


## Response Format

Respond with EXACTLY ONE WORD — the intent name in uppercase.

Valid responses: HOME_CONTROL, WEATHER, FINANCE_STOCKS, TRANSPORTATION, REMINDER, NEWSFEED, INFORMATION_QUERY, NOTES, SEARCH, SPOTIFY, PLANNER, CHAT

Examples:
User: "turn on the lights" → HOME_CONTROL
User: "will it rain today" → WEATHER
User: "check Tesla stock" → FINANCE_STOCKS
User: "directions to the airport" → TRANSPORTATION
User: "set a timer for 10 minutes" → REMINDER
User: "news today" → NEWSFEED
User: "find out what photosynthesis is" → INFORMATION_QUERY
User: "what is quantum computing" → INFORMATION_QUERY
User: "save a note about Dune" → NOTES
User: "show my notes" → NOTES
User: "read my note on Dune" → NOTES
User: "search hellraiser" → SEARCH
User: "look up Blade Runner" → SEARCH
User: "hellraiser" → SEARCH
User: "google best pizza in London" → SEARCH
User: "play Bohemian Rhapsody" → SPOTIFY
User: "pause the music" → SPOTIFY
User: "skip this song" → SPOTIFY
User: "what's playing on Spotify" → SPOTIFY
User: "hello" → CHAT
User: "which one is warmer?" → CHAT
User: "what about item 2?" → CHAT
User: "you were wrong about that" → CHAT
User: "banana elephant purple" → CHAT
User: "fry an egg for me" → CHAT
User: "make me a coffee" → CHAT
User: "drive me to the airport" → CHAT
User: "open the door" → CHAT
User: "plan a 2 week Japan itinerary" → PLANNER
User: "I was hoping you could plan a 2 week itinerary" (during Japan conversation) → PLANNER
User: "come up with a travel plan for my Tokyo trip" → PLANNER
User: "can you put together an itinerary for me" (during Japan conversation) → PLANNER
User: "create a study plan for learning Japanese" → PLANNER
User: "write me a poem about autumn" → CHAT
User: "make me a list of movie recommendations" → CHAT
User: "I was hoping you could come up with a 2 week itinerary for me" (no context) → CHAT
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
  topic = get_current_topic()

  if not history and not topic:
    return user_query

  lines = []
  if topic:
    lines.append(f"## Current topic: {topic}")
  if history:
    lines.append("## Recent conversation")
    for human, assistant in history:
      lines.append(f"User: {human}")
      lines.append(f"Assistant: {assistant[:600]}")  # truncate long responses
  lines.append(f"\nCurrent query: {user_query}")
  return "\n".join(lines)


async def run_intent_classifier(user_query: str, on_token=None) -> str:
  """Run the intent classifier agent and return the response."""

  start_time = time.time()
  classifier_input = _build_classifier_prompt(user_query)

  # Use structured output to guarantee a valid intent classification
  logger.debug("Invoking primary intent classifier")
  logger.debug(f"Classifier input:\n{classifier_input}")

  with Live(Spinner("dots", text=Text("tinkering", style="dim")), console=_console, transient=True):
    result = await asyncio.to_thread(
      generate_structured_output,
      model_name=os.environ["MODEL_GENERALIST"],
      user_prompt=classifier_input,
      system_prompt=_INTENT_PROMPT,
      pydantic_model=IntentResponse,
      max_tokens=100,
    )
  logger.debug(f"Classified intent: {result.intent}")

  handler_response = await route_intent(intent=result.intent, query=user_query, on_token=on_token)

  # Append to today's journal
  from skills.journal import append_to_journal

  await append_to_journal(question=user_query, answer=handler_response)

  logger.info(handler_response)
  if "--speak" in sys.argv:
    speak(handler_response)

  elapsed_time = time.time() - start_time
  logger.info(f"Finished in total {elapsed_time:.2f}s")

  return handler_response
