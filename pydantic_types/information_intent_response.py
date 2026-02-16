from pydantic import BaseModel, Field


class InformationIntentResponse(BaseModel):
  """Strict schema for information intent classification."""

  keyword: str = Field(
    ..., description="The core search keyword or topic extracted from the user's query"
  )
