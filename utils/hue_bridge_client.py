import os
from datetime import datetime, timedelta

import urllib3
from huesdk import Hue
from loguru import logger

from db.schemas import Credentials, HueConfiguration, HueLight, HueLightGroup

urllib3.disable_warnings()


class HueBridgeClient:
  """Client for interacting with Philips Hue bridge with configuration caching."""

  def __init__(self):
    self._instance = None

  async def _get_hue_username(self) -> str:
    """Retrieve Hue bridge username from database or connect to bridge.

    Returns:
        Hue bridge username string
    """
    try:
      username_doc = await Credentials.find_one()
      if username_doc:
        logger.debug("Hue Bridge username found")
        return username_doc.hueUsername
      else:
        logger.debug("Hue Bridge username not found, retrieving")
        username = Hue.connect(bridge_ip=os.environ["HUE_BRIDGE_IP"])
        newRecord = Credentials(
          hueUsername=username,
        )
        await newRecord.insert()
        return username
    except Exception as error:
      logger.error(f"Error getting Hue username: {error}")
      raise

  async def _get_hue_instance(self) -> Hue:
    """Get Hue bridge instance with certificate verification.

    Returns:
        Hue instance configured with the bridge IP and username
    """
    try:
      username = await self._get_hue_username()
      hue_instance = Hue(bridge_ip=os.environ["HUE_BRIDGE_IP"], username=username)
      return hue_instance

    except Exception as error:
      logger.error(error)
      return None

  async def _sync_hue_configuration(self, instance: Hue) -> HueConfiguration:
    """Fetch Hue configuration from SDK and save to database.

    Args:
        instance: Hue bridge instance

    Returns:
        HueConfiguration document with lights and groups
    """
    logger.debug("Syncing Hue configuration from bridge")

    # Fetch lights from SDK
    lights = instance.get_lights()
    lights_list = []
    for light in lights:
      lights_list.append(
        HueLight(
          id=light.id_,
          name=light.name,
          is_on=light.is_on,
          bri=light.bri if hasattr(light, "bri") else None,
          hue=light.hue if hasattr(light, "hue") else None,
          sat=light.sat if hasattr(light, "sat") else None,
        )
      )

    # Fetch groups from SDK
    groups = instance.get_groups()
    groups_list = []
    for group in groups:
      groups_list.append(
        HueLightGroup(
          id=group.id_,
          name=group.name,
        )
      )

    # Delete old configuration if exists
    await HueConfiguration.find_all().delete()

    # Create and save new configuration
    config = HueConfiguration(
      lights=lights_list,
      groups=groups_list,
      lastUpdated=datetime.now().date(),
    )
    await config.insert()

    logger.debug(f"Synced {len(lights_list)} lights and {len(groups_list)} groups")
    return config

  async def get_configuration(self) -> HueConfiguration:
    """Get Hue configuration from database or sync from bridge if stale.

    Returns:
        HueConfiguration document with cached or fresh data
    """
    try:
      # Get instance
      if not self._instance:
        self._instance = await self._get_hue_instance()

      if not self._instance:
        raise Exception("Failed to connect to Hue bridge")

      config_doc = await HueConfiguration.find_one()

      if config_doc:
        # Check if configuration is less than a week old
        age = datetime.now().date() - config_doc.lastUpdated
        if age < timedelta(weeks=1):
          logger.debug(f"Using cached Hue configuration ({age.days} days old)")
          return config_doc
        else:
          logger.debug(f"Cached configuration is stale ({age.days} days old), syncing")
          return await self._sync_hue_configuration(self._instance)
      else:
        logger.debug("No cached configuration found, syncing from bridge")
        return await self._sync_hue_configuration(self._instance)

    except Exception as error:
      logger.error(f"Error getting Hue configuration: {error}")
      raise

  def get_lights_formatted(self, config: HueConfiguration) -> str:
    """Get formatted list of lights from configuration.

    Args:
        config: HueConfiguration document

    Returns:
        Formatted string of lights with IDs and names for prompt
    """
    logger.debug("Formatting lights list from configuration")

    lights_list = ", ".join([f'{light.id}:{light.name}' for light in config.lights])
    return lights_list

  def get_groups_formatted(self, config: HueConfiguration) -> str:
    """Get formatted list of light groups from configuration.

    Args:
        config: HueConfiguration document

    Returns:
        Formatted string of groups with IDs and names for prompt
    """
    logger.debug("Formatting groups list from configuration")

    groups_list = ", ".join([f'{group.id}:{group.name}' for group in config.groups])
    return groups_list

  async def control_light(self, light_id: int, turn_on: bool) -> str:
    """Control a specific light.

    Args:
        light_id: ID of the light to control
        turn_on: True to turn on, False to turn off

    Returns:
        Confirmation message
    """
    if not self._instance:
      self._instance = await self._get_hue_instance()

    if not self._instance:
      raise Exception("Failed to connect to Hue bridge")

    light = self._instance.get_light(id_=light_id)
    light.on() if turn_on else light.off()
    return f"{light.name} turned {'on' if turn_on else 'off'}"

  async def control_group(self, group_id: int, turn_on: bool) -> str:
    """Control a light group.

    Args:
        group_id: ID of the group to control
        turn_on: True to turn on, False to turn off

    Returns:
        Confirmation message
    """
    if not self._instance:
      self._instance = await self._get_hue_instance()

    if not self._instance:
      raise Exception("Failed to connect to Hue bridge")

    group = self._instance.get_group(id_=group_id)
    group.on() if turn_on else group.off()
    return f"{group.name} lights turned {'on' if turn_on else 'off'}"

  async def control_all_lights(self, turn_on: bool) -> str:
    """Control all lights.

    Args:
        turn_on: True to turn on, False to turn off

    Returns:
        Confirmation message
    """
    if not self._instance:
      self._instance = await self._get_hue_instance()

    if not self._instance:
      raise Exception("Failed to connect to Hue bridge")

    self._instance.on() if turn_on else self._instance.off()
    return f"All lights turned {'on' if turn_on else 'off'}"
