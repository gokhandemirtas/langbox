from pydantic import BaseModel


class WeatherOutline(BaseModel):
  location: str
  period: str
