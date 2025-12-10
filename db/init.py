import asyncio
import os

from beanie import init_beanie
from loguru import logger
from pymongo import AsyncMongoClient

from db.schemas import Conversations, Weather

collections = [Conversations, Weather]


async def init():
  try:
    logger.debug(f"Initiating Mongo DB with collections: {[col.__name__ for col in collections]}")
    client = AsyncMongoClient(
      f"""mongodb://{os.environ["MONGODB_USER"]}:{os.environ["MONGODB_PASSWORD"]}@{os.environ["MONGODB_HOST"]}:{os.environ["MONGODB_PORT"]}"""
    )

    await init_beanie(database=client.langbox, document_models=collections)
    logger.debug("Mongo DB initiated successfully")
  except Exception as error:
    logger.error(error)


if __name__ == "__main__":
  asyncio.run(init())
