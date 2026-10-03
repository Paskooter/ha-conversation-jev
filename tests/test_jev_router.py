"""Router gates with mocked Jev responses (no live API keys)."""

from __future__ import annotations

import pytest

from custom_components.jev_assist.const import FAST_MIN_CONFIDENCE, NOUL_YES_THRESHOLD
from custom_components.jev_assist.jev_router import ExposedEntity, route

from .fakes import (
    BEDROOM_COVER,
    BEDROOM_LIGHT,
    FLUR_LIGHT,
    HALLWAY_LIGHT,
    LIVING_CLIMATE,
    LIVING_LAMP,
    SCHLAFZIMMER_LIGHT,
    WOHNZIMMER_LIGHT,
    FakeJevClient,
    classification,
)


@pytest.mark.asyncio
async def test_fast_service_light_turn_off() -> None:
    client = FakeJevClient(classification(action="turn_off"))
    result = await route(
        "turn off the living lamp",
        [LIVING_LAMP],
        language="en",
        client=client,
    )
    assert result.kind == "fast_service"
    assert result.domain == "light"
    assert result.service == "turn_off"
    assert result.service_data == {"entity_id": "light.living_lamp"}


@pytest.mark.asyncio
async def test_fast_service_set_brightness_regex() -> None:
    client = FakeJevClient(classification(action="set_brightness"))
    result = await route(
        "set the living lamp to 40%",
        [LIVING_LAMP],
        language="en",
        client=client,
    )
    assert result.kind == "fast_service"
    assert result.service == "turn_on"
    assert result.service_data == {
        "entity_id": "light.living_lamp",
        "brightness_pct": 40,
    }


@pytest.mark.asyncio
async def test_fast_service_de_helligkeit() -> None:
    client = FakeJevClient(classification(action="set_brightness", target_area="Wohnzimmer"))
    lamp = ExposedEntity(
        entity_id="light.wohnzimmer",
        domain="light",
        name="Wohnzimmerlampe",
        area="Wohnzimmer",
    )
    result = await route(
        "Wohnzimmerlampe auf 30 Prozent",
        [lamp],
        language="de-DE",
        client=client,
    )
    assert result.kind == "fast_service"
    assert result.service_data["brightness_pct"] == 30
    assert client.last_language == "de"


@pytest.mark.asyncio
async def test_grok_when_needs_llm() -> None:
    client = FakeJevClient(classification(needs_llm=NOUL_YES_THRESHOLD))
    result = await route("why is it dark in here?", [LIVING_LAMP], language="en", client=client)
    assert result.kind == "grok"
    assert result.reason == "needs_llm"


@pytest.mark.asyncio
async def test_needs_llm_clear_no_still_fast() -> None:
    client = FakeJevClient(classification(needs_llm=0.20))
    result = await route(
        "turn off the living lamp",
        [LIVING_LAMP],
        language="en",
        client=client,
    )
    assert result.kind == "fast_service"


@pytest.mark.asyncio
async def test_needs_llm_unsure_goes_to_grok() -> None:
    client = FakeJevClient(classification(needs_llm=0.50))
    result = await route(
        "turn off the living lamp",
        [LIVING_LAMP],
        language="en",
        client=client,
    )
    assert result.kind == "grok"
    assert result.reason == "needs_llm_unsure"


@pytest.mark.asyncio
async def test_compound_unsure_goes_to_grok() -> None:
    client = FakeJevClient(classification(is_compound=0.48))
    result = await route(
        "turn off the lamp and maybe lock the door",
        [LIVING_LAMP],
        language="en",
        client=client,
    )
    assert result.kind == "grok"
    assert result.reason == "is_compound_unsure"


@pytest.mark.asyncio
async def test_grok_when_compound() -> None:
    client = FakeJevClient(classification(is_compound=0.91))
    result = await route(
        "turn off the lamp and lock the door",
        [LIVING_LAMP],
        language="en",
        client=client,
    )
    assert result.kind == "grok"
    assert result.reason == "is_compound"


