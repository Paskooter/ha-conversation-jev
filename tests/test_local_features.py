"""New local behavior through real HA registries, entities and services."""

from unittest.mock import AsyncMock

import pytest
from homeassistant.components import conversation
from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
from homeassistant.components.cover import CoverDeviceClass, CoverEntity, CoverEntityFeature
from homeassistant.components.homeassistant import exposed_entities
from homeassistant.components.light import ColorMode
from homeassistant.core import Context
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component

from custom_components.jev_assist.const import DOMAIN
from custom_components.jev_assist.diagnostics import async_get_config_entry_diagnostics
from custom_components.jev_assist.jev_router import ExposedEntity, route
from custom_components.jev_assist.light_map import light_service_call, parse_brightness_pct, parse_color_rgb
from tests.fakes import FakeJevClient, classification
from tests.test_homeassistant import SyntheticLight, install_jev, install_light


async def converse(hass, agent_id, text, *, device_id=None, conversation_id=None, context=None):
    return await conversation.async_converse(
        hass,
        text=text,
        conversation_id=conversation_id,
        context=context or Context(),
        language="en",
        agent_id=agent_id,
        device_id=device_id,
    )


def speech(result):
    return result.response.speech["plain"]["speech"]


async def robot_device(hass, entry, area, name="Synthetic Robot"):
    room = ar.async_get(hass).async_get_area_by_name(area) or ar.async_get(hass).async_create(area)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("synthetic_robot", name)},
        name=name,
    )
    return dr.async_get(hass).async_update_device(device.id, area_id=room.id)


class SyntheticColorLight(SyntheticLight):
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_color_mode = ColorMode.RGB
    _attr_rgb_color = (255, 255, 255)

    async def async_turn_on(self, **kwargs):
        self._attr_rgb_color = tuple(kwargs.get("rgb_color", self._attr_rgb_color))
        await super().async_turn_on(**kwargs)


class SyntheticOnOffLight(SyntheticLight):
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_color_mode = ColorMode.ONOFF
    _attr_is_on = False
    _attr_brightness = None


class SyntheticClimate(ClimateEntity):
    _attr_should_poll = False
    _attr_name = "Study Thermostat"
    _attr_unique_id = "synthetic-study-thermostat"
    _attr_hvac_mode = HVACMode.HEAT
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF]
    _attr_temperature_unit = "°C"
    _attr_current_temperature = 21.5
    _attr_target_temperature = 20
    _attr_current_humidity = 45
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self):
        self.calls = []

    async def async_set_temperature(self, **kwargs):
        self.calls.append(("temperature", kwargs["temperature"]))
        self._attr_target_temperature = kwargs["temperature"]
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode):
        self.calls.append(("mode", hvac_mode))
        self._attr_hvac_mode = HVACMode(hvac_mode)
        self.async_write_ha_state()

    async def async_turn_on(self):
        self.calls.append(("on",))
        self._attr_hvac_mode = HVACMode.HEAT
        self.async_write_ha_state()

    async def async_turn_off(self):
        self.calls.append(("off",))
        self._attr_hvac_mode = HVACMode.OFF
        self.async_write_ha_state()


class SyntheticHSLight(SyntheticLight):
    _attr_supported_color_modes = {ColorMode.HS}
    _attr_color_mode = ColorMode.HS
    _attr_hs_color = (0, 0)

    async def async_turn_on(self, **kwargs):
        self._attr_hs_color = kwargs.get("hs_color", self._attr_hs_color)
        await super().async_turn_on(**kwargs)


class SyntheticCover(CoverEntity):
    _attr_should_poll = False
    _attr_name = "Study Blind"
    _attr_unique_id = "synthetic-study-blind"
    _attr_is_closed = False
    _attr_current_cover_position = 30
    _attr_current_cover_tilt_position = 40
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.SET_TILT_POSITION
    )

    def __init__(self):
        self.calls = []

    async def async_open_cover(self, **kwargs):
        self.calls.append(("open",))
        self._attr_is_closed = False
        self._attr_current_cover_position = 100
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs):
        self.calls.append(("close",))
        self._attr_is_closed = True
        self._attr_current_cover_position = 0
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs):
        self.calls.append(("stop",))

    async def async_set_cover_position(self, **kwargs):
        self.calls.append(("position", kwargs["position"]))
        self._attr_current_cover_position = kwargs["position"]
        self.async_write_ha_state()

    async def async_set_cover_tilt_position(self, **kwargs):
        self.calls.append(("tilt", kwargs["tilt_position"]))
        self._attr_current_cover_tilt_position = kwargs["tilt_position"]
        self.async_write_ha_state()


@pytest.mark.parametrize(
    "text,value",
    [
        ("brightness to fifty percent", 50),
        ("brightness twenty-five percent", 25),
        ("brightness ninety nine", 99),
        ("dim to one hundred percent", 100),
        ("Helligkeit auf fünfzig Prozent", 50),
        ("Helligkeit einundzwanzig Prozent", 21),
        ("Helligkeit null", 0),
        ("brightness zero percent", 0),
    ],
)
def test_spelled_absolute_percentages(text, value):
    assert parse_brightness_pct(text) == value
    assert light_service_call("set_brightness", ["light.synthetic"], text)[2]["brightness_pct"] == value


