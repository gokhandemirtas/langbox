from datetime import date, datetime
from typing import Optional

from beanie import Document
from pydantic import BaseModel


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


class JournalEntry(BaseModel):
  timestamp: datetime
  question: str
  answer: str


class Journal(Document):
  date: date
  entries: list[JournalEntry] = []
  summary: Optional[str] = None  # LLM-generated summary, written at next session start


class UserPersona(Document):
  last_updated: datetime
  exchanges_analyzed: int = 0

  # Explicitly stated demographics
  name: Optional[str] = None                # first name or preferred name
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

  # Free-form facts that don't fit the schema
  facts: list[str] = []

  # Meta
  confidence: float = 0.0