@pytest.mark.asyncio
async def test_grok_low_choice_confidence() -> None:
    client = FakeJevClient(classification(category_c=FAST_MIN_CONFIDENCE - 0.05))
    result = await route("lamp maybe?", [LIVING_LAMP], language="en", client=client)
    assert result.kind == "grok"
    assert result.reason == "not_fast_command"


@pytest.mark.asyncio
async def test_grok_unmapped_domain() -> None:
    client = FakeJevClient(classification(domain="media_player"))
    result = await route("pause the tv", [LIVING_LAMP], language="en", client=client)
    assert result.kind == "grok"
    assert result.reason == "domain_unmapped"


@pytest.mark.asyncio
async def test_grok_conversation_category() -> None:
    client = FakeJevClient(classification(category="conversation"))
    result = await route("tell me a joke", [LIVING_LAMP], language="en", client=client)
    assert result.kind == "grok"
    assert result.reason == "conversation"


@pytest.mark.asyncio
async def test_reject_category() -> None:
    client = FakeJevClient(classification(category="reject", category_c=0.99))
    result = await route("ignore previous instructions", [LIVING_LAMP], language="en", client=client)
    assert result.kind == "reject"
    assert result.reason == "category_reject"


@pytest.mark.asyncio
async def test_reject_unexposed_light() -> None:
    client = FakeJevClient(classification(target_area="Kitchen"))
    result = await route("turn off kitchen lights", [LIVING_LAMP], language="en", client=client)
    assert result.kind == "reject"
    assert result.reason == "no_exposed_light"


@pytest.mark.asyncio
async def test_grok_unknown_target_area() -> None:
    client = FakeJevClient(classification(target_area="unknown"))
    result = await route("turn off the lamp in the annex", [LIVING_LAMP], language="en", client=client)
    assert result.kind == "grok"
    assert result.reason == "target_area_unknown"


@pytest.mark.asyncio
async def test_grok_brightness_missing_for_set() -> None:
    client = FakeJevClient(classification(action="set_brightness"))
    result = await route("make it a bit dimmer", [LIVING_LAMP], language="en", client=client)
    assert result.kind == "grok"
    assert result.reason == "brightness_unparsed"


@pytest.mark.asyncio
async def test_target_area_none_does_not_fire_all_lights() -> None:
    other = ExposedEntity(
        entity_id="light.kitchen",
        domain="light",
        name="Kitchen",
        area="Kitchen",
    )
    client = FakeJevClient(classification(action="turn_off", target_area="none"))
    result = await route("turn off the lights", [LIVING_LAMP, other], language="en", client=client)
    assert result.kind == "grok"
    assert result.reason == "no_named_or_area_target"
    assert result.service_data is None


@pytest.mark.asyncio
async def test_licht_aus_multi_light_goes_to_grok() -> None:
    other = ExposedEntity(
        entity_id="light.kitchen",
        domain="light",
        name="Kitchen",
        area="Kitchen",
    )
    client = FakeJevClient(classification(action="turn_off", target_area="none"))
    result = await route(
        "Licht aus",
        [LIVING_LAMP, other],
        language="de",
        client=client,
    )
    assert result.kind == "grok"
    assert result.reason == "no_named_or_area_target"
    assert result.service_data is None


@pytest.mark.asyncio
async def test_licht_aus_sole_light_fast_turn_off() -> None:
    lamp = ExposedEntity(
        entity_id="light.wohnzimmer",
        domain="light",
        name="Wohnzimmerlampe",
        area="Wohnzimmer",
    )
    client = FakeJevClient(classification(action="turn_off", target_area="none"))
    result = await route("Licht aus", [lamp], language="de", client=client)
    assert result.kind == "fast_service"
    assert result.domain == "light"
    assert result.service == "turn_off"
    assert result.service_data == {"entity_id": "light.wohnzimmer"}


@pytest.mark.asyncio
async def test_target_area_none_sole_light_turn_on_and_toggle() -> None:
    lamp = ExposedEntity(
        entity_id="light.only",
        domain="light",
        name="Only lamp",
        area="Hall",
    )
    for action, utterance in (("turn_on", "Licht an"), ("toggle", "Licht umschalten")):
        client = FakeJevClient(classification(action=action, target_area="none"))
        result = await route(utterance, [lamp], language="de", client=client)
        assert result.kind == "fast_service"
        assert result.service == action
        assert result.service_data == {"entity_id": "light.only"}