@pytest.mark.parametrize(
    "text",
    [
        "brightness to one hundred fifty percent",
        "brightness to one hundred and fifty percent",
        "brightness twenty and fifty percent",
        "dim the light by fifty percent",
        "dimme die Lampe um zwanzig Prozent",
        "make the light fifty percent brighter",
        "brightness minus five percent",
        "brightness -5%",
        "brightness - 50 percent",
        "brightness −50 percent",
        "brightness −fifty percent",
        "brightness 150%",
        "brightness 1050%",
        "brightness 50.5%",
        "brightness fifty five hundred percent",
        "twenty percent or fifty percent",
        "brightness to a bit brighter",
        "brightness half",
    ],
)
def test_ambiguous_relative_negative_and_out_of_range_values(text):
    assert parse_brightness_pct(text) is None


@pytest.mark.parametrize(
    "text,rgb",
    [
        ("set Blue Lamp to red", (255, 0, 0)),
        ("set Living Lamp to blue", (0, 0, 255)),
        ("set light color to purple please", (128, 0, 128)),
        ("Licht auf grün", (0, 128, 0)),
    ],
)
def test_bounded_named_color_values(text, rgb):
    assert parse_color_rgb(text) == rgb


@pytest.mark.parametrize(
    "text",
    [
        "light to dark red",
        "light to blue and red",
        "light to warm white",
        "light to chartreuse",
        "light to red or blue",
    ],
)
def test_modified_or_ambiguous_colors_need_fallback(text):
    assert parse_color_rgb(text) is None


@pytest.mark.parametrize(
    "domain,text,target",
    [
        ("scene", "activate Reading Time scene", "scene.reading_time"),
        ("script", "run Evening Prep script", "script.evening_prep"),
    ],
)
async def test_exact_routine_requires_all_existing_confidence_gates(domain, text, target):
    entity = ExposedEntity(target, domain, "Reading Time" if domain == "scene" else "Evening Prep")
    for field in ("category_c", "domain_c", "action_c", "target_c"):
        client = FakeJevClient(classification(domain=domain, action="activate", target_area="none", **{field: 0.79}))
        assert (await route(text, [entity], language="en", client=client)).kind == "grok"
    client = FakeJevClient(classification(domain=domain, action="activate", target_area="none"))
    result = await route(text, [entity], language="en", client=client)
    assert result.kind == "fast_service"
    assert result.service_data == {"entity_id": target}


@pytest.mark.parametrize(
    "text", ["activate all scenes", "activate Reading scene", "activate Reading Time scene and turn off lights"]
)
async def test_routine_never_expands_or_executes_compound_tail(text):
    entities = [
        ExposedEntity("scene.reading_time", "scene", "Reading Time"),
        ExposedEntity("scene.reading_break", "scene", "Reading Break"),
    ]
    client = FakeJevClient(classification(domain="scene", action="activate", target_area="none"))
    assert (await route(text, entities, language="en", client=client)).kind == "reject"


async def test_actual_color_service_and_spelled_brightness(hass, monkeypatch):
    assert await async_setup_component(hass, "light", {})
    light = SyntheticColorLight("Color Lamp", "synthetic-color-lamp")
    await hass.data["light"].async_add_entities([light])
    exposed_entities.async_expose_entity(hass, "conversation", light.entity_id, True)
    entry, agent_id = await install_jev(hass, monkeypatch)
    runtime = hass.data[DOMAIN][entry.entry_id]
    runtime.jev = FakeJevClient(classification(action="set_color", target_area="none"))
    result = await converse(hass, agent_id, "set Color Lamp to red")
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert hass.states.get(light.entity_id).attributes["rgb_color"] == (255, 0, 0)
    assert light.calls == [("on", {"rgb_color": (255, 0, 0)})]
    runtime.jev = FakeJevClient(classification(action="set_brightness", target_area="none"))
    result = await converse(hass, agent_id, "set Color Lamp brightness to fifty percent")
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert hass.states.get(light.entity_id).attributes["brightness"] == 128
    assert len(light.calls) == 2


async def test_unsupported_color_and_lost_color_confirmation_do_not_handoff(hass, monkeypatch):
    plain = await install_light(hass)
    entry, agent_id = await install_jev(hass, monkeypatch)
    runtime = hass.data[DOMAIN][entry.entry_id]
    runtime.jev = FakeJevClient(classification(action="set_color", target_area="none"))
    handoff = AsyncMock()
    monkeypatch.setattr("custom_components.jev_assist.conversation.async_try_handoff_to_conversation_agent", handoff)
    result = await converse(hass, agent_id, "set Living Lamp to blue")
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert "support color" in speech(result)
    assert plain.calls == []
    colored = SyntheticColorLight("Color Lamp", "synthetic-color-lamp")
    await hass.data["light"].async_add_entities([colored])
    exposed_entities.async_expose_entity(hass, "conversation", colored.entity_id, True)

    async def unchanged_color(**kwargs):
        colored.calls.append(("on", kwargs))

    monkeypatch.setattr(colored, "async_turn_on", unchanged_color)
    result = await converse(hass, agent_id, "set Color Lamp to blue")
    assert result.response.error_code == intent.IntentResponseErrorCode.FAILED_TO_HANDLE
    assert len(colored.calls) == 1
    handoff.assert_not_awaited()


