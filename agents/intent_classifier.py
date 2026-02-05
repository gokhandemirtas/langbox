import os
import time

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from agents.agent_factory import create_llm_agent
from agents.router import route_intent
from prompts.intent_prompt import intent_prompt

def _get_agent():
  """Create the intent classifier agent. Previous LLM instances are freed by the factory."""
  return create_llm_agent(
    model_name=os.environ.get("MODEL_QWEN2.5"),
    temperature=0.0,
    n_ctx=8192,
    n_gpu_layers=-1,
    n_batch=1000,
    max_tokens=512,
    repeat_penalty=1.2,
    top_p=0.1,
    top_k=10,
    verbose=False,
  )


async def run_intent_classifier():
  """Run the intent classifier agent and return the response."""
  from handlers.conversation.handler_conversation import handle_conversation

  start_time = time.time()

  # Get the user's query
  user_query = input("\n \nHow may I assist? \n \n")

  # Invoke the agent with the user's question
  logger.debug(f"Invoking intent classifier {os.environ['MODEL_QWEN2.5']}")
  agent = _get_agent()
  response = agent.invoke(
    {"messages": [SystemMessage(content=intent_prompt()), HumanMessage(content=user_query)]},
  )

  # Extract the final answer from the last message
  final_message = response["messages"][-1]
  final_answer = final_message.content

  handler_response = await route_intent(intent=final_answer, query=user_query)

  # Process through conversational agent and save to DB
  logger.info(handler_response)

  elapsed_time = time.time() - start_time
  logger.info(
    f"Finished in total {elapsed_time:.2f}s",
  )
