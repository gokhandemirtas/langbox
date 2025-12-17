from datetime import date

from beanie import Document


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
