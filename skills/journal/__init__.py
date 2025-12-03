"""Journal skill — tracks daily conversation logs and generates summaries.

This is a background service skill, not registered in the skill registry.
"""

from skills.journal.skill import (
    append_to_journal,
    get_latest_journal_summary,
    summarize_pending_journal,
)

__all__ = ["append_to_journal", "get_latest_journal_summary", "summarize_pending_journal"]
