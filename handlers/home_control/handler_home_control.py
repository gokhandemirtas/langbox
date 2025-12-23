import os

os.environ["GGML_METAL_LOG_LEVEL"] = "0"
os.environ["GGML_LOG_LEVEL"] = "0"

import urllib3
from huesdk import Hue
from loguru import logger

from prompts.home_control_prompt import get_home_control_prompt
from pydantic_types.home_control_intent_response import HomeControlIntentResponse
from utils.llm_structured_output import generate_structured_output


def _get_hue_instance() -> Hue:
  """Get Hue bridge instance with certificate verification.

  Returns:
      Hue instance configured with the bridge IP and username
  """
  bridge_ip = os.environ["HUE_BRIDGE_IP"]

  # Connect and get username (first time only)
  username = Hue.connect(bridge_ip=bridge_ip)
  logger.debug("Connected to Hue bridge")

  hue_instance = Hue(bridge_ip=bridge_ip, username=username)
  return hue_instance


def _get_lights(instance: Hue) -> str:
  """Get list of lights from Hue bridge.

  Args:
      instance: Hue bridge instance

  Returns:
      Formatted string of lights with IDs and names
  """
  logger.debug("Getting lights from Hue bridge")

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
  lights_list = "\n".join(
    [f'    - ID: "{light["id"]}", Name: "{light["name"]}"' for light in lights_dict]
  )
  return lights_list


def _classify_intent(query: str, lights: list[str]) -> dict:
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
      model_name=os.environ["MODEL_LLAMA2_7B"],
      user_prompt=query,
      system_prompt=get_home_control_prompt(lights),
      pydantic_model=HomeControlIntentResponse,
      n_ctx=8192,
    )

    return result.model_dump()

  except Exception as e:
    logger.error(f"Failed to generate structured output. Error: {e}")
    return {"target": "UNKNOWN_TARGET", "period": "CURRENT"}


def handle_home_control(query: str) -> str:
  """Handle home automation control requests.

  Args:
      query: The original user query

  Returns:
      Confirmation of home control action
  """
  try:
    # Get single Hue instance for the entire handler
    instance = _get_hue_instance()

    # Get lights list
    lights_list = _get_lights(instance)

    # Classify intent
    intent = _classify_intent(query, lights_list)
    target = intent.get("target")
    turn_on = intent.get("turn_on")
    action: str

    # Control lights based on target
    if target == "ALL":
      instance.on() if turn_on else instance.off()
      action = f"All lights turned {'on' if turn_on else 'off'}"
    else:
      light = instance.get_light(id_=target)
      light.on() if turn_on else light.off()
      action = f"{light.name} turned {'on' if turn_on else 'off'}"

    logger.debug(intent)
    return action

  except Exception as error:
    logger.error(f"Failed to control home device. Error: {error}")
    return "Cannot connect to Hue bridge at the moment"
