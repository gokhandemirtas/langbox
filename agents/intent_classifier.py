
import multiprocessing
import os
import sys
import time

from langchain.agents import create_agent
from langchain_community.chat_models import ChatLlamaCpp
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from loguru import logger
from pydantic import BaseModel

from agents.router import route_intent
from prompts.intent_prompt import intent_prompt


class ResponseFormat(BaseModel):
  model: str
  elapsed: str
  answer: str


# Redirect stderr during model initialization to suppress Metal logs
stderr_backup = sys.stderr
sys.stderr = open(os.devnull, 'w')

try:
  llm = ChatLlamaCpp(
    temperature=0.0,  # Set to 0 for maximum determinism
    model_path=f"{os.environ['MODEL_PATH']}/{os.environ['MODEL_INTENT_CLASSIFIER']}",
    n_ctx=10000,
    n_gpu_layers=8,
    n_batch=1000,  # Should be between 1 and n_ctx, consider the amount of VRAM in your GPU.
    max_tokens=512,
    n_threads=multiprocessing.cpu_count() - 1,
    repeat_penalty=1.2,  # Reduced from 1.5 to avoid overly constrained output
    top_p=0.1,  # Reduced from 0.5 for more focused sampling
    top_k=10,  # Added: limits vocabulary to top 10 tokens for more deterministic output
    verbose=False,
  )
finally:
  sys.stderr.close()
  sys.stderr = stderr_backup

agent = create_agent(
  model=llm,
  checkpointer=InMemorySaver(),
)

def run_intent_classifier():
  """Run the intent classifier agent and return the response."""
  start_time = time.time()

  # Get the user's query
  user_query = input("How may I assist? \n \n")

  # Invoke the agent with the user's question
  logger.info(f"Invoking intent classifier {os.environ['MODEL_INTENT_CLASSIFIER']}")
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
