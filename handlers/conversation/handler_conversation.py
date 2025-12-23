import os
from datetime import datetime

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from agents.agent_factory import create_llm_agent
from db.schemas import Conversations
from prompts.conversation_prompt import conversation_prompt

# Lazy initialization of conversation agent
_conversation_agent = None


def _get_conversation_agent():
  """Get or create the conversation agent."""
  global _conversation_agent
  if _conversation_agent is None:
    _conversation_agent = create_llm_agent(
      model_name=os.environ.get("MODEL_QWEN2.5"),
      temperature=0.7,
      top_p=0.9,
      top_k=40,
      repeat_penalty=1,
    )
  return _conversation_agent


async def handle_conversation(user_query: str, handler_response: str) -> str:
  """Process handler response through conversational agent and save to DB.

  This function takes the original user query and the handler's response,
  processes it through a conversational LLM to make it more natural,
  saves the interaction to the database, and prompts for the next question.

  Args:
      user_query: The original user question
      handler_response: The response from the specialized handler

  Returns:
      The conversational agent's natural response
  """
  logger.debug(handler_response)

  # Generate a conversational response using the LLM
  messages = [
    SystemMessage(content=conversation_prompt()),
    HumanMessage(content=f"User asked: {user_query}\n\nInformation to use: {handler_response}"),
  ]

  agent = _get_conversation_agent()
  response = agent.invoke({"messages": messages})
  conversational_response = response["messages"][-1].content.strip()

  # Save to database
  try:
    conversation_record = Conversations(
      datestamp=datetime.now().date(),
      question=user_query,
      answer=conversational_response,
      raw=handler_response,
    )
    await conversation_record.insert()
    logger.debug("Conversation saved to database")
  except Exception as e:
    logger.error(f"Failed to save conversation to database: {e}")

  # Display the response to the user
  logger.info(f"\n{conversational_response}\n")

  return conversational_response
