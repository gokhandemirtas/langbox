from pydantic import BaseModel


class HomeControlIntentResponse(BaseModel):
  """Strict schema for home control intent classification."""

  target: str
  turn_on: bool
