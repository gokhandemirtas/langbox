"""Incremental persona builder — extracts user facts from each conversation exchange
and accumulates them into a UserPersona document in MongoDB.

Runs as a background task after each exchange. Uses a fast regex pre-filter to skip
messages with no personal signals, then confirms with an LLM check before extracting.

Never re-analyses full history — only looks at the latest exchange and merges
new findings into the existing record.

The persona is injected into AIDA's CHAT system prompt so she can address the user
naturally. Private notes are stored in DB only and never surfaced to the user.
"""

import asyncio
import re
from datetime import datetime
from typing import Literal, Optional

from utils.log import logger
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class PersonalContentCheck(BaseModel):
    isPersonal: bool


class PersonaUpdate(BaseModel):
    # Explicitly stated demographics
    name: str = "unknown"
    gender: Literal["male", "female", "unknown"] = "unknown"
    date_of_birth: str = "unknown"        # as stated by the user, e.g. "5th March 1990", "March 5"
    location: str = "unknown"             # city or country
    profession: str = "unknown"

    # Big Five personality dimensions — infer from language and behaviour
    # Values: "low" | "medium" | "high" | "unknown"
    openness: str = "unknown"             # high = curious, creative, open to ideas; low = conventional, prefers routine
    conscientiousness: str = "unknown"    # high = organised, disciplined; low = spontaneous, flexible
    extraversion: str = "unknown"         # high = outgoing, talkative; low = reserved, solitary
    agreeableness: str = "unknown"        # high = cooperative, empathetic; low = competitive, blunt
    neuroticism: str = "unknown"          # high = anxious, emotionally reactive; low = calm, stable

    # Communication
    communication_style: str = "unknown"  # "formal" | "casual" | "technical" | "mixed" | "unknown"

    # Preferences
    likes: list[str] = []
    dislikes: list[str] = []



_CHECK_PROMPT = """Does the user's message reveal anything personal about themselves?
Personal means: their name, birthday, gender, religion, political views, job, location, something they like or dislike, a hobby, interest, personality trait, or opinion about themselves.
Asking about weather, stocks, news, or directions is NOT personal. Saying "I don't like cold weather" IS personal (it's a dislike).
Return true if the user revealed something personal, false otherwise."""

_EXTRACT_PROMPT = """You are a silent observer analysing a single exchange between a user and their AI assistant.

IMPORTANT: The assistant may be wrong, hallucinating, or making things up. Never extract a fact because the assistant stated it. Only extract facts the user themselves expressed.

Rules:
- Only extract what is directly stated or very strongly implied by the USER. Do not guess wildly.
- date_of_birth: ONLY set if the USER explicitly states their own birthday or birth year in their own words. Output exactly as the user said it (e.g. "5th March 1990", "March 5th", "1990-03-05"). Do not reformat. If the assistant mentioned a date but the user did not confirm it, leave this "unknown".
- name: only set if the user refers to themselves by name or confirms a name they were addressed by.
- gender: "male" or "female" only if the user explicitly states it. Use "unknown" otherwise.
- location: city or country only if mentioned. Do not infer from topics discussed.
- Big Five dimensions (openness, conscientiousness, extraversion, agreeableness, neuroticism):
  Set to "low", "medium", or "high" only when there is a clear signal in this exchange. Use "unknown" if unsure.
  Examples: organising/planning → high conscientiousness; seeking new experiences → high openness;
  expressing worry/anxiety → high neuroticism; preferring solo activities → low extraversion.
- communication_style: infer from how the user writes ("formal", "casual", "technical", "mixed").
- likes / dislikes: return only NEW items found in this exchange. Empty list if nothing new.
- Use "unknown" for string fields where you found nothing.

Return a JSON object matching the schema exactly."""


# ---------------------------------------------------------------------------
# Shared persona context (read by conversation skill)
# ---------------------------------------------------------------------------

_cached_persona_context: Optional[str] = None