@pytest.mark.parametrize("percentage", ["fifty", "zero"])
async def test_unsupported_brightness_never_turns_on_or_off_onoff_light(hass, monkeypatch, percentage):
    assert await async_setup_component(hass, "light", {})
    light = SyntheticOnOffLight("Plain Lamp", "synthetic-plain-lamp")
    await hass.data["light"].async_add_entities([light])
    exposed_entities.async_expose_entity(hass, "conversation", light.entity_id, True)
    entry, agent_id = await install_jev(hass, monkeypatch)
    hass.data[DOMAIN][entry.entry_id].jev = FakeJevClient(classification(action="set_brightness", target_area="none"))
    handoff = AsyncMock()
    monkeypatch.setattr("custom_components.jev_assist.conversation.async_try_handoff_to_conversation_agent", handoff)
    result = await converse(hass, agent_id, f"set Plain Lamp brightness to {percentage} percent")
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert "support brightness" in speech(result)
    assert light.calls == []
    assert hass.states.get(light.entity_id).state == "off"
    handoff.assert_not_awaited()


@pytest.mark.parametrize("observed,percentage", [(float("nan"), "fifty"), (True, "one"), (256, "one hundred")])
async def test_malformed_brightness_observation_never_confirms_or_retries(hass, monkeypatch, observed, percentage):
    light = await install_light(hass)
    entry, agent_id = await install_jev(hass, monkeypatch)
    hass.data[DOMAIN][entry.entry_id].jev = FakeJevClient(classification(action="set_brightness", target_area="none"))
    handoff = AsyncMock()
    monkeypatch.setattr("custom_components.jev_assist.conversation.async_try_handoff_to_conversation_agent", handoff)

    async def malformed_brightness(**kwargs):
        light.calls.append(("on", kwargs))
        light._attr_is_on = True
        light._attr_brightness = observed
        light.async_write_ha_state()

    monkeypatch.setattr(light, "async_turn_on", malformed_brightness)
    result = await converse(hass, agent_id, f"set Living Lamp brightness to {percentage} percent")
    assert result.response.error_code == intent.IntentResponseErrorCode.FAILED_TO_HANDLE
    assert "confirm" in speech(result)
    assert len(light.calls) == 1
    handoff.assert_not_awaited()


@pytest.mark.parametrize(
    "observed,color", [((720, 100), "red"), ((True, 100), "red"), ((0, True), "white"), ((0, 101), "red")]
)
async def test_malformed_hs_observation_never_confirms_or_retries(hass, monkeypatch, observed, color):
    assert await async_setup_component(hass, "light", {})
    light = SyntheticHSLight("Color Lamp", "synthetic-color-lamp")
    await hass.data["light"].async_add_entities([light])
    exposed_entities.async_expose_entity(hass, "conversation", light.entity_id, True)
    entry, agent_id = await install_jev(hass, monkeypatch)
    hass.data[DOMAIN][entry.entry_id].jev = FakeJevClient(classification(action="set_color", target_area="none"))
    handoff = AsyncMock()
    monkeypatch.setattr("custom_components.jev_assist.conversation.async_try_handoff_to_conversation_agent", handoff)

    async def malformed_color(**kwargs):
        light.calls.append(("on", kwargs))
        light._attr_is_on = True
        light._attr_hs_color = observed
        # LightEntity rounds HS channels, so publish the raw malformed observation
        # directly through the real state machine.
        attributes = dict(hass.states.get(light.entity_id).attributes)
        attributes["hs_color"] = observed
        hass.states.async_set(light.entity_id, "on", attributes)

    monkeypatch.setattr(light, "async_turn_on", malformed_color)
    result = await converse(hass, agent_id, f"set Color Lamp to {color}")
    assert result.response.error_code == intent.IntentResponseErrorCode.FAILED_TO_HANDLE
    assert "confirm" in speech(result)
    assert len(light.calls) == 1
    handoff.assert_not_awaited()


