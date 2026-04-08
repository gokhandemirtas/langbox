"""MCP server for the Langbox REST API.

Exposes the running Langbox assistant (port 8000) as MCP tools so Claude Code
can send queries, read notes, and read reminders through the API.
"""

import os

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("langbox-api", port=8182)

API_BASE = os.getenv("LANGBOX_API_URL", "http://localhost:8000")


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=API_BASE, timeout=120.0)


@mcp.tool()
async def query(text: str) -> str:
    """Send a natural language query to the Langbox assistant and get a response.

    Routes through the full intent classifier → skill pipeline, exactly as if
    typed at the CLI. Use this to ask AIDA anything — weather, notes, reminders,
    search, home control, Spotify, etc.

    Args:
        text: The query to send (e.g. "what's the weather in London", "play Radiohead")

    Returns:
        The assistant's natural language response
    """
    async with _client() as client:
        resp = await client.post("/query", json={"query": text})
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "(no response)")


@mcp.tool()
async def get_notes(category: str | None = None) -> str:
    """Retrieve notes saved by the user.

    Args:
        category: Optional filter — one of: read, listen, watch, eat, visit.
                  Omit to get all notes.

    Returns:
        A formatted list of notes with title, category, and content
    """
    async with _client() as client:
        resp = await client.get("/notes")
        resp.raise_for_status()
        notes = resp.json().get("notes", [])

    if category:
        notes = [n for n in notes if n.get("category") == category]

    if not notes:
        return f"No notes found{' in category ' + category if category else ''}."

    lines = [f"Found {len(notes)} note(s):\n"]
    for n in notes:
        cat = f"[{n['category']}] " if n.get("category") else ""
        lines.append(f"• {cat}{n['title']}  ({n['created_at'][:10]})")
        if n.get("content"):
            lines.append(f"  {n['content'][:200]}")
    return "\n".join(lines)


@mcp.tool()
async def get_reminders(include_completed: bool = False) -> str:
    """Retrieve the user's reminders.

    Args:
        include_completed: If True, include already-completed reminders (default False)

    Returns:
        A formatted list of reminders with datetime and description
    """
    async with _client() as client:
        params = {"include_completed": "true"} if include_completed else {}
        resp = await client.get("/reminders", params=params)
        resp.raise_for_status()
        reminders = resp.json().get("reminders", [])

    if not reminders:
        return "No reminders found."

    lines = [f"Found {len(reminders)} reminder(s):\n"]
    for r in reminders:
        status = "✓" if r["is_completed"] else "○"
        lines.append(f"{status} {r['reminder_datetime'][:16].replace('T', ' ')}  —  {r['description']}")
    return "\n".join(lines)


@mcp.tool()
async def health_check() -> str:
    """Check whether the Langbox API server is running and reachable.

    Returns:
        Status message indicating whether the API is up
    """
    try:
        async with _client() as client:
            resp = await client.get("/health", timeout=5.0)
            resp.raise_for_status()
            return f"Langbox API is up at {API_BASE}"
    except Exception as e:
        return f"Langbox API is not reachable at {API_BASE}: {e}"


def main() -> None:
    print("Langbox API MCP server running on port 8182")
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
