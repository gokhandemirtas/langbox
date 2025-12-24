home_control_prompt = """Extract light control intent. Return JSON only.

Schema: {"type": "ALL"|"GROUP"|"LIGHT", "id": int|null, "on": bool}

Rules:
1. "all lights" → type: "ALL", id: null
2. Room name (e.g. "office") → match to GROUP first, then LIGHT
3. on/turn on = on: true; off/turn off = on: false
4. Match names case-insensitive
5. Return complete JSON matching schema

Examples:
{"type": "ALL", "id": null, "on": true}
{"type": "GROUP", "id": 1, "on": false}
{"type": "LIGHT", "id": 3, "on": true}"""
