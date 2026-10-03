"""Real HA entity lifecycle, exposure, service results and conversation handoff."""

import json
from unittest.mock import AsyncMock

import httpx2
import pytest
from homeassistant.components import conversation
from homeassistant.components.homeassistant import exposed_entities
from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Context
from homeassistant.data_entry_flow import InvalidData
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component

from custom_components.jev_assist.const import DOMAIN
from tests.fakes import FakeJevClient, classification
from tests.test_provider import sdk_transport, system_one_reply


class SyntheticLight(LightEntity):
    _attr_should_poll = False
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_is_on = True
    _attr_brightness = 255

    def __init__(self, name, unique_id):
        self._attr_name = name
        self._attr_unique_id = unique_id
        self.calls = []

    async def async_turn_on(self, **kwargs):
        self.calls.append(("on", kwargs))
        self._attr_is_on = True
        self._attr_brightness = kwargs.get("brightness", self._attr_brightness)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        self.calls.append(("off", kwargs))
        self._attr_is_on = False
        self.async_write_ha_state()


async def install_light(hass, *, name="Living Lamp", area="Living room", exposed=True, available=True):
    assert await async_setup_component(hass, "light", {})
    entity = SyntheticLight(name, "synthetic-" + name)
    entity._attr_available = available
    await hass.data["light"].async_add_entities([entity])
    registry = ar.async_get(hass)
    room = registry.async_get_area_by_name(area) or registry.async_create(area)
    er.async_get(hass).async_update_entity(entity.entity_id, area_id=room.id)
    exposed_entities.async_expose_entity(hass, "conversation", entity.entity_id, exposed)
    return entity


async def install_jev(hass, monkeypatch, *, data=None):
    monkeypatch.setattr(
        "custom_components.jev_assist.config_flow.TypeSafeJevClient.async_validate",
        AsyncMock(),
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
        data=data or {"provider": "openrouter", "api_key": "synthetic-key"},
    )
    assert result["type"] == "create_entry", result
    entry = result["result"]
    await hass.async_block_till_done()
    assert entry.entry_id in hass.data[DOMAIN]
    entity_id = er.async_get(hass).async_get_entity_id("conversation", DOMAIN, entry.entry_id + "-conversation")
    assert entity_id
    return entry, entity_id


async def process(hass, agent_id, text="turn off the living room lights"):
    return await conversation.async_converse(
        hass,
        text=text,
        conversation_id=None,
        context=Context(),
        language="en",
        agent_id=agent_id,
    )


async def test_sdk_to_actual_agent_and_light_reload_unload_remove(hass, monkeypatch):
    living = await install_light(hass)
    other = await install_light(hass, name="Bedroom Lamp", area="Bedroom")
    entry, entity_id = await install_jev(hass, monkeypatch)
    requests = []

    def handler(request):
        requests.append(request)
        return system_one_reply(request)

    sdk_transport(monkeypatch, handler)
    result = await process(hass, entity_id)
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert result.response.speech["plain"]["speech"] == "OK"
    assert result.response.success_results[0].id == living.entity_id
    assert living.calls == [("off", {})]
    assert other.calls == []
    assert json.loads(requests[0].content)["state"]["areas"] == [
        "Bedroom",
        "Living room",
    ]
    assert str(requests[0].url) == "https://openrouter.ai/api/v1/systemone"
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert living.calls == [("off", {})]
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.entry_id not in hass.data[DOMAIN]
    assert conversation.async_get_agent(hass, entity_id) is None
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_remove(entry.entry_id)
    assert living.calls == [("off", {})]


async def test_hidden_unknown_unavailable_and_partial_results(hass, monkeypatch):
    living = await install_light(hass)
    unavailable = await install_light(hass, name="Living Counter", available=False)
    hidden = await install_light(hass, name="Living Private", exposed=False)
    entry, entity_id = await install_jev(hass, monkeypatch)
    runtime = hass.data[DOMAIN][entry.entry_id]
    runtime.jev = FakeJevClient(classification(target_area="Living room"))
    result = await process(hass, entity_id)
    assert living.calls == [("off", {})]
    assert unavailable.calls == hidden.calls == []
    assert [target.id for target in result.response.failed_results] == [unavailable.entity_id]
    assert "unavailable" in result.response.speech["plain"]["speech"]
    exposed_entities.async_expose_entity(hass, "conversation", living.entity_id, False)
    result = await process(hass, entity_id)
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert "unavailable" in result.response.speech["plain"]["speech"]
    runtime.jev = FakeJevClient(classification(target_area="Missing room"))
    result = await process(hass, entity_id, "turn off missing room lights")
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert len(living.calls) == 1


async def test_exposure_change_while_classifying_fails_closed(hass, monkeypatch):
    living = await install_light(hass)
    entry, entity_id = await install_jev(hass, monkeypatch)

    class RacingClient:
        async def classify(self, *args, **kwargs):
            exposed_entities.async_expose_entity(hass, "conversation", living.entity_id, False)
            return classification(target_area="Living room")

    hass.data[DOMAIN][entry.entry_id].jev = RacingClient()
    result = await process(hass, entity_id)
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert living.calls == []


