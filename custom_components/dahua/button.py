# button.py
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import DahuaBaseEntity
from .const import DOMAIN
from . import DahuaDataUpdateCoordinator
from .const import *

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: dict,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up custom button entities based on a config entry."""
    coordinator: DahuaDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = [
        TriggerLightButton(coordinator, entry),
        TriggerSirenButton(coordinator, entry)
    ]

    async_add_entities(entities)

class TriggerSirenButton(DahuaBaseEntity, ButtonEntity):
    """Defines a custom button."""

    async def async_press(self) -> None:
        """Press the button."""
        await self._coordinator.client.toggle_siren()
        
    @property
    def name(self):
        return self._coordinator.get_device_name() + " " + "Trigger Siren"

    @property
    def unique_id(self):
        return self._coordinator.get_serial_number() + "_trigger_siren"

    @property
    def icon(self):
        return SIREN_ICON
    
class TriggerLightButton(DahuaBaseEntity, ButtonEntity):
    """Defines a custom button."""

    async def async_press(self) -> None:
        """Press the button."""
        await self._coordinator.client.toggle_light()
        
    @property
    def name(self):
        return self._coordinator.get_device_name() + " " + "Trigger Light"

    @property
    def unique_id(self):
        return self._coordinator.get_serial_number() + "_trigger_light"

    @property
    def icon(self):
        return SECURITY_LIGHT_ICON