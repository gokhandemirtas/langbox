import os

os.environ["GGML_METAL_LOG_LEVEL"] = "0"
os.environ["GGML_LOG_LEVEL"] = "0"

from loguru import logger
from pydantic import BaseModel
from typing import Optional

from skills.home_control.hue_client import HueBridgeClient
from utils.llm_structured_output import generate_structured_output

HOME_CONTROL_PROMPT = """Extract light control intent. Return JSON only.

Schema: {"type": "ALL"|"GROUP"|"LIGHT", "id": int|null, "on": bool|null}

Rules:
1. If no specific light or group is mentioned → type: "ALL", id: null, example "lights off"
2. Room name (e.g. "office") → match to GROUP first, then LIGHT, example "living room lights on"
3. on/turn on = on: true; off/turn off = on: false
4. toggle/switch = on: null (means toggle current state)
5. Match names case-insensitive
6. Return complete JSON matching schema

Examples:
{"type": "ALL", "id": null, "on": true}
{"type": "GROUP", "id": 1, "on": false}
{"type": "LIGHT", "id": 3, "on": true}
{"type": "ALL", "id": null, "on": null}
{"type": "GROUP", "id": 2, "on": null}"""


class HomeControlIntentResponse(BaseModel):
  type: str
  id: Optional[int] = None
  on: Optional[bool] = None


def _classify_intent(query: str, lights: str, groups: str) -> dict:
  try:
    result = generate_structured_output(
      model_name=os.environ["MODEL_INTENT_CLASSIFIER"],
      user_prompt=query,
      system_prompt=f"""Groups: {groups}, Lights: {lights}, {HOME_CONTROL_PROMPT}""",
      pydantic_model=HomeControlIntentResponse,
    )
    return result.model_dump()
  except Exception as e:
    logger.error(f"Failed to generate structured output. Error: {e}")
    return {"type": "ALL", "id": None, "on": True}


async def handle_home_control(query: str) -> str:
  """Handle home automation control requests."""
  try:
    hue_client = HueBridgeClient()
    config = await hue_client.get_configuration()
    lights_list = hue_client.get_lights_formatted(config)
    groups_list = hue_client.get_groups_formatted(config)

    intent = _classify_intent(query, lights_list, groups_list)
    target_type = intent.get("type")
    target_id = intent.get("id")
    turn_on = intent.get("on")

    logger.debug(f"Detected secondary intent: {intent}")

    if turn_on is None:
      turn_on = not await hue_client.are_lights_on(target_type, target_id)
      logger.debug(f"Toggle resolved to: {'on' if turn_on else 'off'}")

    if target_type == "GROUP" and target_id is not None:
      return await hue_client.control_group(target_id, turn_on)
    elif target_type == "LIGHT" and target_id is not None:
      return await hue_client.control_light(target_id, turn_on)
    else:
      results = []
      for group in config.groups:
        result = await hue_client.control_group(group.id, turn_on)
        results.append(result)
      return "\n".join(results)

  except Exception as error:
    logger.error(f"Failed to control home device. Error: {error}")
    return "Cannot connect to Hue bridge at the moment"
