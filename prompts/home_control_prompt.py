def get_home_control_prompt(lights_list: str, groups_list: str) -> str:
  """Generate home control intent prompt with available lights and groups.

  Args:
      lights_list: Formatted string of available lights
      groups_list: Formatted string of available light groups

  Returns:
      Complete system prompt with lights and groups context
  """
  return f"""Extract light control intent from user query. Return valid JSON only.

Available Light Groups:
{groups_list}

Available Individual Lights:
{lights_list}

JSON Schema:
{{"target_type": "ALL"|"GROUP"|"LIGHT", "target_id": int|null, "turn_on": boolean}}

Examples:
- "Turn on all lights" → {{"target_type": "ALL", "target_id": null, "turn_on": true}}
- "Lights off" → {{"target_type": "ALL", "target_id": null, "turn_on": false}}
- "Office lights on" → {{"target_type": "GROUP", "target_id": 1, "turn_on": true}}  (if Office is group ID 1)
- "Bedroom lights" → {{"target_type": "GROUP", "target_id": 2, "turn_on": true}}  (if Bedroom is group ID 2)
- "Turn off bedroom light" → {{"target_type": "LIGHT", "target_id": 3, "turn_on": false}}  (if a specific light ID 3 is named Bedroom)

Rules:
1. If user says "lights" or "all lights" without specifying a location, use target_type: "ALL"
2. **Prefer matching to GROUPS first** - if query mentions a room/area name (e.g., "office", "bedroom"), match to group name
3. Only use target_type: "LIGHT" if the query specifically mentions a single light name that doesn't match any group
4. Match names case-insensitive with partial matching (e.g., "office" matches "Office")
5. "on/turn on/switch on" = turn_on: true; "off/turn off/switch off" = turn_on: false; if not specified, default to true
6. Return only JSON, no markdown or extra text
"""
