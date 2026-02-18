from enum import Enum

from pydantic import BaseModel, Field


class QueryType(str, Enum):
  contextual = "contextual"
  general_knowledge = "general_knowledge"


class InformationIntentResponse(BaseModel):
  """Strict schema for information intent classification."""

  query_type: QueryType = Field(
    ...,
    description="Type of query: 'contextual' for time/date queries, "
    "'general_knowledge' for factual questions",
  )
  keyword: str = Field(
    ...,
    description="The core search keyword or topic, or context "
    "descriptor like 'current_time', 'current_date'",
  )


class GeneralKnowledgeResponse(BaseModel):
  """Schema for general knowledge answers with confidence rating."""

  answer: str = Field(
    ...,
    description="A concise answer to the user's question",
  )
  confidence: int = Field(
    ...,
    description="Self-assessed confidence in the answer from 1 to 10",
  )