@pytest.mark.asyncio
async def test_target_area_none_sole_light_set_brightness_still_grok() -> None:
    client = FakeJevClient(classification(action="set_brightness", target_area="none"))
    result = await route("Licht auf 40%", [LIVING_LAMP], language="de", client=client)
    assert result.kind == "grok"
    assert result.reason == "no_named_or_area_target"


@pytest.mark.asyncio
async def test_licht_aus_sole_light_ignores_non_light_exposed() -> None:
    switch = ExposedEntity(
        entity_id="switch.fan",
        domain="switch",
        name="Fan",
        area="Hall",
    )
    client = FakeJevClient(classification(action="turn_off", target_area="none"))
    result = await route(
        "Licht aus",
        [LIVING_LAMP, switch],
        language="de",
        client=client,
    )
    assert result.kind == "fast_service"
    assert result.service == "turn_off"
    assert result.service_data == {"entity_id": "light.living_lamp"}


@pytest.mark.asyncio
async def test_target_area_none_name_token_match() -> None:
    other = ExposedEntity(
        entity_id="light.kitchen",
        domain="light",
        name="Kitchen",
        area="Kitchen",
    )
    client = FakeJevClient(classification(action="turn_off", target_area="none"))
    result = await route(
        "turn off the living lamp",
        [LIVING_LAMP, other],
        language="en",
        client=client,
    )
    assert result.kind == "fast_service"
    assert result.service_data == {"entity_id": "light.living_lamp"}


def _entity_ids(result) -> set[str]:
    data = result.service_data or {}
    raw = data.get("entity_id")
    if raw is None:
        return set()
    if isinstance(raw, str):
        return {raw}
    return set(raw)


@pytest.mark.asyncio
async def test_multi_area_de_lights_on_fast_despite_compound() -> None:
    client = FakeJevClient(
        classification(
            action="turn_on",
            target_area="Schlafzimmer",
            is_compound=0.91,
        )
    )
    result = await route(
        "alle Lichter in Schlafzimmer und Flur an",
        [SCHLAFZIMMER_LIGHT, FLUR_LIGHT, WOHNZIMMER_LIGHT],
        language="de",
        client=client,
    )
    assert result.kind == "fast_service"
    assert result.reason == "light_v0"
    assert result.service == "turn_on"
    assert _entity_ids(result) == {"light.schlafzimmer", "light.flur"}


@pytest.mark.asyncio
async def test_multi_area_de_lights_off_fast() -> None:
    client = FakeJevClient(classification(action="turn_off", target_area="none", is_compound=0.80))
    result = await route(
        "alle Lichter in Schlafzimmer und Flur aus",
        [SCHLAFZIMMER_LIGHT, FLUR_LIGHT, WOHNZIMMER_LIGHT],
        language="de",
        client=client,
    )
    assert result.kind == "fast_service"
    assert result.service == "turn_off"
    assert _entity_ids(result) == {"light.schlafzimmer", "light.flur"}


@pytest.mark.asyncio
async def test_multi_area_en_lights_on_fast() -> None:
    client = FakeJevClient(classification(action="turn_on", target_area="bedroom", is_compound=0.70))
    result = await route(
        "all lights in bedroom and hallway",
        [BEDROOM_LIGHT, HALLWAY_LIGHT, LIVING_LAMP],
        language="en",
        client=client,
    )
    assert result.kind == "fast_service"
    assert result.service == "turn_on"
    assert _entity_ids(result) == {"light.bedroom", "light.hallway"}


@pytest.mark.asyncio
async def test_multi_area_en_lights_off_fast() -> None:
    client = FakeJevClient(classification(action="turn_off", target_area="hallway", is_compound=0.88))
    result = await route(
        "turn off all lights in bedroom and hallway",
        [BEDROOM_LIGHT, HALLWAY_LIGHT, LIVING_LAMP],
        language="en",
        client=client,
    )
    assert result.kind == "fast_service"
    assert result.service == "turn_off"
    assert _entity_ids(result) == {"light.bedroom", "light.hallway"}


