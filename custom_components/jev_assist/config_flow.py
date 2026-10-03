"""OpenRouter or direct TypeSafe setup; Grok signs in in its own integration."""

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import conversation
from homeassistant.core import callback
from homeassistant.helpers import selector
from typesafe_sdk import (
    TypeSafeAPIConnectionError,
    TypeSafeAPIError,
    TypeSafeAuthenticationError,
    TypeSafeError,
    TypeSafePermissionDeniedError,
    TypeSafeRateLimitError,
)

from .const import (
    CONF_API_KEY,
    CONF_GROK_HANDOFF_AGENT_ID,
    CONF_PROVIDER,
    DEFAULT_NAME,
    DOMAIN,
    GROK_HANDOFF_AGENT_ID,
    PROVIDER_OPENROUTER,
    PROVIDER_TYPESAFE,
    PROVIDER_URLS,
)
from .grok_handoff import resolve_grok_handoff_agent_id
from .jev_client import TypeSafeJevClient


def agent_choices(hass, entry=None):
    """List loaded agents, excluding Jev entries to prevent recursive handoff."""
    from homeassistant.helpers import entity_registry as er

    choices = [{"value": conversation.HOME_ASSISTANT_AGENT, "label": "Home Assistant"}]
    for state in hass.states.async_all("conversation"):
        agent = conversation.async_get_agent_info(hass, state.entity_id)
        registered = er.async_get(hass).async_get(state.entity_id)
        if registered and registered.platform == DOMAIN:
            continue
        if (
            agent
            and agent.id != conversation.HOME_ASSISTANT_AGENT
            and not state.entity_id.startswith("conversation.jev_assist")
        ):
            choices.append({"value": agent.id, "label": agent.name})
    return choices


def provider_selector():
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=list(PROVIDER_URLS),
            translation_key="provider",
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


class JevAssistConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Validate the classifier key without sending names, areas, or utterances."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return JevAssistOptionsFlow()

    async def async_step_user(self, user_input=None):
        return await self._configure("user", user_input)

    async def async_step_reconfigure(self, user_input=None):
        return await self._configure("reconfigure", user_input)

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        return await self._configure("reauth_confirm", user_input)

    async def _configure(self, step: str, user_input: dict[str, Any] | None):
        entry = (
            self._get_reauth_entry()
            if step == "reauth_confirm"
            else self._get_reconfigure_entry()
            if step == "reconfigure"
            else None
        )
        default_provider = entry.data.get(CONF_PROVIDER, PROVIDER_TYPESAFE) if entry else PROVIDER_OPENROUTER
        errors = {}
        if user_input is not None:
            key = str(user_input[CONF_API_KEY]).strip()
            provider = user_input.get(CONF_PROVIDER, default_provider)
            if not key or not key.isascii() or any(ord(ch) < 33 or ord(ch) > 126 for ch in key):
                errors[CONF_API_KEY] = "invalid_api_key"
            elif provider not in PROVIDER_URLS:
                errors["base"] = "invalid_provider"
            else:
                try:
                    await TypeSafeJevClient(key, provider=provider).async_validate()
                except TypeSafeAuthenticationError, TypeSafePermissionDeniedError:
                    errors["base"] = "invalid_auth"
                except TypeSafeRateLimitError:
                    errors["base"] = "rate_limited"
                except TypeSafeAPIConnectionError, TimeoutError:
                    errors["base"] = "cannot_connect"
                except TypeSafeAPIError, TypeSafeError:
                    errors["base"] = "provider_error"
                else:
                    data = {CONF_PROVIDER: provider, CONF_API_KEY: key}
                    if entry:
                        return self.async_update_reload_and_abort(entry, data_updates=data)
                    await self.async_set_unique_id(DOMAIN)
                    self._abort_if_unique_id_configured()
                    choices = agent_choices(self.hass)
                    fallback = (
                        GROK_HANDOFF_AGENT_ID
                        if any(item["value"] == GROK_HANDOFF_AGENT_ID for item in choices)
                        else conversation.HOME_ASSISTANT_AGENT
                    )
                    return self.async_create_entry(
                        title=DEFAULT_NAME,
                        data={**data, CONF_GROK_HANDOFF_AGENT_ID: fallback},
                    )
        return self.async_show_form(
            step_id=step,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PROVIDER, default=default_provider): provider_selector(),
                    vol.Required(CONF_API_KEY): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
        )


class JevAssistOptionsFlow(config_entries.OptionsFlow):
    """Choose the agent that actually owns Grok authentication and chat tools."""

    async def async_step_init(self, user_input=None):
        errors = {}
        choices = agent_choices(self.hass, self.config_entry)
        allowed = {choice["value"] for choice in choices}
        if user_input is not None:
            if user_input[CONF_GROK_HANDOFF_AGENT_ID] not in allowed:
                errors["base"] = "invalid_agent"
            else:
                return self.async_create_entry(title="", data=user_input)
        current = resolve_grok_handoff_agent_id(self.config_entry)
        if current not in allowed:
            current = conversation.HOME_ASSISTANT_AGENT
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_GROK_HANDOFF_AGENT_ID, default=current): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=choices, mode=selector.SelectSelectorMode.DROPDOWN)
                    ),
                }
            ),
            errors=errors,
        )
