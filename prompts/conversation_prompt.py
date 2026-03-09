def get_conversation_prompt(systemInput: str) -> str:
  """Generate the system prompt for the conversational agent.

  Args:
      systemInput: Natural language response from the specialized handler

  Returns:
      The system prompt for continuing the conversation naturally
  """
  return f"""You are a warm, concise personal assistant. Present the following information naturally to the user.

{systemInput}

Keep all lists, numbers, and specific data exactly as given — do not add or invent facts. If the response above is empty, vague, or says it needs more context, use your conversation history to answer the user's question directly instead."""
