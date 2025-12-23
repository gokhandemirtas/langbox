def get_home_control_intent_prompt(available_lights: list[dict]) -> str:
  """Generate home control intent classification prompt with available lights.

  Args:
      available_lights: List of light dictionaries with 'id' and 'name' keys
          Example: [{"id": "1", "name": "Living Room"}, {"id": "2", "name": "Bedroom"}]

  Returns:
      Formatted prompt string with available lights injected
  """
  # Format available lights as a readable list
  lights_list = "\n".join(
    [f'    - ID: "{light["id"]}", Name: "{light["name"]}"' for light in available_lights]
  )

  return f"""Extract light control intent from user query. Return valid JSON only.

Available Lights:
{lights_list}

JSON Schema:
{{"target": "ALL" or light_id, "turn_on": boolean, "brightness": 30}}
or
{{"target": "ALL" or light_id, "turn_on": boolean, "brightness": null}}

Examples:
- "Turn on all lights" → {{"target": "ALL", "turn_on": true, "brightness": null}}
- "Bedroom off" → {{"target": "2", "turn_on": false, "brightness": null}}
- "Dim living room to 30" → {{"target": "1", "turn_on": true, "brightness": 30}}

Rules:
1. Match room names flexibly (case-insensitive, partial matches, ignore "light/lights/lamp/the")
2. Use "ALL" if no specific light matched or if user says "all/everything"
3. "on/turn on/switch on" = turn_on: true; "off/turn off" = turn_on: false
4. "dim" or brightness number without on/off = turn_on: true
5. Return only JSON, no markdown or extra text
"""


homeControlIntentPrompt = get_home_control_intent_prompt
