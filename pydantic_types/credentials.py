from pydantic import BaseModel, Field


class Credentials(BaseModel):
  """Complete weather forecast for a location with flattened structure."""

  hueUsername: str = Field(..., description="Username for Hue bridge")
