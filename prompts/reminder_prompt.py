"""Prompt for reminder/timer intent classification and extraction."""

reminderIntentPrompt = """Extract reminder or timer information from the user's query.

Determine:
1. Request type: "REMINDER" (for future dates) or "TIMER" (for immediate/short countdowns)
2. Date: Parse the date in ISO format (YYYY-MM-DD). For relative dates like "tomorrow", "next Monday", calculate from today's date. If no date is mentioned, return "UNKNOWN".
3. Text: What the user wants to be reminded about. If not specified, return "UNKNOWN".

IMPORTANT: If the user only says "set a reminder" or "remind me" without providing details, mark missing fields as "UNKNOWN".

Examples:
- "Remind me tomorrow to call mom" → {request_type: "REMINDER", reminder_date: "2025-12-26", reminder_text: "call mom"}
- "Set a reminder" → {request_type: "REMINDER", reminder_date: "UNKNOWN", reminder_text: "UNKNOWN"}
- "Remind me to call mom" → {request_type: "REMINDER", reminder_date: "UNKNOWN", reminder_text: "call mom"}
- "Remind me tomorrow" → {request_type: "REMINDER", reminder_date: "2025-12-26", reminder_text: "UNKNOWN"}
- "Set a timer for 5 minutes" → {request_type: "TIMER", reminder_date: "", reminder_text: "5 minutes timer"}
- "Remind me on Monday to submit the report" → {request_type: "REMINDER", reminder_date: "2025-12-30", reminder_text: "submit the report"}
"""