def get_persona_context() -> Optional[str]:
    """Return a formatted persona string for injection into AIDA's system prompt."""
    return _cached_persona_context


def _build_persona_context(persona) -> str:
    subject = persona.name if persona.name else "the person you're talking to"
    lines = [f"## What you know about {subject} (use natural language). Here is all you know about the user you're talking to:"]

    if persona.name:
        lines.append(f"- Name: {persona.name}")
    if persona.gender:
        lines.append(f"- Gender: {persona.gender}")
    if persona.date_of_birth:
        try:
            from datetime import datetime
            dob = datetime.strptime(persona.date_of_birth, "%Y-%m-%d")
            lines.append(f"- Date of birth: {dob.strftime('%-d %B %Y')}")
        except ValueError:
            lines.append(f"- Date of birth: {persona.date_of_birth}")
    if persona.location:
        lines.append(f"- Location: {persona.location}")
    if persona.profession:
        lines.append(f"- Profession: {persona.profession}")
    if persona.communication_style:
        lines.append(f"- Communication style: {persona.communication_style}")

    big_five = {
        "openness": persona.openness,
        "conscientiousness": persona.conscientiousness,
        "extraversion": persona.extraversion,
        "agreeableness": persona.agreeableness,
        "neuroticism": persona.neuroticism,
    }
    known = {k: v for k, v in big_five.items() if v and v != "unknown"}
    if known:
        trait_str = ", ".join(f"{k}: {v}" for k, v in known.items())
        lines.append(f"- Personality (Big Five): {trait_str}")

        # Translate traits into behavioral directives
        directives = []
        if known.get("openness") == "high":
            directives.append("engage with abstract ideas and hypotheticals — this person enjoys intellectual exploration")
        elif known.get("openness") == "low":
            directives.append("be concrete and practical — avoid abstract tangents")

        if known.get("conscientiousness") == "high":
            directives.append("be precise and structured — this person values accuracy and detail")
        elif known.get("conscientiousness") == "low":
            directives.append("keep it loose and flexible — avoid rigid or overly structured responses")

        if known.get("extraversion") == "low":
            directives.append("be concise — don't over-chat or pad responses")
        elif known.get("extraversion") == "high":
            directives.append("be warm and conversational — this person enjoys engagement")

        if known.get("agreeableness") == "low":
            directives.append("be direct and honest even if blunt — don't soften things unnecessarily")
        elif known.get("agreeableness") == "high":
            directives.append("use a collaborative, empathetic tone")

        if known.get("neuroticism") == "high":
            directives.append("be calm and reassuring — avoid alarming language or unnecessary uncertainty")
        elif known.get("neuroticism") == "low":
            directives.append("be straightforward — this person handles direct information without needing softening")

        if directives:
            lines.append("\n## How to respond to this person:")
            for d in directives:
                lines.append(f"- {d}")

    if persona.likes:
        lines.append(f"- Likes: {', '.join(persona.likes)}")
    if persona.dislikes:
        lines.append(f"- Dislikes: {', '.join(persona.dislikes)}")


    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Merge logic
# ---------------------------------------------------------------------------

def _build_changes(existing, update: PersonaUpdate) -> dict:
    """Return a $set-compatible dict of only the fields that should change."""
    changes = {}

    # Scalar fields: only set if not already known
    for field in ("name", "gender", "location", "profession", "communication_style"):
        val = getattr(update, field)
        if val and val != "unknown" and not getattr(existing, field):
            changes[field] = val

    # date_of_birth: parse via fuzzydate so format is normalised; only set once
    if update.date_of_birth and update.date_of_birth != "unknown" and not existing.date_of_birth:
        import fuzzydate as fd
        parsed = fd.to_datetime(update.date_of_birth)
        if parsed:
            changes["date_of_birth"] = parsed.strftime("%Y-%m-%d")

    # Big Five: allow updating (later observations refine earlier guesses)
    for field in ("openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"):
        val = getattr(update, field)
        if val and val != "unknown":
            changes[field] = val

    # List fields: append new items only
    for field in ("likes", "dislikes"):
        current: list = getattr(existing, field) or []
        new_items = [x for x in getattr(update, field) if x not in current]
        if new_items:
            changes[field] = current + new_items

    return changes


