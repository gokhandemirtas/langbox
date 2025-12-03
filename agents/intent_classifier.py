import os
import time

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from loguru import logger
from pydantic import BaseModel

from agents.agent_factory import create_llm_agent
from agents.router import route_intent
from prompts.intent_prompt import intent_prompt


class ResponseFormat(BaseModel):
  model: str
  elapsed: str
  answer: str


# Lazy initialization of agent
_agent = None

def _get_agent():
  """Get or create the intent classifier agent."""
  global _agent
  if _agent is None:
    _agent = create_llm_agent(
      model_name=os.environ.get('MODEL_INTENT_CLASSIFIER'),
      temperature=0.0,
      n_ctx=8192,
      n_gpu_layers=8,
      n_batch=1000,
      max_tokens=512,
      repeat_penalty=1.2,
      top_p=0.1,
      top_k=10,
      verbose=False,
      checkpointer=InMemorySaver(),
    )
  return _agent

def run_intent_classifier():
  """Run the intent classifier agent and return the response."""
  start_time = time.time()

  # Get the user's query
  user_query = input("How may I assist? \n \n")

  # Invoke the agent with the user's question
  logger.info(f"Invoking intent classifier {os.environ['MODEL_INTENT_CLASSIFIER']}")
  agent = _get_agent()
  response = agent.invoke(
    {"messages": [
      SystemMessage(content=intent_prompt()),
      HumanMessage(content=user_query)
    ]},
    {"configurable": {"thread_id": "1"}}
  )

  elapsed_time = time.time() - start_time

  # Extract the final answer from the last message
  final_message = response["messages"][-1]
  final_answer = final_message.content

  # Create ResponseFormat object
  response_format = ResponseFormat(
    model= f"{os.environ['MODEL_INTENT_CLASSIFIER']}",
    elapsed=f"{elapsed_time:.2f}s",
    answer=final_answer
  )

  # Route to the appropriate handler based on classified intent
  logger.info(f"Finished in {elapsed_time:.2f}s",)
  route_intent(intent=final_answer, query=user_query)

  return response_format
