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

from agents.persona import AGENT_IDENTITY, AGENT_NAME
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
        f"{AGENT_IDENTITY} Summarise the following conversation between you and the user. "
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
    history_text = _format_history()
    if not history_text:
        print("[/analyze] No conversation history to analyse.")
        return

    from skills.personalizer.skill import update_persona_from_exchange

    exchanges = list(_history)
    if len(exchanges) < 2:
        print("[/analyze] Not enough history to analyse.")
        return

    # Walk paired (human, assistant) messages from history
    count = 0
    i = 0
    while i + 1 < len(exchanges):
        human = exchanges[i]
        assistant = exchanges[i + 1]
        if human.__class__.__name__ == "HumanMessage" and assistant.__class__.__name__ != "HumanMessage":
            await update_persona_from_exchange(question=human.content, answer=assistant.content)
            count += 1
        i += 2

    from skills.personalizer.skill import get_persona_context
    context = get_persona_context()
    if context:
        print(f"[/analyze] Done ({count} exchange(s) scanned).\n{context}")
    else:
        print(f"[/analyze] Done ({count} exchange(s) scanned). No new personal facts found.")


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


async def cmd_help() -> None:
    print(
        "\nAvailable commands:\n"
        "  /save           — summarise and save the current session to the database\n"
        "  /clear          — wipe the in-memory conversation history\n"
        "  /history        — print session history to the terminal\n"
        "  /analyze        — extract personal facts from this session into your persona profile\n"
        "  /ctx            — show context window usage for the current session\n"
        "  /planner <task> — run an autonomous multi-step planning agent\n"
        "  /help           — show this message\n"
    )


_COMMANDS = {
    "/save": cmd_save,
    "/clear": cmd_clear,
    "/history": cmd_history,
    "/analyze": cmd_analyze,
    "/ctx": cmd_ctx,
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
