"""Diagnostics disclose no keys, tokens, entity names, or command text."""

from homeassistant.components import conversation

from .const import CONF_PROVIDER, PROVIDER_TYPESAFE
from .grok_handoff import resolve_grok_handoff_agent_id


async def async_get_config_entry_diagnostics(hass, entry):
    agent_id = resolve_grok_handoff_agent_id(entry)
    return {
        "provider": entry.data.get(CONF_PROVIDER, PROVIDER_TYPESAFE),
        "model": "jev-latest",
        "fallback": "builtin" if agent_id == conversation.HOME_ASSISTANT_AGENT else "custom",
        "fallback_available": conversation.async_get_agent(hass, agent_id) is not None,
    }