@pytest.mark.parametrize("percent,expected", [(0, "off"), (50, "on")])
async def test_numeric_brightness_and_zero_percent_real_light(hass, monkeypatch, percent, expected):
    living = await install_light(hass)
    entry, entity_id = await install_jev(hass, monkeypatch)
    hass.data[DOMAIN][entry.entry_id].jev = FakeJevClient(
        classification(target_area="Living room", action="set_brightness")
    )
    result = await process(hass, entity_id, f"set living lamp brightness to {percent} percent")
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert hass.states.get(living.entity_id).state == expected
    assert len(living.calls) == 1
    if percent:
        assert living.calls[0][1]["brightness"] == 128


async def test_lost_confirmation_never_hands_off_or_retries(hass, monkeypatch):
    living = await install_light(hass)
    entry, entity_id = await install_jev(hass, monkeypatch)
    hass.data[DOMAIN][entry.entry_id].jev = FakeJevClient(classification(target_area="Living room"))

    async def no_confirmation(**kwargs):
        living.calls.append(("off", kwargs))

    monkeypatch.setattr(living, "async_turn_off", no_confirmation)
    handed = AsyncMock()
    monkeypatch.setattr(
        "custom_components.jev_assist.conversation.async_try_handoff_to_conversation_agent",
        handed,
    )
    result = await process(hass, entity_id)
    assert result.response.error_code == intent.IntentResponseErrorCode.FAILED_TO_HANDLE
    assert "couldn't confirm" in result.response.speech["plain"]["speech"]
    assert living.calls == [("off", {})]
    handed.assert_not_awaited()


async def test_handoff_uses_actual_selected_agent_and_rejects_self(hass, monkeypatch):
    living = await install_light(hass)
    entry, entity_id = await install_jev(hass, monkeypatch)
    hass.data[DOMAIN][entry.entry_id].jev = FakeJevClient(classification(category="conversation"))
    # Native HA handles a sentence whose Jev classification requests handoff.
    result = await process(hass, entity_id)
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    await hass.async_block_till_done()
    assert living.calls == [("off", {})]
    options = await hass.config_entries.options.async_init(entry.entry_id)
    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(options["flow_id"], {"grok_handoff_agent_id": entity_id})
    hass.config_entries.options.async_abort(options["flow_id"])
    # An agent removal or rename cannot silently substitute a different agent.
    hass.config_entries.async_update_entry(entry, options={"grok_handoff_agent_id": "conversation.missing_grok"})
    await hass.async_block_till_done()
    hass.data[DOMAIN][entry.entry_id].jev = FakeJevClient(classification(category="conversation"))
    result = await process(hass, entity_id)
    assert result.response.error_code == intent.IntentResponseErrorCode.FAILED_TO_HANDLE
    assert living.calls == [("off", {})]


@pytest.mark.parametrize("source", ["reconfigure", "reauth"])
async def test_config_reconfigure_and_reauth_preserve_fallback(hass, monkeypatch, source):
    entry, entity_id = await install_jev(hass, monkeypatch)
    previous = entry.data["grok_handoff_agent_id"]
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": source, "entry_id": entry.entry_id},
        data=entry.data if source == "reauth" else None,
    )
    updated = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"provider": "typesafe", "api_key": "synthetic-new"}
    )
    assert updated["type"] == "abort"
    await hass.async_block_till_done()
    assert entry.data["provider"] == "typesafe"
    assert entry.data["grok_handoff_agent_id"] == previous
    assert conversation.async_get_agent(hass, entity_id)


async def test_upstream_entry_keeps_typesafe_without_duplicate_grok_auth(hass):
    entry = ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="Jev Assist",
        source="user",
        unique_id="synthetic-legacy",
        data={
            "typesafe_api_key": "synthetic-legacy",
            "grok_auth_method": "oauth",
            "access_token": "synthetic-expired-unused",
            "expires_at": 1,
        },
        options={},
        discovery_keys={},
        subentries_data=None,
    )
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    assert hass.data[DOMAIN][entry.entry_id].jev._base_url == "https://api.typesafe.ai"


@pytest.mark.parametrize(
    "status,error",
    [(401, "invalid_auth"), (402, "provider_error"), (429, "rate_limited")],
)
async def test_key_validation_errors_do_not_publish_secrets(hass, monkeypatch, caplog, status, error):
    def handler(request):
        return httpx2.Response(status, json={"error": {"message": "synthetic-sensitive-key"}})

    sdk_transport(monkeypatch, handler)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
        data={"provider": "openrouter", "api_key": "synthetic-sensitive-key"},
    )
    assert result["errors"] == {"base": error}
    assert "synthetic-sensitive-key" not in caplog.text
    hass.config_entries.flow.async_abort(result["flow_id"])
