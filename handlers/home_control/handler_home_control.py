import os

os.environ["GGML_METAL_LOG_LEVEL"] = "0"
os.environ["GGML_LOG_LEVEL"] = "0"

import urllib3
from huesdk import Hue
from loguru import logger

from prompts.home_control_prompt import get_home_control_intent_prompt
from pydantic_types.home_control_intent_response import HomeControlIntentResponse
from utils.llm_structured_output import generate_structured_output

urllib3.disable_warnings()


def _get_hue_instance() -> Hue:
  """Get Hue bridge instance with certificate verification.

  Returns:
      Hue instance configured with the bridge IP and username
  """
  bridge_ip = os.environ["HUE_BRIDGE_IP"]

  # Connect and get username (first time only)
  username = Hue.connect(bridge_ip=bridge_ip)
  logger.debug(f"Connected to Hue bridge, username: {username}")

  hue_instance = Hue(bridge_ip=bridge_ip, username=username)
  return hue_instance


def _classify_intent(query: str, lights: list[dict]) -> dict:
  """Classify user intent and extract home control actions.

  Args:
      query: The user's home control query
      lights: List of light dictionaries with id, name, and state information

  Returns:
      Dictionary with keys: target, turn_on, brightness

  Example:
      >>> _classify_intent("Turn on bedroom lights", [{"id": "1", "name": "Bedroom"}])
      {"target": "1", "turn_on": true, "brightness": null}
  """

  # Try to parse and validate JSON response
  try:
    result = generate_structured_output(
      model_name=os.environ["MODEL_QWEN2.5"],
      user_prompt=query,
      system_prompt=get_home_control_intent_prompt(lights),
      pydantic_model=HomeControlIntentResponse,
      n_ctx=8192,
    )

    return result.model_dump()

  except Exception as e:
    logger.error(f"Failed to generate structured output. Error: {e}")
    return {"location": "UNKNOWN_LOCATION", "period": "CURRENT"}


def handle_home_control(query: str) -> str:
  """Handle home automation control requests.

  Args:
    query: The original user query

  Returns:
    Confirmation of home control action
  """
  instance = _get_hue_instance()

  if instance:
    logger.debug("Connected to Hue bridge, identifying intent")

    lights = instance.get_lights()

    # Convert Hue SDK Light objects to dictionaries for prompt formatting
    lights_dict = []
    for light in lights:
      lights_dict.append(
        {
          "id": str(light.id_),
          "name": light.name,
        }
      )

    logger.debug(lights_dict)

    intent = _classify_intent(query, lights_dict)
    logger.debug(intent)
    return "Hue bridge activated"

  else:
    return "Can not connect to Hue bridge at the moment"
