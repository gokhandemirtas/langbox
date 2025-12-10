from typing import Any, Dict

from beanie import Document
from pydantic import NaiveDatetime


class Conversations(Document):
  datestamp: NaiveDatetime
  question: str
  answer: str


class Weather(Document):
  datestamp: NaiveDatetime
  location: str
  forecast: Dict[str, Any]
