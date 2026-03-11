from skills.base import Skill
from skills.home_control.skill import HOME_CONTROL_PROMPT, handle_home_control

home_control_skill = Skill(
    id="HOME_CONTROL",
    description="Control smart home devices — lights, groups, toggle state (Philips Hue)",
    system_prompt=HOME_CONTROL_PROMPT,  # Available light IDs/names are prepended at runtime
    handle=handle_home_control,
)
