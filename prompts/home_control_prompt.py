home_control_prompt = """Extract light control intent. Return JSON only.

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
