
from loguru import logger

from db.connection import get_db
from db.schemas import ConversationHistory, Weather

db = get_db()

logger.debug("Creating tables")

tables = [Weather, ConversationHistory]

try:
    for table in tables:
        db.create(table)
        logger.debug(f"Created table: {table.__name__}")
            

except Exception as error:
    logger.error(error)
