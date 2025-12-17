from pydantic import BaseModel


class WeatherIntentResponse(BaseModel):
  location: str
  period: str
