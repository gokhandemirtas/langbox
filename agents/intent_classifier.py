import os
import time

from loguru import logger

from agents.router import route_intent
from prompts.intent_prompt import intent_prompt
from pydantic_types.intent_response import IntentResponse
from tts.tts import speak
from utils.llm_structured_output import generate_structured_output


async def run_intent_classifier():
  """Run the intent classifier agent and return the response."""

  start_time = time.time()
  user_query = input("\n \nHow may I assist? \n \n")

  # Use structured output to guarantee a valid intent classification
  logger.debug(f"Invoking intent classifier {os.environ['MODEL_QWEN2.5']}")
  result = generate_structured_output(
    model_name=os.environ["MODEL_QWEN2.5"],
    user_prompt=user_query,
    system_prompt=intent_prompt(),
    pydantic_model=IntentResponse,
    n_ctx=8192,
    max_tokens=50,
    n_gpu_layers=-1,
  )

  final_answer = result.intent
  logger.debug(f"Classified intent: {final_answer}")

  handler_response = await route_intent(intent=final_answer, query=user_query)

  # Process through conversational agent and save to DB
  logger.info(handler_response)
  speak(handler_response)

  elapsed_time = time.time() - start_time
  logger.info(
    f"Finished in total {elapsed_time:.2f}s",
  )
