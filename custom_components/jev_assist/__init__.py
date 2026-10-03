"""Jev Assist: a classifier with an explicitly selected Assist fallback."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import (
    CONF_API_KEY,
    CONF_PROVIDER,
    CONF_TYPESAFE_API_KEY,
    DOMAIN,
    PROVIDER_TYPESAFE,
)
from .jev_client import TypeSafeJevClient

PLATFORMS = ("conversation",)


@dataclass
class JevAssistRuntime:
    """No persistent sockets, background auth tasks, or separate Grok tokens."""

    jev: TypeSafeJevClient
    entry: ConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the selected provider; preserve existing direct TypeSafe entries."""
    key = entry.data.get(CONF_API_KEY) or entry.data.get(CONF_TYPESAFE_API_KEY)
    if not key:
        raise ConfigEntryAuthFailed("Jev API key missing")
    provider = entry.data.get(CONF_PROVIDER, PROVIDER_TYPESAFE)
    runtime = JevAssistRuntime(jev=TypeSafeJevClient(key, provider=provider), entry=entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Remove the conversation entity and its runtime."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unloaded


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