@pytest.mark.parametrize(
    "domain,text", [("scene", "activate Reading Time scene"), ("script", "run Evening Prep script")]
)
async def test_actual_scene_script_started_once_and_exposure_rechecked(hass, monkeypatch, domain, text):
    light = await install_light(hass)
    if domain == "scene":
        config = {"scene": [{"name": "Reading Time", "entities": {light.entity_id: "off"}}]}
        target = "scene.reading_time"
    else:
        config = {
            "script": {
                "evening_prep": {
                    "alias": "Evening Prep",
                    "sequence": [{"action": "light.turn_off", "target": {"entity_id": light.entity_id}}],
                }
            }
        }
        target = "script.evening_prep"
    assert await async_setup_component(hass, domain, config)
    await hass.async_block_till_done()
    assert hass.states.get(target)
    exposed_entities.async_expose_entity(hass, "conversation", target, True)
    entry, agent_id = await install_jev(hass, monkeypatch)
    runtime = hass.data[DOMAIN][entry.entry_id]
    runtime.jev = FakeJevClient(classification(domain=domain, action="activate", target_area="none"))
    result = await converse(hass, agent_id, text)
    await hass.async_block_till_done()
    assert speech(result).startswith("Started ")
    assert [target.id for target in result.response.success_results] == [target]
    assert light.calls == [("off", {})]

    class RacingClient:
        async def classify(self, *args, **kwargs):
            exposed_entities.async_expose_entity(hass, "conversation", target, False)
            return classification(domain=domain, action="activate", target_area="none")

    runtime.jev = RacingClient()
    result = await converse(hass, agent_id, text)
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert light.calls == [("off", {})]


async def test_queries_read_actual_states_without_classifier_services_or_handoff(hass, monkeypatch):
    on = await install_light(hass)
    unknown = await install_light(hass, name="Living Accent")
    unavailable = await install_light(hass, name="Living Counter", available=False)
    hidden = await install_light(hass, name="Living Private", exposed=False)
    hass.states.async_set(unknown.entity_id, "unknown", {"friendly_name": "Living Accent"})
    entry, agent_id = await install_jev(hass, monkeypatch)
    classifier = AsyncMock(side_effect=AssertionError("question must remain local"))
    hass.data[DOMAIN][entry.entry_id].jev = type("QueryOnly", (), {"classify": classifier})()
    handoff = AsyncMock(side_effect=AssertionError("question must not invoke tools"))
    monkeypatch.setattr("custom_components.jev_assist.conversation.async_try_handoff_to_conversation_agent", handoff)
    result = await converse(hass, agent_id, "are living room lights on?")
    assert result.response.response_type == intent.IntentResponseType.QUERY_ANSWER
    assert "Living Lamp is on" in speech(result)
    assert "don't know" in speech(result)
    assert "unavailable" in speech(result)
    assert "Private" not in speech(result)
    assert [target.id for target in result.response.success_results] == [on.entity_id]
    assert {target.id for target in result.response.failed_results} == {unknown.entity_id, unavailable.entity_id}
    for text in ("is Living Private on?", "are missing room lights on?", "are all lights on?"):
        assert (
            await converse(hass, agent_id, text)
        ).response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    result = await converse(hass, agent_id, "what is the Living Lamp brightness?")
    assert "100 percent" in speech(result)
    assert on.calls == unknown.calls == unavailable.calls == hidden.calls == []
    classifier.assert_not_awaited()
    handoff.assert_not_awaited()


async def test_temperature_humidity_and_binary_sensor_open_queries(hass, monkeypatch):
    room = ar.async_get(hass).async_create("Kitchen")
    registry = er.async_get(hass)
    for domain, object_id, value, attrs in (
        ("sensor", "kitchen_temperature", "21.5", {"device_class": "temperature", "unit_of_measurement": "°C"}),
        ("sensor", "kitchen_humidity", "48", {"device_class": "humidity", "unit_of_measurement": "%"}),
        ("binary_sensor", "kitchen_window", "on", {"device_class": "window"}),
    ):
        entity = registry.async_get_or_create(domain, "synthetic", object_id, suggested_object_id=object_id)
        registry.async_update_entity(entity.entity_id, area_id=room.id)
        hass.states.async_set(entity.entity_id, value, {"friendly_name": object_id.replace("_", " ").title(), **attrs})
        exposed_entities.async_expose_entity(hass, "conversation", entity.entity_id, True)
    entry, agent_id = await install_jev(hass, monkeypatch)
    hass.data[DOMAIN][entry.entry_id].jev = None
    for text, expected in (
        ("what is the kitchen temperature?", "21.5 °C"),
        ("what is the kitchen humidity?", "48 %"),
        ("is Kitchen Window open?", "is open"),
    ):
        result = await converse(hass, agent_id, text)
        assert result.response.response_type == intent.IntentResponseType.QUERY_ANSWER
        assert expected in speech(result)


