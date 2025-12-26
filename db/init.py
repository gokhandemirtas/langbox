import asyncio
import os

from beanie import init_beanie
from loguru import logger
from pymongo import AsyncMongoClient

from db.schemas import Conversations, Credentials, HueConfiguration, Reminders, Weather

collections = [Conversations, Credentials, HueConfiguration, Reminders, Weather]


async def init():
  try:
    logger.debug(f"Initiating Mongo DB with collections: {[col.__name__ for col in collections]}")
    client = AsyncMongoClient(
      f"""mongodb://{os.environ["MONGODB_USER"]}:{os.environ["MONGODB_PASSWORD"]}@{os.environ["MONGODB_HOST"]}:{os.environ["MONGODB_PORT"]}""",
      timeoutMS=1000,
    )

    await init_beanie(database=client.langbox, document_models=collections)
    logger.debug("Mongo DB initiated successfully")
  except Exception as error:
    logger.error(error)
    exit("Mongo DB failed to start")


if __name__ == "__main__":
  asyncio.run(init())
