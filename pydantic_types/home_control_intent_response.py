from typing import Literal, Optional

from pydantic import BaseModel, Field


class HomeControlIntentResponse(BaseModel):
  """Strict schema for home control intent classification."""

  target: str = Field(
    ...,
    description="Either 'ALL' for all lights, or the specific light ID from the available lights list",
  )
  turn_on: bool = Field(..., description="True to turn on, False to turn off")
  brightness: Optional[int] = Field(
    None, description="Brightness level 0-100 if specified, None otherwise"
  )
