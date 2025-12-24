from typing import Literal

from pydantic import BaseModel, Field


class HomeControlIntentResponse(BaseModel):
  """Strict schema for home control intent classification."""

  target_type: Literal["ALL", "GROUP", "LIGHT"] = Field(
    ..., description="Type of target: ALL for all lights, GROUP for light group, LIGHT for individual light"
  )
  target_id: int | None = Field(
    None, description="ID of the target light or group. None if target_type is ALL"
  )
  turn_on: bool = Field(..., description="True to turn on, False to turn off")
