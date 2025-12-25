def get_conversation_prompt(systemInput: str) -> str:
  """Generate the system prompt for the conversational agent.

  Args:
      systemInput: Natural language response from the specialized handler

  Returns:
      The system prompt for continuing the conversation naturally
  """
  return f"""You are a helpful personal assistant. A specialized handler provided this response:

{systemInput}

Continue the conversation naturally by adding personality, context, or helpful suggestions. Don't repeat what was said - build on it conversationally. Be warm, concise, and engaging."""
