from typing import Literal, Optional

from pydantic import BaseModel, Field


class FinanceIntentResponse(BaseModel):
  """Strict schema for finance intent classification."""

  ticker: str = Field(
    ..., description="Stock ticker symbol from the available tickers list, or 'UNKNOWN_TICKER' if not found"
  )
  dataType: Literal["CURRENT", "HISTORICAL"] = Field(..., description="Either CURRENT or HISTORICAL")
  period: Optional[Literal["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"]] = Field(
    None, description="Time period for historical data, null for current data"
  )
