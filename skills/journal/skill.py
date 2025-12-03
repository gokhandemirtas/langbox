"""Journal skill — tracks daily conversation logs and generates summaries."""

import os
from datetime import date, datetime

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from db.schemas import Journal, JournalEntry

_SUMMARY_PROMPT = """You are summarising a day's conversation log between a user and their personal assistant AIDA.
Write a concise, factual summary (3-8 sentences) covering the key topics discussed, decisions made, and anything the user expressed interest in or asked to follow up on.
Write in third person. Be specific — include names, numbers, and topics mentioned. Do not add commentary or opinions."""


async def append_to_journal(question: str, answer: str) -> None:
    """Append an exchange to today's journal, creating the document if needed."""
    today = date.today()
    entry = JournalEntry(timestamp=datetime.now(), question=question, answer=answer)

    journal = await Journal.find_one(Journal.date == today)
    if journal is None:
        await Journal(date=today, entries=[entry]).insert()
    else:
        journal.entries.append(entry)
        await journal.save()


async def summarize_pending_journal() -> str | None:
    """Find the most recent past journal without a summary, generate one, and save it.

    Returns the summary text if one was generated, None otherwise.
    """
    journal = await (
        Journal.find(Journal.date < date.today(), Journal.summary == None)
        .sort(-Journal.date)
        .first_or_none()
    )
    if journal is None or not journal.entries:
        return None

    lines = [f"Conversation log for {journal.date}:"]
    for e in journal.entries:
        ts = e.timestamp.strftime("%H:%M")
        lines.append(f"[{ts}] User: {e.question}")
        lines.append(f"[{ts}] AIDA: {e.answer}")
    log_text = "\n".join(lines)

    from agents.agent_factory import create_llm
    llm = create_llm(
        model_name=os.environ.get("MODEL_GENERALIST"),
        temperature=0.3,
        max_tokens=512,
        top_p=0.9,
        top_k=40,
        repeat_penalty=1,
    )
    response = await llm.ainvoke([
        SystemMessage(content=_SUMMARY_PROMPT),
        HumanMessage(content=log_text),
    ])
    summary = response.content.strip()

    journal.summary = summary
    await journal.save()
    logger.info(f"Journal summarised for {journal.date}")
    return summary


async def get_latest_journal_summary() -> str | None:
    """Return the summary from the most recent past journal that has one."""
    journal = await (
        Journal.find(Journal.date < date.today(), Journal.summary != None)
        .sort(-Journal.date)
        .first_or_none()
    )
    return journal.summary if journal else None
