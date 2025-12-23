def get_home_control_prompt(lights_list: str) -> str:
  """Generate home control intent prompt with available lights.

  Args:
      lights_list: Formatted string of available lights

  Returns:
      Complete system prompt with lights context
  """
  return f"""Extract light control intent from user query. Return valid JSON only.

Available Lights:
{lights_list}

JSON Schema:
{{"target": "ALL", "turn_on": boolean}}
or
{{"target": "light_id", "turn_on": boolean}}

Examples:
- "Turn on all lights" → {{"target": "ALL", "turn_on": true}}
- "Lights off" → {{"target": "ALL", "turn_on": false}}
- "Turn off lights" → {{"target": "ALL", "turn_on": false}}
- "Bedroom off" → {{"target": "2", "turn_on": false}}

Rules:
1. If user says just "lights" or "all lights" without specifying a room, use "ALL"
2. Match room names ONLY from the available lights list above (case-insensitive, partial matches)
3. If no specific room/light name is mentioned, use "ALL"
4. "on/turn on/switch on" = turn_on: true; "off/turn off/switch off" = turn_on: false
5. Return only JSON, no markdown or extra text
"""