async def test_room_context_followup_device_isolation_and_expiry(hass, monkeypatch):
    living = await install_light(hass)
    bedroom = await install_light(hass, name="Bedroom Lamp", area="Bedroom")
    entry, agent_id = await install_jev(hass, monkeypatch)
    alpha = await robot_device(hass, entry, "Living room", "Alpha Robot")
    beta = await robot_device(hass, entry, "Bedroom", "Beta Robot")
    runtime = hass.data[DOMAIN][entry.entry_id]
    runtime.jev = FakeJevClient(classification(action="turn_off", target_area="none"))
    monkeypatch.setattr("custom_components.jev_assist.conversation.monotonic", lambda: 1000)
    initial = await converse(hass, agent_id, "turn off the lights", device_id=alpha.id)
    assert initial.conversation_id
    assert living.calls == [("off", {})]
    assert bedroom.calls == []
    runtime.jev = FakeJevClient(classification(action="set_brightness", target_area="none"))
    followup = await converse(
        hass, agent_id, "set it to fifty percent", device_id=alpha.id, conversation_id=initial.conversation_id
    )
    assert followup.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert living.calls[-1] == ("on", {"brightness": 128})
    before = len(living.calls)
    other_robot = await converse(
        hass, agent_id, "set it to fifty percent", device_id=beta.id, conversation_id=initial.conversation_id
    )
    assert other_robot.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert bedroom.calls == []
    runtime.jev = None
    question = await converse(hass, agent_id, "is it on?", device_id=alpha.id, conversation_id=initial.conversation_id)
    assert "is on" in speech(question)
    monkeypatch.setattr("custom_components.jev_assist.conversation.monotonic", lambda: 1031)
    expired = await converse(hass, agent_id, "is it on?", device_id=alpha.id, conversation_id=initial.conversation_id)
    assert expired.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert len(living.calls) == before


async def test_room_context_cannot_expand_whole_home_or_hidden_named_target(hass, monkeypatch):
    living = await install_light(hass)
    bedroom = await install_light(hass, name="Bedroom Lamp", area="Bedroom")
    entry, agent_id = await install_jev(hass, monkeypatch)
    device = await robot_device(hass, entry, "Living room")
    runtime = hass.data[DOMAIN][entry.entry_id]
    runtime.jev = FakeJevClient(classification(target_area="Living room", scope="whole_home"))
    handed = AsyncMock(return_value=(None, "No broad target."))
    monkeypatch.setattr("custom_components.jev_assist.conversation.async_try_handoff_to_conversation_agent", handed)
    result = await converse(hass, agent_id, "turn off all lights", device_id=device.id)
    assert result.response.error_code
    assert living.calls == bedroom.calls == []
    runtime.jev = None
    for text in ("is Private Lamp on?", "are all lights on?", "what is the temperature in Missing Room?"):
        result = await converse(hass, agent_id, text, device_id=device.id)
        assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS


async def test_followup_exposure_rechecked_and_reload_forgets_targets(hass, monkeypatch):
    light = await install_light(hass)
    entry, agent_id = await install_jev(hass, monkeypatch)
    device = await robot_device(hass, entry, "Living room")
    runtime = hass.data[DOMAIN][entry.entry_id]
    runtime.jev = FakeJevClient(classification(target_area="none"))
    result = await converse(hass, agent_id, "turn off Living Lamp", device_id=device.id)
    exposed_entities.async_expose_entity(hass, "conversation", light.entity_id, False)
    runtime.jev = FakeJevClient(classification(action="turn_on", target_area="none"))
    followup = await converse(hass, agent_id, "turn it on", device_id=device.id, conversation_id=result.conversation_id)
    assert followup.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert light.calls == [("off", {})]
    exposed_entities.async_expose_entity(hass, "conversation", light.entity_id, True)
    result = await converse(hass, agent_id, "turn on Living Lamp", device_id=device.id)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    hass.data[DOMAIN][entry.entry_id].jev = FakeJevClient(classification(target_area="none"))
    followup = await converse(
        hass, agent_id, "turn it off", device_id=device.id, conversation_id=result.conversation_id
    )
    assert followup.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert len(light.calls) == 2


@pytest.mark.parametrize(
    "domain,model,cases,queries",
    [
        (
            "climate",
            SyntheticClimate,
            [
                ("set_temperature", "set Study Thermostat to 23 degrees", ("temperature", 23)),
                ("set_hvac_mode", "set Study Thermostat mode to cool", ("mode", "cool")),
                ("turn_off", "turn off Study Thermostat", ("off",)),
                ("turn_on", "turn on Study Thermostat", ("on",)),
            ],
            [
                ("what is Study Thermostat temperature?", "21.5 °C"),
                ("what is Study Thermostat target temperature?", "23 °C"),
                ("what is Study Thermostat humidity?", "45 %"),
            ],
        ),
        (
            "cover",
            SyntheticCover,
            [
                ("open", "open Study Blind", ("open",)),
                ("close", "close Study Blind", ("close",)),
                ("stop", "stop Study Blind", ("stop",)),
                ("set_position", "set Study Blind position to 50 percent", ("position", 50)),
                ("set_tilt", "set Study Blind tilt to 25 percent", ("tilt", 25)),
            ],
            [("what is Study Blind position?", "50 percent"), ("what is Study Blind tilt?", "25 percent")],
        ),
    ],
)
async def test_existing_climate_cover_paths_and_queries_use_real_ha(hass, monkeypatch, domain, model, cases, queries):
    assert await async_setup_component(hass, domain, {})
    entity = model()
    await hass.data[domain].async_add_entities([entity])
    exposed_entities.async_expose_entity(hass, "conversation", entity.entity_id, True)
    entry, agent_id = await install_jev(hass, monkeypatch)
    runtime = hass.data[DOMAIN][entry.entry_id]
    for action, text, expected in cases:
        runtime.jev = FakeJevClient(classification(domain=domain, action=action, target_area="none"))
        result = await converse(hass, agent_id, text)
        assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
        assert entity.calls[-1] == expected
        assert [target.id for target in result.response.success_results] == [entity.entity_id]
    runtime.jev = None
    for text, expected in queries:
        result = await converse(hass, agent_id, text)
        assert result.response.response_type == intent.IntentResponseType.QUERY_ANSWER
        assert expected in speech(result)
    assert len(entity.calls) == len(cases)