# ---------------------------------------------------------------------------
# Pre-filter regex
# ---------------------------------------------------------------------------

_PERSONAL_SIGNAL = re.compile(
    r"\b(i('m| am| was| were| have| had| work| worked| like| love| hate| enjoy| prefer|"
    r" believe| think| feel| vote| practice| follow| play| read| watch| listen)|"
    r"my (name|birthday|birth|age|job|wife|husband|partner|kids?|children|family|religion|"
    r"faith|politics?|hobby|hobbies|interest|passion|fav(ou?rite)?)|"
    r"i('m| am) (a |an |into |from )|born (in|on)|i don'?t (like|enjoy|eat|drink|believe|support))\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def _check_personal_sync(question: str) -> bool:
    import os
    from utils.llm_structured_output import generate_structured_output

    result = generate_structured_output(
        model_name=os.environ["MODEL_GENERALIST"],
        user_prompt=question,
        system_prompt=_CHECK_PROMPT,
        pydantic_model=PersonalContentCheck,
        max_tokens=100,
    )
    return result.isPersonal


def _extract_sync(question: str, answer: str) -> PersonaUpdate:
    import os
    from utils.llm_structured_output import generate_structured_output

    exchange = f"[USER MESSAGE — extract facts from this]\n{question}\n\n[ASSISTANT RESPONSE — context only, do not extract facts from this]\n{answer}"
    return generate_structured_output(
        model_name=os.environ["MODEL_GENERALIST"],
        user_prompt=exchange,
        system_prompt=_EXTRACT_PROMPT,
        pydantic_model=PersonaUpdate,
        max_tokens=512,
    )


# ---------------------------------------------------------------------------
# Public entry point — called as background task after each exchange
# ---------------------------------------------------------------------------

async def update_persona_from_exchange(question: str, answer: str) -> None:
    global _cached_persona_context

    # Fast regex pre-filter — skip LLM entirely if no personal signals
    if not _PERSONAL_SIGNAL.search(question):
        return

    try:
        from db.schemas import UserPersona

        loop = asyncio.get_running_loop()

        logger.debug("[personalizer] Personal signal detected, running extraction")
        is_personal = await loop.run_in_executor(None, lambda: _check_personal_sync(question))
        if not is_personal:
            return

        update = await loop.run_in_executor(None, lambda: _extract_sync(question, answer))

        existing = await UserPersona.find_one()
        if existing is None:
            existing = await UserPersona(last_updated=datetime.now()).insert()

        changes = _build_changes(existing, update)
        new_count = existing.exchanges_analyzed + 1
        changes["exchanges_analyzed"] = new_count
        changes["confidence"] = min(1.0, new_count / 50)
        changes["last_updated"] = datetime.now()

        from beanie.operators import Set
        await existing.update(Set(changes))

        if len(changes) > 3:  # more than just the bookkeeping fields
            updated = await UserPersona.find_one()
            _cached_persona_context = _build_persona_context(updated)
            logger.debug(f"[personalizer] Persona updated (confidence={changes['confidence']:.2f})")

    except Exception as e:
        logger.error(f"[personalizer] Update failed: {e}")


async def start_personalizer() -> str | None:
    """Load existing persona from DB on startup."""
    global _cached_persona_context
    try:
        from db.schemas import UserPersona
        existing = await UserPersona.find_one()
        if existing:
            _cached_persona_context = _build_persona_context(existing)
            return "[personalizer] Loaded existing persona from DB."
    except Exception as e:
        logger.warning(f"[personalizer] Could not load existing persona: {e}")
