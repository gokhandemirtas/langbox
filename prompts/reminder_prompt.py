"""Prompt for reminder/timer intent classification and extraction."""

reminderIntentPrompt = """Extract reminder or timer information from the user's query and populate JSON with three fields:

1. TYPE: Determine if this is a "REMINDER" (for future dates) or "TIMER" (for immediate/short countdowns)

2. DATETIME: Extract ONLY the date/time expression from the query. Use fuzzy-date format. Leave EMPTY if not mentioned.
   - Extract phrases like: "tomorrow", "tomorrow 5pm", "next monday 3pm", "in two weeks", "in 3 days"
   - DO NOT convert to ISO format - keep the natural language expression
   - Examples: "tomorrow", "next monday at 3pm", "in two weeks", "december 30"

3. DESCRIPTION: Extract what the user wants to be reminded about (the purpose/goal/reason). Leave EMPTY if not specified.
   - Extract the action or event: "call mom", "dentist appointment", "moms birthday", "submit report"
   - This is the WHY of the reminder

JSON format: {"type": "REMINDER" or "TIMER", "datetime": "fuzzy-date string or empty", "description": "reminder purpose or empty"}

Examples:
- "Remind me tomorrow to call mom" → {"type": "REMINDER", "datetime": "tomorrow", "description": "call mom"}
- "Set a reminder in two weeks" → {"type": "REMINDER", "datetime": "in two weeks", "description": ""}
- "Remind me to call mom" → {"type": "REMINDER", "datetime": "", "description": "call mom"}
- "Set a reminder for mom's birthday" → {"type": "REMINDER", "datetime": "", "description": "moms birthday"}
- "Remind me next monday at 3pm to submit report" → {"type": "REMINDER", "datetime": "next monday 3pm", "description": "submit report"}
- "Set a timer for 5 minutes" → {"type": "TIMER", "datetime": "5 minutes", "description": "5 minutes timer"}
- "Remind me in two weeks about the dentist" → {"type": "REMINDER", "datetime": "in two weeks", "description": "dentist"}
"""