async def test_full_name_wins_over_shared_words_and_unknown_qualifiers_fail_closed(hass, monkeypatch):
    study = await install_light(hass, name="Study Ceiling", area="Study")
    bedroom = await install_light(hass, name="Bedroom Ceiling", area="Bedroom")
    entry, agent_id = await install_jev(hass, monkeypatch)
    robot = await robot_device(hass, entry, "Study")
    runtime = hass.data[DOMAIN][entry.entry_id]
    runtime.jev = FakeJevClient(classification(action="turn_on", target_area="none"))
    result = await converse(hass, agent_id, "turn on the Study Ceiling", device_id=robot.id)
    assert [target.id for target in result.response.success_results] == [study.entity_id]
    assert study.calls == [("on", {})]
    assert bedroom.calls == []
    for text in ("turn on the Imaginary light", "turn on the Bedroom Imaginary light"):
        result = await converse(hass, agent_id, text, device_id=robot.id)
        assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    runtime.jev = None
    for text in ("is the Bedroom Imaginary light on?", "is the Imaginary light here on?"):
        result = await converse(hass, agent_id, text, device_id=robot.id)
        assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert study.calls == [("on", {})]
    assert bedroom.calls == []


async def test_sole_device_shortcut_does_not_ignore_unknown_explicit_name(hass, monkeypatch):
    light = await install_light(hass, name="Study Ceiling", area="Study")
    entry, agent_id = await install_jev(hass, monkeypatch)
    hass.data[DOMAIN][entry.entry_id].jev = FakeJevClient(classification(action="turn_on", target_area="none"))
    result = await converse(hass, agent_id, "turn on the Imaginary light")
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert light.calls == []


async def test_duplicate_alias_and_distinct_explicit_names_cannot_disappear(hass, monkeypatch):
    first = await install_light(hass, name="Desk Lamp", area="Study")
    second = await install_light(hass, name="Bedroom Floor Lamp", area="Bedroom")
    registry = er.async_get(hass)
    registry.async_update_entity(first.entity_id, aliases={"Focus Lamp"})
    registry.async_update_entity(second.entity_id, aliases={"Focus Lamp"})
    entry, agent_id = await install_jev(hass, monkeypatch)
    runtime = hass.data[DOMAIN][entry.entry_id]
    runtime.jev = FakeJevClient(classification(target_area="none"))
    for text in ("turn off Focus Lamp", "turn off Desk Lamp and Bedroom Floor Lamp"):
        result = await converse(hass, agent_id, text)
        assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    runtime.jev = None
    result = await converse(hass, agent_id, "is Focus Lamp on?")
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert first.calls == second.calls == []


async def test_device_area_uses_ha_8_compatible_fallback(hass, monkeypatch):
    light = await install_light(hass)
    entry, agent_id = await install_jev(hass, monkeypatch)
    robot = await robot_device(hass, entry, "Living room")
    monkeypatch.delattr(dr, "async_get_effective_area_id", raising=False)
    hass.data[DOMAIN][entry.entry_id].jev = FakeJevClient(classification(target_area="none"))
    result = await converse(hass, agent_id, "turn off the lights here", device_id=robot.id)
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert light.calls == [("off", {})]


async def test_diagnostics_report_only_aggregate_local_routes_and_reset_on_reload(hass, monkeypatch):
    light = await install_light(hass)
    entry, agent_id = await install_jev(hass, monkeypatch)
    hass.data[DOMAIN][entry.entry_id].jev = FakeJevClient(classification(target_area="none"))
    await converse(hass, agent_id, "turn off Living Lamp")
    await converse(hass, agent_id, "is Living Lamp on?")
    await converse(hass, agent_id, "is Missing Lamp on?")
    diagnostic = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostic["routes"] == {"fast_service": 1, "fast_query": 2, "grok": 0, "reject": 0}
    assert light.entity_id not in str(diagnostic)
    assert "Living Lamp" not in str(diagnostic)
    assert "synthetic-key" not in str(diagnostic)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert all(count == 0 for count in (await async_get_config_entry_diagnostics(hass, entry))["routes"].values())