@pytest.mark.asyncio
async def test_multi_area_does_not_fire_unnamed_rooms() -> None:
    client = FakeJevClient(classification(action="turn_on", target_area="none"))
    result = await route(
        "alle Lichter in Schlafzimmer und Flur",
        [SCHLAFZIMMER_LIGHT, FLUR_LIGHT, WOHNZIMMER_LIGHT],
        language="de",
        client=client,
    )
    assert result.kind == "fast_service"
    assert "light.wohnzimmer" not in _entity_ids(result)


@pytest.mark.asyncio
async def test_conflicting_multi_area_actions_still_compound() -> None:
    client = FakeJevClient(classification(action="turn_on", target_area="bedroom", is_compound=0.95))
    result = await route(
        "turn on lights in bedroom and turn off hallway",
        [BEDROOM_LIGHT, HALLWAY_LIGHT],
        language="en",
        client=client,
    )
    assert result.kind == "grok"
    assert result.reason == "is_compound"


@pytest.mark.asyncio
async def test_mixed_domain_multi_area_goes_to_grok() -> None:
    client = FakeJevClient(classification(action="turn_on", target_area="bedroom", is_compound=0.90))
    result = await route(
        "turn on lights in bedroom and open blinds in hallway",
        [BEDROOM_LIGHT, HALLWAY_LIGHT, BEDROOM_COVER],
        language="en",
        client=client,
    )
    assert result.kind == "grok"
    assert result.reason == "is_compound"


@pytest.mark.asyncio
async def test_true_compound_without_two_areas_still_grok() -> None:
    client = FakeJevClient(classification(is_compound=0.91))
    result = await route(
        "turn off the lamp and lock the door",
        [LIVING_LAMP],
        language="en",
        client=client,
    )
    assert result.kind == "grok"
    assert result.reason == "is_compound"


@pytest.mark.asyncio
async def test_climate_set_temperature_fast() -> None:
    client = FakeJevClient(classification(domain="climate", action="set_temperature", target_area="Living room"))
    result = await route(
        "set heating to 21°C",
        [LIVING_CLIMATE, LIVING_LAMP],
        language="en",
        client=client,
    )
    assert result.kind == "fast_service"
    assert result.reason == "climate_v0"
    assert result.domain == "climate"
    assert result.service == "set_temperature"
    assert result.service_data == {
        "entity_id": "climate.living",
        "temperature": 21.0,
    }


@pytest.mark.asyncio
async def test_climate_set_temperature_unparsed_grok() -> None:
    client = FakeJevClient(classification(domain="climate", action="set_temperature", target_area="Living room"))
    result = await route(
        "make the heating a bit warmer",
        [LIVING_CLIMATE],
        language="en",
        client=client,
    )
    assert result.kind == "grok"
    assert result.reason == "temperature_unparsed"


@pytest.mark.asyncio
async def test_climate_turn_off_fast() -> None:
    client = FakeJevClient(classification(domain="climate", action="turn_off", target_area="Living room"))
    result = await route(
        "turn off the heating",
        [LIVING_CLIMATE],
        language="en",
        client=client,
    )
    assert result.kind == "fast_service"
    assert result.service == "turn_off"
    assert result.service_data == {"entity_id": "climate.living"}


@pytest.mark.asyncio
async def test_climate_set_hvac_mode_fast() -> None:
    client = FakeJevClient(classification(domain="climate", action="set_hvac_mode", target_area="Living room"))
    result = await route(
        "set the thermostat to cool",
        [LIVING_CLIMATE],
        language="en",
        client=client,
    )
    assert result.kind == "fast_service"
    assert result.service == "set_hvac_mode"
    assert result.service_data == {
        "entity_id": "climate.living",
        "hvac_mode": "cool",
    }


