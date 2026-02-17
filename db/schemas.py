from datetime import date, datetime

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


class Conversations(Document):
  datestamp: date
  question: str
  answer: str
  raw: str


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
