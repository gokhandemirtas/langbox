import os
from typing import Any
from datetime import datetime, date

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("langbox-mongodb")

# MongoDB connection configuration
MONGODB_HOST = os.getenv("MONGODB_HOST", "localhost")
MONGODB_PORT = int(os.getenv("MONGODB_PORT", "27017"))
MONGODB_USER = os.getenv("MONGODB_USER", "admin")
MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD", "admin")
MONGODB_DB = os.getenv("MONGODB_DB", "langbox")

# Build connection string
MONGODB_URI = f"mongodb://{MONGODB_USER}:{MONGODB_PASSWORD}@{MONGODB_HOST}:{MONGODB_PORT}"

# Global database client
db_client = None
db = None


async def init_db():
  """Initialize MongoDB connection and Beanie ODM."""
  global db_client, db

  if db_client is None:
    db_client = AsyncIOMotorClient(MONGODB_URI)
    db = db_client[MONGODB_DB]

    # Initialize Beanie with document models
    # Note: We're initializing without importing the schemas to avoid dependencies
    # This allows the MCP server to work independently
    await init_beanie(database=db, document_models=[])


def serialize_doc(doc: dict[str, Any] | Any) -> dict[str, Any] | Any:
  """Serialize MongoDB document to JSON-serializable format."""
  if doc is None:
    return {}

  if isinstance(doc, dict):
    result = {}
    for key, value in doc.items():
      if key == "_id":
        result[key] = str(value)
      elif isinstance(value, datetime):
        result[key] = value.isoformat()
      elif isinstance(value, date):
        result[key] = value.isoformat()
      elif isinstance(value, list):
        result[key] = [serialize_doc(item) for item in value]
      elif isinstance(value, dict):
        result[key] = serialize_doc(value)
      else:
        result[key] = value
    return result
  return doc


@mcp.tool()
async def list_collections() -> str:
  """List all collections in the langbox database.

  Returns:
      A formatted string listing all collection names
  """
  await init_db()
  collections = await db.list_collection_names()
  return f"Collections in database:\n" + "\n".join(f"  - {col}" for col in collections)


@mcp.tool()
async def query_collection(
  collection: str, filter: dict[str, Any] | None = None, limit: int = 10
) -> str:
  """Query documents from a collection with optional filters.

  Args:
      collection: Name of the collection to query
      filter: MongoDB filter query (optional). Example: {"question": {"$regex": "weather"}}
      limit: Maximum number of documents to return (default: 10)

  Returns:
      A formatted string with the query results
  """
  await init_db()

  collections = await db.list_collection_names()
  if collection not in collections:
    return f"Error: Collection '{collection}' not found"

  filter_query = filter or {}

  try:
    cursor = db[collection].find(filter_query).limit(limit)
    documents = []
    async for doc in cursor:
      documents.append(serialize_doc(doc))

    if not documents:
      return f"No documents found in '{collection}' matching the filter"

    result = f"Found {len(documents)} document(s) in '{collection}':\n\n"
    for i, doc in enumerate(documents, 1):
      result += f"Document {i}:\n"
      for key, value in doc.items():
        result += f"  {key}: {value}\n"
      result += "\n"

    return result
  except Exception as e:
    return f"Error querying collection: {str(e)}"


@mcp.tool()
async def count_documents(collection: str, filter: dict[str, Any] | None = None) -> str:
  """Count documents in a collection matching a filter.

  Args:
      collection: Name of the collection to count
      filter: MongoDB filter query (optional)

  Returns:
      A string with the count of matching documents
  """
  await init_db()

  collections = await db.list_collection_names()
  if collection not in collections:
    return f"Error: Collection '{collection}' not found"

  filter_query = filter or {}

  try:
    count = await db[collection].count_documents(filter_query)
    return f"Collection '{collection}' has {count} document(s) matching the filter"
  except Exception as e:
    return f"Error counting documents: {str(e)}"


@mcp.tool()
async def get_recent_conversations(limit: int = 10) -> str:
  """Get the most recent conversation records.

  Args:
      limit: Maximum number of conversations to return (default: 10)

  Returns:
      A formatted string with recent conversations
  """
  await init_db()

  try:
    cursor = db.conversations.find().sort("datestamp", -1).limit(limit)
    conversations = []
    async for doc in cursor:
      conversations.append(serialize_doc(doc))

    if not conversations:
      return "No conversations found in database"

    result = f"Found {len(conversations)} recent conversation(s):\n\n"
    for i, conv in enumerate(conversations, 1):
      result += f"Conversation {i}:\n"
      result += f"  Date: {conv.get('datestamp', 'N/A')}\n"
      result += f"  Question: {conv.get('question', 'N/A')}\n"
      result += f"  Answer: {conv.get('answer', 'N/A')}\n"
      if "raw" in conv:
        result += (
          f"  Raw Response: {conv.get('raw', 'N/A')[:100]}...\n"  # Truncate raw for readability
        )
      result += "\n"

    return result
  except Exception as e:
    return f"Error getting conversations: {str(e)}"


@mcp.tool()
async def search_conversations(search_text: str, limit: int = 10) -> str:
  """Search conversations by text in question or answer fields.

  Args:
      search_text: Text to search for in questions and answers
      limit: Maximum number of results to return (default: 10)

  Returns:
      A formatted string with matching conversations
  """
  await init_db()

  try:
    # Search in both question and answer fields using regex
    filter_query = {
      "$or": [
        {"question": {"$regex": search_text, "$options": "i"}},
        {"answer": {"$regex": search_text, "$options": "i"}},
      ]
    }

    cursor = db.conversations.find(filter_query).sort("datestamp", -1).limit(limit)
    conversations = []
    async for doc in cursor:
      conversations.append(serialize_doc(doc))

    if not conversations:
      return f"No conversations found matching '{search_text}'"

    result = f"Found {len(conversations)} conversation(s) matching '{search_text}':\n\n"
    for i, conv in enumerate(conversations, 1):
      result += f"Conversation {i}:\n"
      result += f"  Date: {conv.get('datestamp', 'N/A')}\n"
      result += f"  Question: {conv.get('question', 'N/A')}\n"
      result += f"  Answer: {conv.get('answer', 'N/A')}\n"
      result += "\n"

    return result
  except Exception as e:
    return f"Error searching conversations: {str(e)}"


def main():
  """Initialize and run the MCP server."""
  print("MCP Server up and running")
  mcp.run(transport="streamable-http")


if __name__ == "__main__":
  main()