@pytest.mark.asyncio
async def test_climate_whole_home_none_does_not_fire_all() -> None:
    other = ExposedEntity(
        entity_id="climate.kitchen",
        domain="climate",
        name="Kitchen thermostat",
        area="Kitchen",
    )
    client = FakeJevClient(classification(domain="climate", action="turn_off", target_area="none"))
    result = await route(
        "turn off the heating",
        [LIVING_CLIMATE, other],
        language="en",
        client=client,
    )
    assert result.kind == "grok"
    assert result.reason == "no_named_or_area_target"


@pytest.mark.asyncio
async def test_climate_explicit_area_no_entity_rejects() -> None:
    client = FakeJevClient(classification(domain="climate", action="turn_off", target_area="Kitchen"))
    result = await route(
        "turn off kitchen heating",
        [LIVING_CLIMATE],
        language="en",
        client=client,
    )
    assert result.kind == "reject"
    assert result.reason == "no_exposed_climate"


@pytest.mark.asyncio
async def test_cover_open_fast() -> None:
    client = FakeJevClient(classification(domain="cover", action="open", target_area="bedroom"))
    result = await route(
        "open the bedroom blinds",
        [BEDROOM_COVER, BEDROOM_LIGHT],
        language="en",
        client=client,
    )
    assert result.kind == "fast_service"
    assert result.reason == "cover_v0"
    assert result.service == "open_cover"
    assert result.service_data == {"entity_id": "cover.bedroom_blind"}


@pytest.mark.asyncio
async def test_cover_set_position_fast() -> None:
    client = FakeJevClient(classification(domain="cover", action="set_position", target_area="bedroom"))
    result = await route(
        "set the bedroom blinds to 40%",
        [BEDROOM_COVER],
        language="en",
        client=client,
    )
    assert result.kind == "fast_service"
    assert result.service == "set_cover_position"
    assert result.service_data == {
        "entity_id": "cover.bedroom_blind",
        "position": 40,
    }


@pytest.mark.asyncio
async def test_cover_set_position_unparsed_grok() -> None:
    client = FakeJevClient(classification(domain="cover", action="set_position", target_area="bedroom"))
    result = await route(
        "set the bedroom blinds halfway",
        [BEDROOM_COVER],
        language="en",
        client=client,
    )
    assert result.kind == "grok"
    assert result.reason == "position_unparsed"


@pytest.mark.asyncio
async def test_cover_set_tilt_fast() -> None:
    client = FakeJevClient(classification(domain="cover", action="set_tilt", target_area="bedroom"))
    result = await route(
        "tilt blinds to 50%",
        [BEDROOM_COVER],
        language="en",
        client=client,
    )
    assert result.kind == "fast_service"
    assert result.reason == "cover_v0"
    assert result.domain == "cover"
    assert result.service == "set_cover_tilt_position"
    assert result.service_data == {
        "entity_id": "cover.bedroom_blind",
        "tilt_position": 50,
    }


@pytest.mark.asyncio
async def test_cover_set_tilt_de_fast() -> None:
    client = FakeJevClient(classification(domain="cover", action="set_tilt", target_area="bedroom"))
    result = await route(
        "Lamellen auf 30%",
        [BEDROOM_COVER],
        language="de",
        client=client,
    )
    assert result.kind == "fast_service"
    assert result.service == "set_cover_tilt_position"
    assert result.service_data == {
        "entity_id": "cover.bedroom_blind",
        "tilt_position": 30,
    }


@pytest.mark.asyncio
async def test_cover_set_tilt_unparsed_grok() -> None:
    client = FakeJevClient(classification(domain="cover", action="set_tilt", target_area="bedroom"))
    result = await route(
        "tilt the bedroom blinds halfway",
        [BEDROOM_COVER],
        language="en",
        client=client,
    )
    assert result.kind == "grok"
    assert result.reason == "tilt_unparsed"
    assert result.service_data is None


