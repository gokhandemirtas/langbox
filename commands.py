"""Built-in slash commands for the assistant CLI.

Available commands:
  /save           — summarise the current session
  /clear          — wipe the in-memory conversation history
  /history        — print the current session history to the terminal
  /analyze        — extract personal facts from this session into your persona profile
  /planner <task> — run an autonomous multi-step planning agent
  /help           — list available commands
"""

from utils.log import logger

from agents.persona import get_active_identity
from skills.conversation.skill import _history

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_history() -> str:
    """Return the current session history as a plain-text string."""
    messages = list(_history)
    if not messages:
        return ""
    lines = []
    for msg in messages:
        role = "User" if msg.__class__.__name__ == "HumanMessage" else "Assistant"
        lines.append(f"{role}: {msg.content}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------

async def cmd_save() -> None:
    if not _history:
        print("[/save] Nothing to save — conversation history is empty.")
        return

    history_text = _format_history()

    from langchain_core.messages import HumanMessage, SystemMessage
    from skills.conversation.skill import _get_llm

    llm = _get_llm()
    summary_prompt = (
        f"{get_active_identity()} Summarise the following conversation between you and the user. "
        "Write in first person — 'I told the user...', 'the user asked me...'. "
        "Capture the key topics discussed and any conclusions or answers given. Be concise."
    )
    response = await llm.ainvoke([
        SystemMessage(content=summary_prompt),
        HumanMessage(content=history_text),
    ])
    summary = response.content.strip()
    print(f"[/save] Summary:\n{summary}")


async def cmd_clear() -> None:
    _history.clear()
    print("[/clear] Conversation history cleared.")


async def cmd_history() -> None:
    text = _format_history()
    if not text:
        print("[/history] No conversation history yet.")
    else:
        print(f"\n--- Session history ---\n{text}\n-----------------------")


async def cmd_planner(args: str) -> None:
    from skills.planner import run_planner

    task = args.strip()
    if not task:
        print("[/planner] Please provide a task. Usage: /planner <task>")
        return

    print(f"[/planner] Running agent on: {task}\n")
    response = await run_planner(task)
    print(response)


async def cmd_analyze() -> None:
    from skills.personalizer.skill import analyze_persona_from_log, get_persona_context
    from db.schemas import Conversations
    from datetime import date

    today = date.today()
    doc = await Conversations.find_one(Conversations.date == today)
    if not doc or not doc.exchanges:
        print("[/analyze] No conversations from today to analyse.")
        return

    await analyze_persona_from_log(doc.exchanges)
    context = get_persona_context()
    if context:
        print(f"[/analyze] Done ({len(doc.exchanges)} exchange(s) scanned).\n{context}")
    else:
        print(f"[/analyze] Done ({len(doc.exchanges)} exchange(s) scanned). No new personal facts found.")


async def cmd_ctx() -> None:
    import os
    from utils.llm_structured_output import _get_or_load_llama, _model_path

    model_name = os.environ.get("MODEL_GENERALIST")
    n_ctx = int(os.environ.get("MODEL_CTX", 8192))
    full_path = _model_path(model_name)
    llama = _get_or_load_llama(model_name, full_path, -1, {})

    history_text = _format_history()
    tokens = llama.tokenize(history_text.encode()) if history_text else []
    used = len(tokens)
    pct = used / n_ctx * 100

    bar_width = 40
    filled = int(bar_width * used / n_ctx)
    bar = "█" * filled + "░" * (bar_width - filled)

    print(f"\n[/ctx] Context usage: {used:,} / {n_ctx:,} tokens ({pct:.1f}%)")
    print(f"       [{bar}]\n")


async def cmd_note(args: str) -> None:
    """Create a note from the current conversation context.

    Usage:
      /note                  — auto-generate title + content from recent exchange
      /note <title>          — use provided title, generate content from context
    """
    import os
    from typing import Optional
    from pydantic import BaseModel, Field
    from skills.conversation.skill import get_current_topic
    from skills.notes.create import handle_create_note_from_context
    from db.schemas import NoteCategory
    from utils.llm_structured_output import generate_structured_output

    recent = _format_history()
    if not recent and not args:
        print("[/note] Nothing to note — no conversation history and no title provided.")
        return

    topic = get_current_topic() or ""

    class _NoteFromContext(BaseModel):
        title: str = Field(description="Short plain text title for this note")
        content: str = Field(description="Markdown content summarising what should be remembered")
        category: Optional[NoteCategory] = Field(
            default=None,
            description="Category: read, listen, watch, eat, visit. Omit if none applies.",
        )

    user_title_hint = f"The user wants to title it: {args}\n\n" if args else ""
    prompt = (
        f"{user_title_hint}"
        f"Current topic: {topic}\n\n"
        f"Recent conversation:\n{recent[-1500:]}"  # last 1500 chars of history
    )

    extracted = generate_structured_output(
        model_name=os.environ["MODEL_GENERALIST"],
        user_prompt=prompt,
        system_prompt=(
            "Extract a note from this conversation. "
            "Title: plain text, concise. "
            "Content: markdown, capture what the user should remember. "
            "Category: read/listen/watch/eat/visit only if clearly applicable."
        ),
        pydantic_model=_NoteFromContext,
        max_tokens=512,
    )

    result = await handle_create_note_from_context(
        title=extracted.title,
        content=extracted.content,
        category=extracted.category,
    )
    print(f"[/note] {result}")


async def cmd_flush_memory() -> None:
    """Delete all mem0 memories for the default user."""
    try:
        from utils.memory_client import _get_memory
        mem = _get_memory()
        mem.delete_all(user_id="default")
        print("[/flush-memory] All memories deleted.")
    except Exception as e:
        print(f"[/flush-memory] Failed: {e}")


async def cmd_help() -> None:
    print(
        "\nAvailable commands:\n"
        "  /save            — summarise and save the current session to the database\n"
        "  /clear           — wipe the in-memory conversation history\n"
        "  /history         — print session history to the terminal\n"
        "  /analyze         — extract personal facts from this session into your persona profile\n"
        "  /flush-memory    — delete all mem0 memories\n"
        "  /ctx             — show context window usage for the current session\n"
        "  /note [title]    — save a note from the current conversation context\n"
        "  /planner <task>  — run an autonomous multi-step planning agent\n"
        "  /help            — show this message\n"
    )


_COMMANDS = {
    "/save": cmd_save,
    "/clear": cmd_clear,
    "/history": cmd_history,
    "/analyze": cmd_analyze,
    "/flush-memory": cmd_flush_memory,
    "/ctx": cmd_ctx,
    "/note": cmd_note,
    "/planner": cmd_planner,
    "/help": cmd_help,
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def handle_command(user_input: str) -> bool:
    """Execute a slash command if recognised. Returns True if handled."""
    import inspect

    parts = user_input.strip().split(None, 1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if cmd not in _COMMANDS:
        print(f"Unknown command '{cmd}'. Type /help for available commands.")
        return True  # still consumed — don't pass to classifier
    try:
        fn = _COMMANDS[cmd]
        if inspect.signature(fn).parameters:
            await fn(args)
        else:
            await fn()
    except Exception as e:
        logger.error(f"Command {cmd} failed: {e}")
    return True
