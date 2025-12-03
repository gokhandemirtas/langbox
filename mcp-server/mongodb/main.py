import os
from typing import Any
from datetime import datetime, date

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("langbox-mongodb", port=8181)

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
async def get_recent_journal_entries(limit: int = 5) -> str:
  """Get the most recent journal entries (AIDA's first-person narratives, one per day).

  Args:
      limit: Maximum number of journal days to return (default: 5)

  Returns:
      A formatted string with recent journal entries and their summaries
  """
  await init_db()

  try:
    cursor = db.journal.find().sort("datestamp", -1).limit(limit)
    entries = []
    async for doc in cursor:
      entries.append(serialize_doc(doc))

    if not entries:
      return "No journal entries found in database"

    result = f"Found {len(entries)} journal entry/entries:\n\n"
    for entry in entries:
      result += f"Date: {entry.get('datestamp', 'N/A')}\n"
      result += f"Summary: {entry.get('summary', '(empty)')}\n\n"

    return result
  except Exception as e:
    return f"Error getting journal entries: {str(e)}"


@mcp.tool()
async def search_journal(search_text: str, limit: int = 10) -> str:
  """Search conversation exchanges and journal summaries for matching text.

  Searches both the raw Q&A exchanges in the conversations collection and
  AIDA's journal summaries.

  Args:
      search_text: Text to search for
      limit: Maximum number of results to return (default: 10)

  Returns:
      A formatted string with matching results
  """
  await init_db()

  try:
    results = []

    # Search raw exchanges in conversations collection
    conv_filter = {
      "$or": [
        {"exchanges.question": {"$regex": search_text, "$options": "i"}},
        {"exchanges.answer": {"$regex": search_text, "$options": "i"}},
        {"compacted": {"$regex": search_text, "$options": "i"}},
      ]
    }
    conv_cursor = db.conversations.find(conv_filter).sort("date", -1).limit(limit)
    async for doc in conv_cursor:
      results.append(("conversation", serialize_doc(doc)))

    # Search journal summaries
    journal_filter = {"summary": {"$regex": search_text, "$options": "i"}}
    journal_cursor = db.journal.find(journal_filter).sort("datestamp", -1).limit(limit)
    async for doc in journal_cursor:
      results.append(("journal", serialize_doc(doc)))

    if not results:
      return f"No results found matching '{search_text}'"

    output = f"Found {len(results)} result(s) matching '{search_text}':\n\n"
    for source, entry in results:
      if source == "conversation":
        output += f"[Conversation] Date: {entry.get('date', 'N/A')}\n"
        for ex in entry.get("exchanges", []):
          q = ex.get("question", "")
          a = ex.get("answer", "")
          if search_text.lower() in q.lower() or search_text.lower() in a.lower():
            output += f"  [{ex.get('timestamp', '')}] Q: {q[:120]}\n"
            output += f"  [{ex.get('timestamp', '')}] A: {a[:160]}\n"
      else:
        output += f"[Journal] Date: {entry.get('datestamp', 'N/A')}\n"
        output += f"  {entry.get('summary', '')[:200]}\n"
      output += "\n"

    return output
  except Exception as e:
    return f"Error searching: {str(e)}"


def main():
  """Initialize and run the MCP server."""
  print("MCP Server up and running")
  mcp.run(transport="streamable-http")


if __name__ == "__main__":
  main()