async def test_multi_room_exact_entities_never_expand_to_other_devices(hass, monkeypatch):
    study_ceiling = await install_light(hass, name="Study Ceiling", area="Study")
    study_floor = await install_light(hass, name="Study Floor", area="Study")
    bedroom_ceiling = await install_light(hass, name="Bedroom Ceiling", area="Bedroom")
    bedroom_floor = await install_light(hass, name="Bedroom Floor", area="Bedroom")
    entry, agent_id = await install_jev(hass, monkeypatch)
    hass.data[DOMAIN][entry.entry_id].jev = FakeJevClient(
        classification(action="turn_on", target_area="none", is_compound=0.99)
    )
    result = await converse(hass, agent_id, "turn on the Study Ceiling and Bedroom Ceiling")
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert {target.id for target in result.response.success_results} == {
        study_ceiling.entity_id,
        bedroom_ceiling.entity_id,
    }
    assert study_ceiling.calls == bedroom_ceiling.calls == [("on", {})]
    assert study_floor.calls == bedroom_floor.calls == []


async def test_computed_alias_uses_actual_ha_alias_resolver(hass, monkeypatch):
    light = await install_light(hass)
    er.async_get(hass).async_update_entity(light.entity_id, aliases=[er.COMPUTED_NAME, "Focus Lamp"])
    entry, agent_id = await install_jev(hass, monkeypatch)
    hass.data[DOMAIN][entry.entry_id].jev = FakeJevClient(classification(target_area="none"))
    result = await converse(hass, agent_id, "turn off Focus Lamp")
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert light.calls == [("off", {})]


async def test_color_confirmation_accepts_ha_hs_conversion_without_changing_brightness(hass, monkeypatch):
    assert await async_setup_component(hass, "light", {})
    light = SyntheticHSLight("Hue Lamp", "synthetic-hue-lamp")
    await hass.data["light"].async_add_entities([light])
    exposed_entities.async_expose_entity(hass, "conversation", light.entity_id, True)
    entry, agent_id = await install_jev(hass, monkeypatch)
    hass.data[DOMAIN][entry.entry_id].jev = FakeJevClient(classification(action="set_color", target_area="none"))
    result = await converse(hass, agent_id, "set Hue Lamp to green")
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert light.calls == [("on", {"hs_color": (120, 100)})]
    state = hass.states.get(light.entity_id)
    assert state.attributes["rgb_color"] == (0, 255, 0)
    assert state.attributes["brightness"] == 255


@pytest.mark.parametrize("decimal", ["20.5", "20,5"])
async def test_climate_decimal_setpoints_preserved_with_exact_names(hass, monkeypatch, decimal):
    assert await async_setup_component(hass, "climate", {})
    climate = SyntheticClimate()
    await hass.data["climate"].async_add_entities([climate])
    exposed_entities.async_expose_entity(hass, "conversation", climate.entity_id, True)
    entry, agent_id = await install_jev(hass, monkeypatch)
    hass.data[DOMAIN][entry.entry_id].jev = FakeJevClient(
        classification(domain="climate", action="set_temperature", target_area="none")
    )
    result = await converse(hass, agent_id, f"set Study Thermostat to {decimal} degrees")
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert climate.calls == [("temperature", 20.5)]
    assert hass.states.get(climate.entity_id).attributes["temperature"] == 20.5


async def test_generic_query_device_classes_select_only_requested_room_sensors(hass, monkeypatch):
    room = ar.async_get(hass).async_create("Study")
    registry = er.async_get(hass)
    ids = {}
    for key, domain, device_class in (
        ("door", "binary_sensor", "door"),
        ("window", "binary_sensor", "window"),
        ("motion", "binary_sensor", "motion"),
        ("blind", "cover", CoverDeviceClass.BLIND),
        ("garage", "cover", CoverDeviceClass.GARAGE),
    ):
        object_id = "overhead" if key == "garage" else "study_" + key
        entity = registry.async_get_or_create(domain, "synthetic", object_id, suggested_object_id=object_id)
        registry.async_update_entity(entity.entity_id, area_id=room.id)
        hass.states.async_set(
            entity.entity_id,
            "on" if domain == "binary_sensor" else "open",
            {"friendly_name": "Overhead" if key == "garage" else "Study " + key.title(), "device_class": device_class},
        )
        exposed_entities.async_expose_entity(hass, "conversation", entity.entity_id, True)
        ids[key] = entity.entity_id
    entry, agent_id = await install_jev(hass, monkeypatch)
    hass.data[DOMAIN][entry.entry_id].jev = None
    for text, expected in (
        ("are Study doors open?", "door"),
        ("are Study windows open?", "window"),
        ("what is Study motion status?", "motion"),
        ("are Study blinds open?", "blind"),
        ("are Study garage doors open?", "garage"),
    ):
        result = await converse(hass, agent_id, text)
        assert result.response.response_type == intent.IntentResponseType.QUERY_ANSWER
        assert [target.id for target in result.response.success_results] == [ids[expected]]
        assert result.response.failed_results == []


