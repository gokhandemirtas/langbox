from datetime import date
from typing import Any, Dict

from beanie import Document


class Conversations(Document):
  datestamp: date
  question: str
  answer: str


class Weather(Document):
  datestamp: date
  location: str
  forecast: Dict[str, Any]
