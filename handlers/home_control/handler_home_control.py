import os

os.environ["GGML_METAL_LOG_LEVEL"] = "0"
os.environ["GGML_LOG_LEVEL"] = "0"

from loguru import logger

from prompts.home_control_prompt import home_control_prompt
from pydantic_types.home_control_intent_response import HomeControlIntentResponse
from utils.hue_bridge_client import HueBridgeClient
from utils.llm_structured_output import generate_structured_output


def _classify_intent(query: str, lights: str, groups: str) -> dict:
  """Classify user intent and extract home control actions.

  Best results with MODEL_HERMES_2_PRO

  Args:
      query: The user's home control query
      lights: Formatted string of available lights
      groups: Formatted string of available light groups

  Returns:
      Dictionary with keys: target_type, target_id, turn_on

  Example:
      >>> _classify_intent("Turn on office lights", lights_str, groups_str)
      {"type": "GROUP", "id": 1, "on": True}
  """
  try:
    result = generate_structured_output(
      model_name=os.environ["MODEL_HERMES_2_PRO"],
      user_prompt=query,
      system_prompt=f"""Groups: {groups}, Lights: {lights}, {home_control_prompt}""",
      pydantic_model=HomeControlIntentResponse,
    )

    return result.model_dump()

  except Exception as e:
    logger.error(f"Failed to generate structured output. Error: {e}")
    return {"type": "ALL", "id": None, "on": True}


async def handle_home_control(query: str) -> str:
  """Handle home automation control requests.

  Args:
      query: The original user query

  Returns:
      Confirmation of home control action
  """
  try:
    # Initialize Hue bridge client
    hue_client = HueBridgeClient()

    # Get configuration (cached or fresh)
    config = await hue_client.get_configuration()

    # Get formatted lights and groups lists for prompt
    lights_list = hue_client.get_lights_formatted(config)
    groups_list = hue_client.get_groups_formatted(config)

    # Classify intent using LLM
    intent = _classify_intent(query, lights_list, groups_list)
    target_type = intent.get("type")
    target_id = intent.get("id")
    turn_on = intent.get("on")

    logger.debug(f"Intent: {intent}")

    # Control lights based on target type
    if target_type == "ALL":
      action = await hue_client.control_all_lights(turn_on)
    elif target_type == "GROUP":
      action = await hue_client.control_group(target_id, turn_on)
    elif target_type == "LIGHT":
      action = await hue_client.control_light(target_id, turn_on)
    else:
      action = await hue_client.control_all_lights(turn_on)

    return action

  except Exception as error:
    logger.error(f"Failed to control home device. Error: {error}")
    return "Cannot connect to Hue bridge at the moment"
