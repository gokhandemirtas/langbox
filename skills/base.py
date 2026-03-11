"""Base Skill definition for langbox."""


class SkillFallback(Exception):
    """Raised by a skill to tell the router to fall back to CHAT.

    Use this when a skill cannot handle the query (e.g. no location in a weather
    follow-up) but the conversation history held by the CHAT handler can answer it.
    """
    pass

from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class Skill:
    """A self-contained unit of functionality routed by intent.

    Attributes:
        id: Intent name used by the router (e.g., "WEATHER"). Must match the
            intent categories defined in the intent classification prompt.
        description: One-line description shown to users and used in the intent
            classification prompt to explain what this skill handles.
        system_prompt: The sub-classification system prompt this skill uses to
            further parse a user query (e.g., extract location from a weather
            query). None for skills that do not run a secondary classification.
        handle: Async (or sync) callable that processes the user query and
            returns a raw string response.  Signature: handle(query: str) -> str
        needs_wrapping: Whether the router should pass the skill's output
            through handle_conversation to produce natural language. Set False
            for skills that already return final natural language (e.g., CHAT).
    """

    id: str
    description: str
    system_prompt: Optional[str]
    handle: Callable
    needs_wrapping: bool = True