async def test_partial_actions_and_queries_do_not_save_successful_subset_for_pronouns(hass, monkeypatch):
    light = await install_light(hass)
    unavailable = await install_light(hass, name="Living Counter", available=False)
    entry, agent_id = await install_jev(hass, monkeypatch)
    robot = await robot_device(hass, entry, "Living room")
    runtime = hass.data[DOMAIN][entry.entry_id]
    runtime.jev = FakeJevClient(classification(target_area="none"))
    initial = await converse(hass, agent_id, "turn off the lights", device_id=robot.id)
    assert initial.response.failed_results[0].id == unavailable.entity_id
    runtime.jev = FakeJevClient(classification(action="turn_on", target_area="none"))
    followup = await converse(
        hass, agent_id, "turn them on", device_id=robot.id, conversation_id=initial.conversation_id
    )
    assert followup.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    runtime.jev = None
    question = await converse(hass, agent_id, "are living room lights on?", device_id=robot.id)
    assert question.response.failed_results[0].id == unavailable.entity_id
    followup = await converse(hass, agent_id, "is it on?", device_id=robot.id, conversation_id=question.conversation_id)
    assert followup.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert light.calls == [("off", {})]
    assert unavailable.calls == []


@pytest.mark.parametrize(
    "name,action,text,expected",
    [
        ("Heating Thermostat", "set_hvac_mode", "set Heating Thermostat to cool", ("mode", "cool")),
        ("Thermostat 20", "set_temperature", "set Thermostat 20 to 21", ("temperature", 21)),
    ],
)
async def test_target_name_cannot_supply_climate_setting(hass, monkeypatch, name, action, text, expected):
    assert await async_setup_component(hass, "climate", {})
    climate = SyntheticClimate()
    climate._attr_name = name
    await hass.data["climate"].async_add_entities([climate])
    exposed_entities.async_expose_entity(hass, "conversation", climate.entity_id, True)
    entry, agent_id = await install_jev(hass, monkeypatch)
    hass.data[DOMAIN][entry.entry_id].jev = FakeJevClient(
        classification(domain="climate", action=action, target_area="none")
    )
    result = await converse(hass, agent_id, text)
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert climate.calls == [expected]


@pytest.mark.parametrize(
    "domain,model,action,text",
    [
        ("cover", SyntheticCover, "set_position", "set Study Blind to20.5percent"),
        ("cover", SyntheticCover, "set_position", "set Study Blind to 20.5 percent"),
        ("cover", SyntheticCover, "set_position", "set Study Blind to-50percent"),
        ("cover", SyntheticCover, "set_position", "set Study Blind to -50 percent"),
        ("cover", SyntheticCover, "set_position", "set Study Blind to1000percent"),
        ("cover", SyntheticCover, "set_position", "set Study Blind to 1000 percent"),
        ("cover", SyntheticCover, "set_tilt", "set Study Blind tilt to20.5percent"),
        ("cover", SyntheticCover, "set_tilt", "set Study Blind tilt to 20.5 percent"),
        ("cover", SyntheticCover, "set_tilt", "set Study Blind tilt to-50percent"),
        ("cover", SyntheticCover, "set_tilt", "set Study Blind tilt to -50 percent"),
        ("cover", SyntheticCover, "set_tilt", "set Study Blind tilt to1000percent"),
        ("cover", SyntheticCover, "set_tilt", "set Study Blind tilt to 1000 percent"),
        ("climate", SyntheticClimate, "set_temperature", "set Study Thermostat to121degrees"),
        ("climate", SyntheticClimate, "set_temperature", "set Study Thermostat to 121 degrees"),
        ("climate", SyntheticClimate, "set_temperature", "set Study Thermostat to-20degrees"),
        ("climate", SyntheticClimate, "set_temperature", "set Study Thermostat to -20 degrees"),
    ],
)
async def test_invalid_complete_numeric_literals_never_call_fast_services(
    hass, monkeypatch, domain, model, action, text
):
    assert await async_setup_component(hass, domain, {})
    entity = model()
    await hass.data[domain].async_add_entities([entity])
    exposed_entities.async_expose_entity(hass, "conversation", entity.entity_id, True)
    entry, agent_id = await install_jev(hass, monkeypatch)
    runtime = hass.data[DOMAIN][entry.entry_id]
    runtime.jev = FakeJevClient(classification(domain=domain, action=action, target_area="none"))
    handoff = AsyncMock(return_value=(None, None))
    monkeypatch.setattr("custom_components.jev_assist.conversation.async_try_handoff_to_conversation_agent", handoff)
    result = await converse(hass, agent_id, text)
    assert result.response.error_code == intent.IntentResponseErrorCode.FAILED_TO_HANDLE
    assert runtime.route_counts == {"grok": 1}
    assert entity.calls == []
    handoff.assert_awaited_once()


@pytest.mark.parametrize("sign", ["−", "–", "－"])
@pytest.mark.parametrize(
    "domain,action,name,value",
    [
        ("light", "set_brightness", "Study Lamp", "50 percent"),
        ("cover", "set_position", "Study Blind", "50 percent"),
        ("climate", "set_temperature", "Study Thermostat", "20 degrees"),
    ],
)
async def test_unicode_negative_signs_never_become_positive_fast_parameters(sign, domain, action, name, value):
    entity = ExposedEntity(f"{domain}.synthetic", domain, name, "Study")
    client = FakeJevClient(classification(domain=domain, action=action, target_area="none"))
    result = await route(f"set {name} to {sign}{value}", [entity], language="en", client=client)
    assert result.kind == "grok"
    assert result.service_data is None