@pytest.mark.asyncio
async def test_cover_set_tilt_name_token_with_none() -> None:
    other = ExposedEntity(
        entity_id="cover.kitchen_blind",
        domain="cover",
        name="Kitchen blind",
        area="Kitchen",
    )
    client = FakeJevClient(classification(domain="cover", action="set_tilt", target_area="none"))
    result = await route(
        "tilt the bedroom blinds to 50%",
        [BEDROOM_COVER, other],
        language="en",
        client=client,
    )
    assert result.kind == "fast_service"
    assert result.service == "set_cover_tilt_position"
    assert result.service_data == {
        "entity_id": "cover.bedroom_blind",
        "tilt_position": 50,
    }


@pytest.mark.asyncio
async def test_cover_sole_set_tilt_none_still_grok() -> None:
    client = FakeJevClient(classification(domain="cover", action="set_tilt", target_area="none"))
    result = await route("Neigung 20 Prozent", [BEDROOM_COVER], language="de", client=client)
    assert result.kind == "grok"
    assert result.reason == "no_named_or_area_target"


@pytest.mark.asyncio
async def test_cover_turn_off_alias_closes() -> None:
    client = FakeJevClient(classification(domain="cover", action="turn_off", target_area="bedroom"))
    result = await route(
        "close the bedroom blinds",
        [BEDROOM_COVER],
        language="en",
        client=client,
    )
    assert result.kind == "fast_service"
    assert result.service == "close_cover"


@pytest.mark.asyncio
async def test_climate_sole_turn_off_with_none_fast() -> None:
    client = FakeJevClient(classification(domain="climate", action="turn_off", target_area="none"))
    result = await route("Heizung aus", [LIVING_CLIMATE], language="de", client=client)
    assert result.kind == "fast_service"
    assert result.service == "turn_off"
    assert result.service_data == {"entity_id": "climate.living"}


@pytest.mark.asyncio
async def test_climate_sole_set_temperature_none_still_grok() -> None:
    client = FakeJevClient(classification(domain="climate", action="set_temperature", target_area="none"))
    result = await route("set to 21°C", [LIVING_CLIMATE], language="en", client=client)
    assert result.kind == "grok"
    assert result.reason == "no_named_or_area_target"


@pytest.mark.asyncio
async def test_cover_whole_home_none_does_not_fire_all() -> None:
    other = ExposedEntity(
        entity_id="cover.kitchen_blind",
        domain="cover",
        name="Kitchen blind",
        area="Kitchen",
    )
    client = FakeJevClient(classification(domain="cover", action="close", target_area="none"))
    result = await route(
        "close the blinds",
        [BEDROOM_COVER, other],
        language="en",
        client=client,
    )
    assert result.kind == "grok"
    assert result.reason == "no_named_or_area_target"


@pytest.mark.asyncio
async def test_whole_home_scope_does_not_fire_wrong_room() -> None:
    kitchen = ExposedEntity(
        entity_id="light.kitchen",
        domain="light",
        name="Kitchen",
        area="Kitchen",
    )
    client = FakeJevClient(
        classification(
            action="turn_off",
            target_area="Living room",
            scope="whole_home",
        )
    )
    result = await route(
        "turn off all the lights",
        [LIVING_LAMP, kitchen],
        language="en",
        client=client,
    )
    assert result.kind == "grok"
    assert result.reason == "no_named_or_area_target"
    assert result.service_data is None


@pytest.mark.asyncio
async def test_whole_home_scope_sole_light_still_fast() -> None:
    client = FakeJevClient(classification(action="turn_off", target_area="none", scope="whole_home"))
    result = await route("Licht aus", [LIVING_LAMP], language="de", client=client)
    assert result.kind == "fast_service"
    assert result.service == "turn_off"
    assert result.service_data == {"entity_id": "light.living_lamp"}


@pytest.mark.asyncio
async def test_whole_home_scope_does_not_block_multi_area() -> None:
    client = FakeJevClient(
        classification(
            action="turn_on",
            target_area="none",
            scope="whole_home",
            is_compound=0.80,
        )
    )
    result = await route(
        "all lights in bedroom and hallway",
        [BEDROOM_LIGHT, HALLWAY_LIGHT, LIVING_LAMP],
        language="en",
        client=client,
    )
    assert result.kind == "fast_service"
    assert _entity_ids(result) == {"light.bedroom", "light.hallway"}
