from datetime import date, datetime
from typing import Literal, Optional

from beanie import Document
from pydantic import BaseModel

NoteCategory = Literal["read", "listen", "watch", "eat", "visit"]


class HueLight(BaseModel):
  id: int
  name: str
  is_on: bool
  bri: int | None = None
  hue: int | None = None
  sat: int | None = None


class HueLightGroup(BaseModel):
  id: int
  name: str



class Weather(Document):
  datestamp: date
  location: str
  current_temperature: int
  forecast: list[str]


class Credentials(Document):
  hueUsername: str


class ServiceCredentials(Document):
  """Generic per-service credential store. One document per service (e.g. 'spotify', 'hue')."""
  service: str
  data: dict  # flexible payload — tokens, usernames, expiry timestamps, etc.


class HueConfiguration(Document):
  groups: list[HueLightGroup]
  lights: list[HueLight]
  lastUpdated: date


class Newsfeed(Document):
  datestamp: date
  content: str  # Large text field for storing full RSS feed content


class Reminders(Document):
  reminder_datetime: datetime  # Main datetime for the reminder
  reminder_end_time: datetime | None = None  # Optional end time for time ranges
  description: str
  created_at: date
  is_completed: bool = False


class Plans(Document):
  created_at: datetime
  ask: str
  plan: str


class ConversationExchange(BaseModel):
  timestamp: datetime
  question: str
  answer: str


class Conversations(Document):
  date: date
  exchanges: list[ConversationExchange] = []
  compacted: Optional[str] = None
  compact_status: Literal["idle", "pending", "complete", "error"] = "idle"


class Journal(Document):
  datestamp: date
  summary: str


class Note(Document):
  created_at: datetime
  title: str                          # plain text
  content: str                        # markdown
  category: Optional[NoteCategory] = None

  class Settings:
    name = "Notes"


class VoiceSettings(Document):
  active_voice_id: str = "azelma"


class UserPersona(Document):
  last_updated: datetime
  exchanges_analyzed: int = 0

  # Explicitly stated demographics
  name: Optional[str] = None                # first name or preferred name
  gender: Optional[str] = None              # "male" | "female" — only set when explicitly stated
  date_of_birth: Optional[str] = None       # "YYYY-MM-DD" — only set when user states it explicitly
  location: Optional[str] = None            # city or country
  profession: Optional[str] = None

  # Big Five personality dimensions (low | medium | high)
  openness: Optional[str] = None            # curious/open vs conventional
  conscientiousness: Optional[str] = None   # organised/disciplined vs spontaneous
  extraversion: Optional[str] = None        # outgoing/energetic vs reserved
  agreeableness: Optional[str] = None       # cooperative/empathetic vs critical
  neuroticism: Optional[str] = None         # anxious/sensitive vs stable/calm

  # Communication
  communication_style: Optional[str] = None  # formal | casual | technical | mixed

  # Preferences
  likes: list[str] = []
  dislikes: list[str] = []

  # Meta
  confidence: float = 0.0
