"""Journal skill — appends exchanges to the daily Conversations document."""

from datetime import date, datetime

from db.schemas import Conversations, ConversationExchange, Journal
from utils.log import logger


async def append_to_journal(question: str, answer: str) -> None:
    """Append a Q&A exchange to today's Conversations document."""
    today = date.today()
    exchange = ConversationExchange(timestamp=datetime.now(), question=question, answer=answer)

    doc = await Conversations.find_one(Conversations.date == today)
    if doc is None:
        await Conversations(date=today, exchanges=[exchange]).insert()
    else:
        doc.exchanges.append(exchange)
        await doc.save()


async def get_latest_journal_summary() -> str | None:
    """Return the summary from the most recent Journal entry."""
    journal = await (
        Journal.find()
        .sort(-Journal.datestamp)
        .first_or_none()
    )
    return journal.summary if journal else None
